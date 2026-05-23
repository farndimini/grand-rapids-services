"""
memory_index.py — Searchable Memory Layer
==========================================
Wraps the existing JSON memory with:
  • Full-text keyword search across articles
  • Niche / topic indexing
  • Trend analysis (performance over time)
  • Duplicate detection

Usage:
    from agent_core.memory_index import MemoryIndex
    idx = MemoryIndex()
    results = idx.search("password manager")
    duplicates = idx.find_duplicates(threshold=0.7)
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import memory as mem_module

log = logging.getLogger("agent_core.memory_index")


@dataclass
class ArticleRecord:
    keyword: str
    model: str
    word_count: int
    date: str
    performance_history: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def latest_position(self) -> int | None:
        if self.performance_history:
            return self.performance_history[-1].get("position")
        return None

    @property
    def avg_ctr(self) -> float | None:
        ctrs = [p.get("ctr") for p in self.performance_history if p.get("ctr") is not None]
        return sum(ctrs) / len(ctrs) if ctrs else None

    @property
    def revision_count(self) -> int:
        return len(self.performance_history)


class MemoryIndex:
    """Enhanced search and analytics over the existing memory system."""

    def __init__(self):
        self._articles: list[ArticleRecord] = []
        self._keyword_index: dict[str, set[int]] = {}  # token -> article indices
        self._niche_index: dict[str, list[int]] = {}    # niche -> article indices
        self._rebuild()

    # ── Indexing ───────────────────────────────────────────

    def _rebuild(self) -> None:
        """Reload and index memory from disk."""
        mem = mem_module.load()
        self._articles = []
        self._keyword_index.clear()
        self._niche_index.clear()

        for i, raw in enumerate(mem.get("articles_written", [])):
            rec = ArticleRecord(
                keyword=raw.get("keyword", ""),
                model=raw.get("model", ""),
                word_count=raw.get("word_count", 0),
                date=raw.get("date", ""),
                performance_history=raw.get("performance_history", []),
                raw=raw,
            )
            self._articles.append(rec)
            self._index_article(i, rec)

        log.debug(f"[INDEX] Rebuilt with {len(self._articles)} articles")

    def _index_article(self, idx: int, rec: ArticleRecord) -> None:
        tokens = self._tokenize(rec.keyword)
        for tok in tokens:
            self._keyword_index.setdefault(tok, set()).add(idx)
        # Cluster-based niche indexing
        mem = mem_module.load()
        for niche, cluster_data in mem.get("clusters", {}).items():
            pillar_kw = cluster_data.get("pillar", {}).get("keyword", "")
            cluster_kws = [c.get("keyword", "") for c in cluster_data.get("clusters", [])]
            if rec.keyword == pillar_kw or rec.keyword in cluster_kws:
                self._niche_index.setdefault(niche, []).append(idx)

    def _tokenize(self, text: str) -> list[str]:
        return [t.lower() for t in re.findall(r'\b\w{3,}\b', text) if t.lower() not in {
            "the","and","for","are","but","not","you","all","any","can","her","was",
            "one","our","out","day","get","has","him","his","how","man","new","now",
            "old","see","two","way","who","boy","did","its","let","put","say","she",
            "too","use","best","top","review","guide","complete","ultimate","free",
        }]

    # ── Search ─────────────────────────────────────────────

    def search(self, query: str, top_n: int = 10) -> list[ArticleRecord]:
        """Full-text keyword search across articles."""
        self._rebuild()
        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []

        scores: Counter[int] = Counter()
        for tok in q_tokens:
            for idx in self._keyword_index.get(tok, set()):
                scores[idx] += 1

        # TF bonus: exact phrase match
        query_lower = query.lower()
        for idx, rec in enumerate(self._articles):
            if query_lower in rec.keyword.lower():
                scores[idx] += 5

        ranked = scores.most_common(top_n * 2)
        return [self._articles[i] for i, _ in ranked[:top_n]]

    def by_niche(self, niche: str) -> list[ArticleRecord]:
        """Return articles belonging to a niche cluster."""
        self._rebuild()
        indices = self._niche_index.get(niche, [])
        return [self._articles[i] for i in indices if 0 <= i < len(self._articles)]

    def find_duplicates(self, threshold: float = 0.75) -> list[tuple[str, str, float]]:
        """Find article pairs with high keyword overlap (potential duplicates)."""
        self._rebuild()
        duplicates = []
        n = len(self._articles)
        for i in range(n):
            for j in range(i + 1, n):
                a = self._articles[i]
                b = self._articles[j]
                sim = self._jaccard_similarity(a.keyword, b.keyword)
                if sim >= threshold:
                    duplicates.append((a.keyword, b.keyword, sim))
        return sorted(duplicates, key=lambda x: x[2], reverse=True)

    def trend_analysis(self, keyword: str | None = None) -> dict[str, Any]:
        """Analyze performance trends over time."""
        self._rebuild()
        articles = [a for a in self._articles if not keyword or keyword.lower() in a.keyword.lower()]
        if not articles:
            return {"error": "No data"}

        positions = []
        ctrs = []
        revisions = []
        for a in articles:
            if a.latest_position is not None:
                positions.append(a.latest_position)
            if a.avg_ctr is not None:
                ctrs.append(a.avg_ctr)
            revisions.append(a.revision_count)

        return {
            "article_count": len(articles),
            "avg_position": round(sum(positions) / len(positions), 1) if positions else None,
            "avg_ctr": round(sum(ctrs) / len(ctrs), 2) if ctrs else None,
            "avg_revisions": round(sum(revisions) / len(revisions), 1) if revisions else 0,
            "underperformers": len([a for a in articles if (a.latest_position or 999) > 20]),
            "stars": len([a for a in articles if (a.latest_position or 999) <= 3]),
        }

    # ── Utility ────────────────────────────────────────────

    @staticmethod
    def _jaccard_similarity(a: str, b: str) -> float:
        tokens_a = set(MemoryIndex._static_tokenize(a))
        tokens_b = set(MemoryIndex._static_tokenize(b))
        if not tokens_a or not tokens_b:
            return 0.0
        inter = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        return inter / union if union else 0.0

    @staticmethod
    def _static_tokenize(text: str) -> list[str]:
        return [t.lower() for t in re.findall(r'\b\w{3,}\b', text)]

    def summary(self) -> dict[str, Any]:
        self._rebuild()
        return {
            "total_articles": len(self._articles),
            "indexed_keywords": len(self._keyword_index),
            "indexed_niches": list(self._niche_index.keys()),
            "models_used": list(set(a.model for a in self._articles)),
            "avg_word_count": sum(a.word_count for a in self._articles) / max(1, len(self._articles)),
        }
