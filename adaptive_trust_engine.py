"""
adaptive_trust_engine.py — Probabilistic Governance Layer
==========================================================
Replaces hard if/else rules with weighted risk scoring:

  publish_risk = Σ(factor_weight × factor_score)

Factors drawn from ALL existing subsystems:
  • Evidence DAG (contradictions, claim confidence)
  • Consensus Engine (entropy, critique, rejections)
  • Truth Infrastructure (repairs, hallucinations, freshness)
  • Enterprise Guardian (existing block reasons)

Learns per-niche weights from historical outcomes.
"""

from __future__ import annotations

import json
import time
import logging
import re
from typing import Any, Optional
from dataclasses import dataclass, field

log = logging.getLogger("adaptive_trust")


# ── TrustFactor ───────────────────────────────────────────

@dataclass
class TrustFactor:
    """A single factor contributing to publish risk."""
    name: str
    weight: float      # 0.0 to 1.0 — importance of this factor
    score: float       # 0.0 (safe) to 1.0 (risky)
    evidence: str      # human-readable explanation

    def weighted(self) -> float:
        return self.weight * self.score


# ── PublishRiskReport ─────────────────────────────────────

@dataclass
class PublishRiskReport:
    """Final verdict with full factor breakdown."""
    risk_score: float        # 0.0 (safe) to 1.0 (block)
    verdict: str             # "publish" / "review" / "quarantine" / "block"
    factors: list[TrustFactor] = field(default_factory=list)
    niche: str = "default"
    keyword: str = ""
    recommendations: list[str] = field(default_factory=list)
    computed_at: float = 0.0

    def __post_init__(self):
        self.computed_at = time.time()

    def to_dict(self) -> dict:
        return {
            "risk_score": self.risk_score,
            "verdict": self.verdict,
            "niche": self.niche,
            "keyword": self.keyword,
            "factors": [
                {"name": f.name, "weight": f.weight, "score": f.score,
                 "weighted": round(f.weighted(), 3), "evidence": f.evidence}
                for f in self.factors
            ],
            "recommendations": self.recommendations,
            "computed_at": self.computed_at,
        }

    def summary(self) -> str:
        lines = [f"Publish Risk: {self.risk_score:.2f} → {self.verdict.upper()}"]
        lines.append(f"  Niche: {self.niche}  Keyword: {self.keyword}")
        lines.append("  Factors:")
        for f in sorted(self.factors, key=lambda x: x.weighted(), reverse=True):
            bar = "█" * int(f.weighted() * 20)
            lines.append(f"    {f.name:25s} {f.weighted():.3f}  {bar}")
            lines.append(f"    {'':25s} {f.evidence}")
        if self.recommendations:
            lines.append("  Recommendations:")
            for r in self.recommendations:
                lines.append(f"    • {r}")
        return "\n".join(lines)


# ── AdaptiveWeights ───────────────────────────────────────

class AdaptiveWeights:
    """Per-niche weight profiles learned from historical outcomes.

    Each niche has a weight vector. The `learn()` method adjusts
    weights based on which factors correctly predicted outcomes.
    """

    BASE_WEIGHTS: dict[str, float] = {
        "contradictions": 0.25,
        "entropy_risk": 0.15,
        "hallucination_rate": 0.20,
        "freshness_decay": 0.10,
        "source_trust": 0.10,
        "repair_failures": 0.10,
        "critique_critical": 0.10,
    }

    # Niche-specific adjustments (learned over time)
    NICHE_BIAS: dict[str, dict[str, float]] = {
        "health": {"hallucination_rate": 0.30, "source_trust": 0.20},
        "finance": {"contradictions": 0.35, "freshness_decay": 0.15},
        "legal": {"source_trust": 0.30, "critique_critical": 0.20},
        "technology": {"freshness_decay": 0.20, "entropy_risk": 0.20},
    }

    def __init__(self):
        self._history: list[dict] = []  # (niche, factor_scores, outcome)

    def get_weights(self, niche: str = "default") -> dict[str, float]:
        """Get weight vector for a niche, merged with base."""
        weights = dict(self.BASE_WEIGHTS)
        niche_bias = self.NICHE_BIAS.get(niche, {})
        for k, v in niche_bias.items():
            if k in weights:
                weights[k] = min(1.0, weights[k] + (v - weights[k]) * 0.5)
        return weights

    def learn(
        self,
        niche: str,
        factor_scores: dict[str, float],
        was_blocked: bool,
        outcome_score: float,
    ) -> None:
        """Record an outcome and adjust niche weights.

        Factors that correlated with correct predictions get
        slightly boosted; factors that were wrong get penalized.
        """
        self._history.append({
            "niche": niche,
            "factor_scores": dict(factor_scores),
            "was_blocked": was_blocked,
            "outcome_score": outcome_score,
            "timestamp": time.time(),
        })

        # Simple learning: if blocked, boost weights of high-scoring factors
        if was_blocked and niche not in self.NICHE_BIAS:
            self.NICHE_BIAS[niche] = {}

        if was_blocked and niche in self.NICHE_BIAS:
            bias = self.NICHE_BIAS[niche]
            for factor, score in factor_scores.items():
                if score > 0.6:  # factor was correctly high-risk
                    bias[factor] = bias.get(factor, 0.0) + 0.02
                elif score < 0.3:  # factor was low but outcome was block
                    bias[factor] = bias.get(factor, 0.0) - 0.01

    def get_history(self, niche: Optional[str] = None) -> list[dict]:
        if niche:
            return [h for h in self._history if h["niche"] == niche]
        return list(self._history)


# ── Niche Detector ────────────────────────────────────────

_NICHE_KEYWORDS: dict[str, list[str]] = {
    "health": ["health", "medical", "symptom", "treatment", "disease",
               "diagnosis", "therapy", "patient", "doctor", "clinical"],
    "finance": ["finance", "invest", "stock", "money", "bank", "loan",
                "mortgage", "credit", "tax", "insurance", "retirement"],
    "legal": ["legal", "law", "attorney", "lawsuit", "contract",
              "compliance", "regulation", "court", "legal advice"],
    "technology": ["technology", "software", "hardware", "app", "digital",
                   "tech", "programming", "algorithm", "data", "cloud"],
    "ecommerce": ["buy", "best", "review", "price", "cheap", "deal",
                  "discount", "shop", "product", "top-rated"],
}


def _detect_niche(keyword: str) -> str:
    lower = keyword.lower()
    for niche, kws in _NICHE_KEYWORDS.items():
        for kw in kws:
            if kw in lower:
                return niche
    return "default"


# ── AdaptiveTrustEngine ───────────────────────────────────

class AdaptiveTrustEngine:
    """Probabilistic governance engine.

    Collects signals from all subsystems, computes weighted
    publish risk, and produces actionable recommendations.
    """

    # Thresholds for verdicts
    THRESHOLD_PUBLISH = 0.40
    THRESHOLD_REVIEW = 0.65
    THRESHOLD_QUARANTINE = 0.80

    def __init__(self):
        self.weights = AdaptiveWeights()
        self._evaluation_count = 0

    def evaluate(
        self,
        article: str,
        keyword: str,
        niche: Optional[str] = None,
        dag=None,          # pre-built EvidenceDAG (optional)
        consensus=None,    # pre-built consensus report (optional)
    ) -> PublishRiskReport:
        """Compute publish risk from ALL available signals."""
        self._evaluation_count += 1
        niche = niche or _detect_niche(keyword)
        weight_map = self.weights.get_weights(niche)
        factors: list[TrustFactor] = []
        recommendations: list[str] = []

        # ── Factor 1: Contradictions (from DAG) ──
        _contra_factor = self._eval_contradictions(article, dag)
        if _contra_factor:
            factors.append(_contra_factor)

        # ── Factor 2: Entropy risk (from consensus) ──
        _entropy_factor = self._eval_entropy(article, consensus)
        if _entropy_factor:
            factors.append(_entropy_factor)

        # ── Factor 3: Hallucination rate (from truth store) ──
        _hallu_factor = self._eval_hallucinations(keyword)
        if _hallu_factor:
            factors.append(_hallu_factor)

        # ── Factor 4: Freshness decay (from truth store) ──
        _fresh_factor = self._eval_freshness(keyword)
        if _fresh_factor:
            factors.append(_fresh_factor)

        # ── Factor 5: Source trust (from truth store citations) ──
        _source_factor = self._eval_source_trust(keyword)
        if _source_factor:
            factors.append(_source_factor)

        # ── Factor 6: Repair failures (from truth store) ──
        _repair_factor = self._eval_repairs(keyword)
        if _repair_factor:
            factors.append(_repair_factor)

        # ── Factor 7: Critique critical issues (from consensus) ──
        _critique_factor = self._eval_critique(article, consensus)
        if _critique_factor:
            factors.append(_critique_factor)

        # ── Compute weighted risk ──
        total_weight = sum(weight_map.get(f.name, 0.5) for f in factors) or 1.0
        risk_score = sum(
            weight_map.get(f.name, 0.5) * f.score for f in factors
        ) / total_weight
        risk_score = max(0.0, min(1.0, risk_score))

        # ── Assign weights to factors ──
        for f in factors:
            f.weight = weight_map.get(f.name, 0.5)

        # ── Verdict ──
        if risk_score < self.THRESHOLD_PUBLISH:
            verdict = "publish"
        elif risk_score < self.THRESHOLD_REVIEW:
            verdict = "review"
            recommendations.append("Manual review recommended before publishing.")
        elif risk_score < self.THRESHOLD_QUARANTINE:
            verdict = "quarantine"
            recommendations.append("Quarantine: moderate-to-high publish risk detected.")
        else:
            verdict = "block"
            recommendations.append("BLOCKED: publish risk exceeds safety threshold.")

        # ── Dynamic recommendations ──
        for f in factors:
            if f.score > 0.6 and f.weighted() > 0.05:
                recommendations.append(
                    f"Address '{f.name}' (score={f.score:.2f}) before publishing."
                )

        return PublishRiskReport(
            risk_score=risk_score,
            verdict=verdict,
            factors=factors,
            niche=niche,
            keyword=keyword,
            recommendations=recommendations,
        )

    def learn(
        self,
        keyword: str,
        risk_report: PublishRiskReport,
        was_blocked: bool,
        outcome_score: float = 0.0,
    ) -> None:
        """Learn from an evaluation outcome to adapt future weights."""
        factor_scores = {f.name: f.score for f in risk_report.factors}
        self.weights.learn(
            niche=risk_report.niche,
            factor_scores=factor_scores,
            was_blocked=was_blocked,
            outcome_score=outcome_score,
        )

    def get_stats(self) -> dict:
        return {
            "evaluations": self._evaluation_count,
            "learned_outcomes": len(self.weights._history),
            "active_niches": list(self.weights.NICHE_BIAS.keys()),
        }

    # ── Per-factor evaluation methods ──

    def _eval_contradictions(self, article: str, dag) -> Optional[TrustFactor]:
        try:
            if dag is not None and dag.claim_count() > 0:
                contra = sum(1 for n in dag.nodes.values() if n.contradicted_by)
                score = min(1.0, contra / max(1, dag.claim_count()) * 3)
                return TrustFactor(
                    name="contradictions",
                    weight=0.0,  # assigned later
                    score=score,
                    evidence=f"{contra}/{dag.claim_count()} claims contradicted",
                )
        except Exception:
            pass
        return None

    def _eval_entropy(self, article: str, consensus) -> Optional[TrustFactor]:
        if consensus and consensus.get("entropy_risk") == "high":
            return TrustFactor(
                name="entropy_risk",
                weight=0.0,
                score=0.7,
                evidence="High AI detection risk from entropy analysis",
            )
        # Fallback: rough estimate from article
        sentences = re.split(r"[.!?]+", article)
        long_enough = [s for s in sentences if len(s.strip().split()) > 5]
        if long_enough:
            starts = set()
            for s in long_enough[:20]:
                words = s.strip().split()
                if words:
                    starts.add(words[0].lower())
            variety = len(starts) / max(1, len(long_enough[:20]))
            if variety < 0.3:
                return TrustFactor(
                    name="entropy_risk",
                    weight=0.0,
                    score=0.6,
                    evidence=f"Low sentence start variety ({variety:.2f})",
                )
        return None

    def _eval_hallucinations(self, keyword: str) -> Optional[TrustFactor]:
        try:
            from truth_infrastructure import get_truth_store
            store = get_truth_store()
            signals = store.hallucinations.get_all()
            kw_signals = [s for s in signals if s.keyword == keyword]
            if kw_signals:
                rate = len(kw_signals) / max(1, len(signals))
                return TrustFactor(
                    name="hallucination_rate",
                    weight=0.0,
                    score=min(1.0, rate * 2),
                    evidence=f"{len(kw_signals)} hallucination signals for this keyword",
                )
        except Exception:
            pass
        return None

    def _eval_freshness(self, keyword: str) -> Optional[TrustFactor]:
        try:
            from truth_infrastructure import get_truth_store
            store = get_truth_store()
            cites = store.load_citations(keyword=keyword)
            if cites:
                avg_fresh = sum(c.freshness_score for c in cites) / len(cites)
                score = 1.0 - avg_fresh  # low freshness = high risk
                return TrustFactor(
                    name="freshness_decay",
                    weight=0.0,
                    score=score,
                    evidence=f"Avg freshness {avg_fresh:.2f} across {len(cites)} citations",
                )
        except Exception:
            pass
        return None

    def _eval_source_trust(self, keyword: str) -> Optional[TrustFactor]:
        try:
            from truth_infrastructure import get_truth_store, FreshnessScorer
            store = get_truth_store()
            cites = store.load_citations(keyword=keyword)
            if cites:
                low_trust = sum(1 for c in cites if c.freshness_score < 0.4)
                score = low_trust / len(cites)
                return TrustFactor(
                    name="source_trust",
                    weight=0.0,
                    score=score,
                    evidence=f"{low_trust}/{len(cites)} low-trust citations",
                )
        except Exception:
            pass
        return None

    def _eval_repairs(self, keyword: str) -> Optional[TrustFactor]:
        try:
            from truth_infrastructure import get_truth_store
            store = get_truth_store()
            kw_repairs = store.repairs.get_by_keyword(keyword)
            if kw_repairs:
                failures = sum(1 for r in kw_repairs if not r.repair_success)
                score = failures / max(1, len(kw_repairs))
                return TrustFactor(
                    name="repair_failures",
                    weight=0.0,
                    score=score,
                    evidence=f"{failures}/{len(kw_repairs)} failed repairs",
                )
        except Exception:
            pass
        return None

    def _eval_critique(self, article: str, consensus) -> Optional[TrustFactor]:
        if consensus and consensus.get("critical_issues"):
            n = len(consensus["critical_issues"])
            return TrustFactor(
                name="critique_critical",
                weight=0.0,
                score=min(1.0, n * 0.3),
                evidence=f"{n} critical issues from consensus critique",
            )
        # Fallback: check for missing H1
        if not re.search(r"<h1[^>]*>", article, re.I):
            return TrustFactor(
                name="critique_critical",
                weight=0.0,
                score=0.5,
                evidence="Missing H1 heading",
            )
        return None


# ── Global Singleton ──────────────────────────────────────

_ENGINE: Optional[AdaptiveTrustEngine] = None


def get_trust_engine() -> AdaptiveTrustEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = AdaptiveTrustEngine()
    return _ENGINE


def reset_trust_engine() -> None:
    global _ENGINE
    _ENGINE = None


def evaluate_publish_risk(
    article: str,
    keyword: str,
    niche: Optional[str] = None,
    dag=None,
    consensus=None,
) -> PublishRiskReport:
    """Quick-access: evaluate publish risk for an article."""
    engine = get_trust_engine()
    return engine.evaluate(article, keyword, niche, dag, consensus)
