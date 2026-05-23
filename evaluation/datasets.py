"""
evaluation/datasets.py — Evaluation Dataset Management
========================================================
Handles storage, versioning, and retrieval of:
  • Historical article generations
  • SERP benchmark snapshots
  • Prompt variant outcomes
  • Model variant outcomes

Provides regression detection and dataset curation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("evaluation.datasets")


@dataclass
class DatasetEntry:
    keyword: str
    model: str
    prompt_variant: str
    final_score: float
    article_hash: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "keyword": self.keyword,
            "model": self.model,
            "prompt_variant": self.prompt_variant,
            "final_score": self.final_score,
            "article_hash": self.article_hash,
            "timestamp": self.timestamp,
            "meta": self.meta,
        }


class EvaluationDataset:
    """Manages on-disk dataset of generation runs for regression testing."""

    def __init__(self, base_dir: Path | str = "evaluation/datasets"):
        self._dir = Path(base_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self._dir / "_index.json"
        self._index = self._load_index()

    def _load_index(self) -> dict[str, Any]:
        if self._index_file.exists():
            try:
                return json.loads(self._index_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {"version": 1, "entries": [], "baselines": {}}

    def _save_index(self) -> None:
        self._index_file.write_text(json.dumps(self._index, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, entry: DatasetEntry) -> None:
        """Add an entry to the dataset and update index."""
        keyword_slug = entry.keyword.replace(" ", "_")
        dataset_file = self._dir / f"{keyword_slug}.jsonl"
        with open(dataset_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

        self._index["entries"].append({
            "keyword": entry.keyword,
            "model": entry.model,
            "prompt_variant": entry.prompt_variant,
            "score": entry.final_score,
            "timestamp": entry.timestamp,
        })
        self._save_index()

        # Update running baseline
        self._update_baseline(entry.keyword)

    def _update_baseline(self, keyword: str) -> None:
        """Recalculate baseline (median score) for keyword."""
        scores = [
            e["score"] for e in self._index["entries"]
            if e["keyword"] == keyword and e["score"] > 0
        ]
        if scores:
            import statistics
            self._index["baselines"][keyword] = round(statistics.median(scores), 1)
            self._save_index()

    def get_baseline(self, keyword: str) -> float | None:
        return self._index["baselines"].get(keyword)

    def get_entries(self, keyword: str | None = None, model: str | None = None,
                    prompt_variant: str | None = None, limit: int = 100) -> list[DatasetEntry]:
        """Query dataset with optional filters."""
        entries = []
        for e in self._index["entries"]:
            if keyword and e["keyword"] != keyword:
                continue
            if model and e["model"] != model:
                continue
            if prompt_variant and e.get("prompt_variant") != prompt_variant:
                continue
            entries.append(e)
        return entries[:limit]

    def best_for_keyword(self, keyword: str) -> dict | None:
        """Return the highest-scoring entry for a keyword."""
        matches = [e for e in self._index["entries"] if e["keyword"] == keyword]
        if not matches:
            return None
        best = max(matches, key=lambda x: x["score"])
        return best

    def regression_check(self, keyword: str, new_score: float, threshold: float = 5.0) -> dict:
        """Check if new_score regresses from baseline."""
        baseline = self.get_baseline(keyword)
        if baseline is None:
            return {"regression": False, "baseline": None, "delta": 0.0, "message": "No baseline"}
        delta = new_score - baseline
        return {
            "regression": delta < -threshold,
            "baseline": baseline,
            "delta": round(delta, 1),
            "message": f"Score {new_score} vs baseline {baseline} (Δ {delta:+.1f})",
        }

    def prompt_leaderboard(self) -> list[dict]:
        """Rank prompt variants by average score."""
        from collections import defaultdict
        stats = defaultdict(lambda: {"scores": [], "count": 0})
        for e in self._index["entries"]:
            pv = e.get("prompt_variant", "default")
            stats[pv]["scores"].append(e["score"])
            stats[pv]["count"] += 1
        import statistics
        ranked = []
        for pv, data in stats.items():
            ranked.append({
                "prompt_variant": pv,
                "avg_score": round(statistics.mean(data["scores"]), 1),
                "count": data["count"],
            })
        ranked.sort(key=lambda x: x["avg_score"], reverse=True)
        return ranked

    def model_leaderboard(self) -> list[dict]:
        """Rank models by average score."""
        from collections import defaultdict
        stats = defaultdict(lambda: {"scores": [], "count": 0})
        for e in self._index["entries"]:
            stats[e["model"]]["scores"].append(e["score"])
            stats[e["model"]]["count"] += 1
        import statistics
        ranked = []
        for model, data in stats.items():
            ranked.append({
                "model": model,
                "avg_score": round(statistics.mean(data["scores"]), 1),
                "count": data["count"],
            })
        ranked.sort(key=lambda x: x["avg_score"], reverse=True)
        return ranked
