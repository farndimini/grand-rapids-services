"""editorial_score.py — Unified Editorial Scoring Dashboard

Consolidates all quality signals into a single FINAL_EDITORIAL_SCORE.

Weights:
  trust_score      x 0.30  (adaptive_trust_engine → PublishRiskReport)
  freshness_score  x 0.20  (temporal_governor → freshness_report / temporal_grounding violations)
  coverage_score   x 0.20  (coverage_validator → outline coverage)
  citation_score   x 0.15  (evidence_dag → claim support / truth_infrastructure citations)
  entropy_score    x 0.15  (generation_consensus_engine → entropy risk / superlative suppression)

Verdict thresholds:
  90+  publish
  75-89 review
  60-74 quarantine
  <60   block
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

log = logging.getLogger("editorial_score")


@dataclass
class ScoreComponent:
    name: str
    weight: float
    score: float = 0.0
    details: str = ""

    @property
    def weighted(self) -> float:
        return self.score * self.weight


@dataclass
class EditorialScoreReport:
    keyword: str
    components: list[ScoreComponent] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def final_score(self) -> float:
        total_weight = sum(c.weight for c in self.components)
        if total_weight == 0:
            return 0.0
        return round(sum(c.weighted for c in self.components) / total_weight * 100, 1)

    @property
    def verdict(self) -> str:
        score = self.final_score
        if score >= 90:
            return "publish"
        elif score >= 75:
            return "review"
        elif score >= 60:
            return "quarantine"
        return "block"

    @property
    def verdict_icon(self) -> str:
        return {
            "publish": "✓",
            "review": "~",
            "quarantine": "!",
            "block": "✗",
        }.get(self.verdict, "?")

    def add(self, name: str, score: float, weight: float, details: str = ""):
        self.components.append(ScoreComponent(
            name=name, weight=weight, score=max(0.0, min(1.0, score)), details=details
        ))

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "timestamp": self.timestamp,
            "final_score": self.final_score,
            "verdict": self.verdict,
            "components": [
                {"name": c.name, "weight": c.weight, "score": c.score,
                 "weighted": round(c.weighted, 3), "details": c.details[:100]}
                for c in self.components
            ],
        }

    def summary(self) -> str:
        lines = [
            "╔══════════════════════════════════════════════════════════",
            f"║  EDITORIAL SCORE: {self.final_score}/100  [{self.verdict_icon} {self.verdict.upper()}]",
            "╠══════════════════════════════════════════════════════════",
        ]
        for c in self.components:
            bar = "█" * int(c.score * 20) + "░" * (20 - int(c.score * 20))
            lines.append(f"║  {c.name:20s} {bar} {c.score:.2f}  (w={c.weight:.2f})")
        lines.append("╚══════════════════════════════════════════════════════════")
        return "\n".join(lines)


class EditorialScorer:
    """Compute unified editorial score from all available signals."""

    def __init__(self):
        self._history: list[EditorialScoreReport] = []

    def compute(
        self,
        keyword: str,
        trust_risk_score: float | None = None,
        temporal_violations: list | None = None,
        coverage_result: dict | None = None,
        dag_report: dict | None = None,
        consensus_report: dict | None = None,
        superlative_report: dict | None = None,
        article: str | None = None,
    ) -> EditorialScoreReport:
        """Compute the full editorial score from available signals.

        Each signal is optional — missing signals default to neutral (0.5).
        """
        report = EditorialScoreReport(keyword=keyword)

        # 1. Trust score (0.30)
        trust_score = 0.5
        trust_details = "no trust signal available"
        if trust_risk_score is not None:
            trust_score = 1.0 - trust_risk_score  # invert: 0 risk = 1.0 score
            trust_details = f"trust_risk={trust_risk_score:.2f}"
        report.add("trust_score", trust_score, 0.30, trust_details)

        # 2. Freshness score (0.20)
        freshness_score = 0.5
        freshness_details = "no temporal signal available"
        if temporal_violations is not None:
            high = sum(1 for v in temporal_violations if v.get("severity") == "high")
            low = sum(1 for v in temporal_violations if v.get("severity") == "low")
            freshness_score = max(0.0, 1.0 - (high * 0.3 + low * 0.1))
            freshness_details = f"{high} high, {low} low violations"
        report.add("freshness_score", freshness_score, 0.20, freshness_details)

        # 3. Coverage score (0.20)
        coverage_score = 0.5
        coverage_details = "no coverage signal available"
        if coverage_result is not None:
            passed = coverage_result.get("passed", False)
            total = coverage_result.get("required_sections_total", 1)
            found = coverage_result.get("required_sections_found", 0)
            coverage_score = found / max(1, total)
            if passed:
                coverage_score = max(coverage_score, 0.8)
            coverage_details = f"{found}/{total} sections, passed={passed}"
        report.add("coverage_score", coverage_score, 0.20, coverage_details)

        # 4. Citation score (0.15)
        citation_score = 0.5
        citation_details = "no citation signal available"
        if dag_report is not None:
            total_claims = dag_report.get("total_claims", 0)
            supported = dag_report.get("supported_claims", 0)
            citation_score = supported / max(1, total_claims)
            citation_details = f"{supported}/{total_claims} claims supported"
        elif superlative_report is not None:
            total_sup = superlative_report.get("total_superlatives", 0)
            unsupported = superlative_report.get("unsupported", 0)
            citation_score = (total_sup - unsupported) / max(1, total_sup)
            citation_details = f"{total_sup - unsupported}/{total_sup} superlatives cited"
        report.add("citation_score", citation_score, 0.15, citation_details)

        # 5. Entropy score (0.15)
        entropy_score = 0.5
        entropy_details = "no entropy signal available"
        if consensus_report is not None:
            entropy_risk = consensus_report.get("entropy_risk", "")
            if entropy_risk == "low":
                entropy_score = 0.9
            elif entropy_risk == "medium":
                entropy_score = 0.6
            elif entropy_risk == "high":
                entropy_score = 0.3
            entropy_details = f"entropy_risk={entropy_risk}"
        report.add("entropy_score", entropy_score, 0.15, entropy_details)

        self._history.append(report)
        return report

    def get_history(self, limit: int = 10) -> list[dict]:
        return [r.to_dict() for r in self._history[-limit:]]


# Singleton
_SCORER = EditorialScorer()


def compute_editorial_score(
    keyword: str,
    **signals,
) -> EditorialScoreReport:
    return _SCORER.compute(keyword, **signals)


def get_scorer() -> EditorialScorer:
    return _SCORER
