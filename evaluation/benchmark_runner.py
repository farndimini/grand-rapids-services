"""
evaluation/benchmark_runner.py — Full Article Evaluation Pipeline
==================================================================
Orchestrates all scorers into a single benchmark report:

  Generated Article
      ↓
  SERP Benchmark Extraction (optional)
      ↓
  Semantic Scoring
  Structure Scoring
  SERP Alignment Scoring
  Readability Scoring
  E-E-A-T Scoring
      ↓
  Weighted Final Score
      ↓
  Regression Check (vs. historical baseline)

Usage:
    from evaluation.benchmark_runner import BenchmarkRunner
    runner = BenchmarkRunner()
    report = runner.evaluate(article_html, keyword="best CRM", serp_data=serp)
    print(report.final_score, report.verdict)
"""

from __future__ import annotations

import json
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import re

from evaluation.scorers import SemanticScorer, StructureScorer, SERPScorer, ReadabilityScorer, ScoreResult
from agent_core.validator import SemanticValidator
from agent_core.metrics_store import MetricsStore

log = logging.getLogger("evaluation.benchmark_runner")

# Default weights for composite scoring
DEFAULT_WEIGHTS = {
    "semantic": 0.20,
    "structure": 0.20,
    "serp_alignment": 0.20,
    "readability": 0.15,
    "eeat": 0.15,
    "quality_gate": 0.10,
}


@dataclass
class BenchmarkReport:
    keyword: str
    final_score: float
    verdict: str
    dimension_scores: dict[str, ScoreResult]
    weights_used: dict[str, float]
    regression_delta: float | None = None
    baseline_score: float | None = None
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "keyword": self.keyword,
            "final_score": self.final_score,
            "verdict": self.verdict,
            "dimension_scores": {
                k: {"score": v.score, "feedback": v.feedback, "details": v.details}
                for k, v in self.dimension_scores.items()
            },
            "weights_used": self.weights_used,
            "regression_delta": self.regression_delta,
            "baseline_score": self.baseline_score,
            "generated_at": self.generated_at,
            "meta": self.meta,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class BenchmarkRunner:
    """End-to-end article evaluation with regression tracking."""

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        dataset_dir: Path | str = "evaluation/datasets",
    ):
        self.weights = weights or dict(DEFAULT_WEIGHTS)
        self.semantic = SemanticScorer()
        self.structure = StructureScorer()
        self.serp = SERPScorer()
        self.readability = ReadabilityScorer()
        self.validator = SemanticValidator()
        self.dataset_dir = Path(dataset_dir)
        self.dataset_dir.mkdir(parents=True, exist_ok=True)
        self._store = MetricsStore()

    def evaluate(
        self,
        article_html: str,
        keyword: str,
        serp_data: dict | None = None,
        model: str = "unknown",
    ) -> BenchmarkReport:
        """Run full benchmark suite on generated article."""
        text_only = self._strip_html(article_html)
        word_count = len(text_only.split())

        # 1. Semantic
        sem = self.semantic.score(text_only, keyword)

        # 2. Structure
        struct = self.structure.score(article_html, keyword)

        # 3. SERP alignment
        serp_res = self.serp.score(article_html, keyword, serp_data)

        # 4. Readability
        read = self.readability.score(text_only)

        # 5. E-E-A-T via SemanticValidator
        val_report = self.validator.validate(article_html, keyword)
        eeat_result = ScoreResult(
            score=val_report.eeat_score,
            weight=self.weights.get("eeat", 0.15),
            feedback=val_report.warnings[:5],
            details={"readability_ease": val_report.readability_ease},
        )

        # 6. Quality gate
        quality_result = ScoreResult(
            score=val_report.score,
            weight=self.weights.get("quality_gate", 0.10),
            feedback=val_report.issues,
            details={"pass": val_report.passed(70)},
        )

        dimensions = {
            "semantic": sem,
            "structure": struct,
            "serp_alignment": serp_res,
            "readability": read,
            "eeat": eeat_result,
            "quality_gate": quality_result,
        }

        # Weighted final score
        final = sum(
            dimensions[k].score * self.weights.get(k, 0)
            for k in dimensions
        )
        final = min(100.0, max(0.0, round(final, 1)))

        # Verdict
        if final >= 85:
            verdict = "EXCELLENT"
        elif final >= 70:
            verdict = "GOOD"
        elif final >= 55:
            verdict = "ACCEPTABLE"
        elif final >= 40:
            verdict = "NEEDS_IMPROVEMENT"
        else:
            verdict = "POOR"

        # Regression check against historical baseline for keyword
        baseline = self._load_baseline(keyword)
        regression_delta = None
        if baseline:
            regression_delta = round(final - baseline, 1)
            if regression_delta < -5:
                verdict += " [REGRESSION]"

        # Persist to dataset
        self._save_to_dataset(keyword, article_html, final, model)

        # Store metrics


        return BenchmarkReport(
            keyword=keyword,
            final_score=final,
            verdict=verdict,
            dimension_scores=dimensions,
            weights_used=dict(self.weights),
            regression_delta=regression_delta,
            baseline_score=baseline,
            meta={
                "word_count": word_count,
                "model": model,
                "has_serp_data": serp_data is not None,
                "validation_passed": val_report.passed(70),
            },
        )

    def compare_models(
        self,
        keyword: str,
        model_outputs: dict[str, str],
        serp_data: dict | None = None,
    ) -> dict[str, BenchmarkReport]:
        """Evaluate multiple model outputs for the same keyword and return ranking."""
        results = {}
        for model, html in model_outputs.items():
            results[model] = self.evaluate(html, keyword, serp_data, model=model)
        return dict(sorted(results.items(), key=lambda x: x[1].final_score, reverse=True))

    def leaderboard(self, keyword: str | None = None, top_n: int = 10) -> list[dict]:
        """Return top-performing generations from dataset."""
        pattern = f"{keyword or '*'}.jsonl"
        entries = []
        for f in self.dataset_dir.glob("*.jsonl"):
            if keyword and keyword not in f.stem:
                continue
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        entry = json.loads(line)
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        entries.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        return entries[:top_n]

    def _strip_html(self, html: str) -> str:
        text = re.sub(r'<[^>]+>', ' ', html)
        return re.sub(r'\s+', ' ', text).strip()

    def _load_baseline(self, keyword: str) -> float | None:
        f = self.dataset_dir / f"{keyword.replace(' ', '_')}.jsonl"
        if not f.exists():
            return None
        scores = []
        with open(f, "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    scores.append(json.loads(line).get("final_score", 0))
                except Exception:
                    continue
        return statistics.median(scores) if scores else None

    def _save_to_dataset(self, keyword: str, article_html: str, score: float, model: str) -> None:
        f = self.dataset_dir / f"{keyword.replace(' ', '_')}.jsonl"
        entry = {
            "timestamp": datetime.now().isoformat(),
            "keyword": keyword,
            "model": model,
            "final_score": score,
            "word_count": len(self._strip_html(article_html).split()),
        }
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    @staticmethod
    def _reward_from_score(score: float) -> float:
        """Map 0-100 score to -1..+1 reward signal."""
        if score >= 90:
            return 1.0
        if score >= 75:
            return 0.5
        if score >= 60:
            return 0.0
        if score >= 40:
            return -0.5
        return -1.0
