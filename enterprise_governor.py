"""
enterprise_governor.py — Central Enterprise Governance & Orchestration
=======================================================================
Final publish decision authority. Coordinates all subsystems:
  Generation → Consensus → DAG → Truth → Temporal → Adversarial Swarm
  → Adaptive Trust → Repair Orchestrator → Temporal Governor → PUBLISH

Responsibilities:
  - Central orchestration of the full pipeline
  - Publish decisions with confidence budgeting
  - Quarantine routing
  - Event-driven coordination
  - Failure escalation
  - Trust score enforcement
  - Policy enforcement
"""

from __future__ import annotations

import re
import json
import time
import logging
from typing import Any, Optional
from dataclasses import dataclass, field

log = logging.getLogger("enterprise_governor")


# ── Exceptions ──────────────────────────────────────────

class PublishBlocked(Exception):
    """Raised when the article is blocked from publishing."""
    def __init__(self, reason: str, source: str = "enterprise_governor"):
        self.reason = reason
        self.source = source
        super().__init__(f"PUBLISH_BLOCKED [{source}]: {reason}")


class PublishQuarantined(Exception):
    """Raised when the article is quarantined for manual review."""
    def __init__(self, reason: str, source: str = "enterprise_governor"):
        self.reason = reason
        self.source = source
        super().__init__(f"PUBLISH_QUARANTINED [{source}]: {reason}")


# ── Governance Data Classes ─────────────────────────────

@dataclass
class GovernanceDecision:
    """Final publish decision with full audit trail."""
    keyword: str
    verdict: str           # publish / review / quarantine / block
    confidence_budget: float  # 0.0 to 1.0
    risk_score: float      # aggregate risk
    factors: list[dict] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    quarantine_path: str = ""
    escalation_path: list[str] = field(default_factory=list)
    subsystem_reports: dict = field(default_factory=dict)
    decided_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "verdict": self.verdict,
            "confidence_budget": self.confidence_budget,
            "risk_score": self.risk_score,
            "factors": list(self.factors),
            "recommendations": list(self.recommendations),
            "quarantine_path": self.quarantine_path,
            "escalation_path": self.escalation_path,
            "subsystem_reports": dict(self.subsystem_reports),
            "decided_at": self.decided_at or time.time(),
        }

    def summary(self) -> str:
        lines = [
            f"Enterprise Governor: {self.verdict.upper()}",
            f"  Keyword: {self.keyword}",
            f"  Risk:    {self.risk_score:.2f}",
            f"  Budget:  {self.confidence_budget:.2f}",
        ]
        if self.factors:
            lines.append("  Factors:")
            for f in self.factors:
                lines.append(f"    • {f.get('name', '?')}: {f.get('score', 0)}")
        if self.recommendations:
            lines.append("  Actions:")
            for r in self.recommendations:
                lines.append(f"    → {r}")
        return "\n".join(lines)


# ── Confidence Budget ───────────────────────────────────

class ConfidenceBudget:
    """Tracks and enforces a confidence budget across articles.

    Each article draws from the budget based on risk score.
    High-risk articles consume more budget.
    """

    def __init__(self, max_budget: float = 100.0, reset_interval: float = 86400.0):
        self.max_budget = max_budget
        self.reset_interval = reset_interval
        self._consumed: float = 0.0
        self._last_reset: float = time.time()
        self._history: list[dict] = []

    @property
    def remaining(self) -> float:
        self._check_reset()
        return max(0.0, self.max_budget - self._consumed)

    def can_publish(self, risk_score: float) -> bool:
        """Check if the budget allows publishing an article with this risk."""
        cost = self._calculate_cost(risk_score)
        return self.remaining >= cost

    def consume(self, keyword: str, risk_score: float, verdict: str) -> float:
        """Consume budget for an article. Returns cost."""
        self._check_reset()
        cost = self._calculate_cost(risk_score)
        self._consumed += cost
        self._history.append({
            "keyword": keyword,
            "risk_score": risk_score,
            "verdict": verdict,
            "cost": cost,
            "remaining_after": self.remaining,
            "timestamp": time.time(),
        })
        return cost

    def _calculate_cost(self, risk_score: float) -> float:
        return risk_score * 20.0

    def _check_reset(self) -> None:
        if time.time() - self._last_reset > self.reset_interval:
            self._consumed = 0.0
            self._last_reset = time.time()

    def get_stats(self) -> dict:
        return {
            "max_budget": self.max_budget,
            "consumed": self._consumed,
            "remaining": self.remaining,
            "usage_pct": round(self._consumed / max(1, self.max_budget) * 100, 1),
            "total_decisions": len(self._history),
        }


# ── PolicyEngine ────────────────────────────────────────

class PolicyEngine:
    """Enforces configurable policies on publish decisions."""

    def __init__(self):
        self.policies: list[dict] = [
            {"name": "max_risk_block", "threshold": 0.80, "action": "block",
             "description": "Block articles exceeding maximum risk threshold"},
            {"name": "max_risk_quarantine", "threshold": 0.55, "action": "quarantine",
             "description": "Quarantine articles with moderate-to-high risk"},
            {"name": "min_confidence", "threshold": 0.40, "action": "review",
             "description": "Review articles below minimum confidence"},
        ]

    def enforce(self, risk_score: float, confidence: float) -> list[dict]:
        """Check all policies against the given scores. Returns violations."""
        violations = []
        for policy in self.policies:
            name = policy["name"]
            if name == "max_risk_block" and risk_score >= policy["threshold"]:
                violations.append({
                    "policy": name,
                    "action": policy["action"],
                    "reason": policy["description"],
                    "value": risk_score,
                    "threshold": policy["threshold"],
                })
            elif name == "max_risk_quarantine" and risk_score >= policy["threshold"]:
                violations.append({
                    "policy": name,
                    "action": policy["action"],
                    "reason": policy["description"],
                    "value": risk_score,
                    "threshold": policy["threshold"],
                })
            elif name == "min_confidence" and confidence < policy["threshold"]:
                violations.append({
                    "policy": name,
                    "action": policy["action"],
                    "reason": policy["description"],
                    "value": confidence,
                    "threshold": policy["threshold"],
                })
        return violations


# ── EnterpriseGovernor ──────────────────────────────────

class EnterpriseGovernor:
    """Central governance authority for the entire pipeline.

    Orchestrates all subsystems and makes final publish decisions.
    """

    def __init__(self):
        self.policy_engine = PolicyEngine()
        self.confidence_budget = ConfidenceBudget()
        self._decision_history: list[GovernanceDecision] = []

    def evaluate(
        self,
        keyword: str,
        article: str = "",
        # Optional pre-computed reports from subsystems
        consensus_report: Optional[dict] = None,
        dag_report: Optional[dict] = None,
        truth_report: Optional[dict] = None,
        trust_report: Optional[dict] = None,
        temporal_report: Optional[dict] = None,
        swarm_report: Optional[dict] = None,
        repair_memory: Optional[dict] = None,
        governor_report: Optional[dict] = None,
        site_graph: Optional[dict] = None,
        # Direct scores (used when report objects not available)
        risk_score: Optional[float] = None,
        confidence: Optional[float] = None,
        # Orchestration control
        run_full_pipeline: bool = False,
        **kwargs,
    ) -> GovernanceDecision:
        """Evaluate all signals and make a publish decision."""
        start = time.time()
        factors = []
        recommendations = []
        escalation = []
        subsystem_reports = {}

        # ── 1. Collect risk scores from all subsystems ──
        risk_scores = []
        confidence_scores = []

        # Adaptive Trust
        trust_risk = None
        if trust_report:
            trust_risk = trust_report.get("risk_score", 0.5)
            trust_verdict = trust_report.get("verdict", "unknown")
            risk_scores.append(trust_risk)
            factors.append({"name": "adaptive_trust", "score": trust_risk,
                            "verdict": trust_verdict,
                            "source": "adaptive_trust_engine"})
            subsystem_reports["trust"] = trust_report

        # Adversarial Swarm
        swarm_risk = None
        if swarm_report:
            swarm_risk = swarm_report.get("weighted_risk_score", 0.5)
            swarm_verdict = swarm_report.get("consensus_verdict", "pass")
            risk_scores.append(swarm_risk)
            factors.append({"name": "adversarial_swarm", "score": swarm_risk,
                            "verdict": swarm_verdict,
                            "source": "adversarial_swarm"})
            if swarm_report.get("quarantine_recommended"):
                recommendations.append("Adversarial swarm recommends quarantine")
            if swarm_report.get("human_review_recommended"):
                recommendations.append("Adversarial swarm recommends human review")
            subsystem_reports["swarm"] = swarm_report

        # Temporal Governor
        governor_risk = None
        if governor_report:
            freshness = governor_report.get("overall_freshness", 0.5)
            governor_risk = 1.0 - freshness
            sla_status = governor_report.get("sla_status", "compliant")
            risk_scores.append(governor_risk)
            factors.append({"name": "temporal_governor", "score": governor_risk,
                            "sla": sla_status,
                            "source": "temporal_governor"})
            if governor_report.get("quarantine_recommended"):
                recommendations.append("Temporal governor recommends quarantine (stale content)")
            if governor_report.get("expired_claims"):
                recommendations.append(
                    f"Resolve {len(governor_report.get('expired_claims', []))} expired claims"
                )
            subsystem_reports["governor"] = governor_report

        # Temporal Intelligence
        temporal_risk = None
        if temporal_report:
            temporal_risk = 1.0 - temporal_report.get("effective_confidence", 0.5)
            risk_scores.append(temporal_risk)
            factors.append({"name": "temporal_intelligence", "score": temporal_risk,
                            "source": "temporal_intelligence"})
            subsystem_reports["temporal"] = temporal_report

        # Evidence DAG
        dag_risk = None
        if dag_report:
            contra = dag_report.get("contradictions", 0)
            claim_count = dag_report.get("claim_count", 1)
            dag_risk = min(1.0, contra / max(1, claim_count) * 3)
            risk_scores.append(dag_risk)
            factors.append({"name": "evidence_dag", "score": dag_risk,
                            "contradictions": contra,
                            "source": "evidence_dag"})
            subsystem_reports["dag"] = dag_report

        # Consensus
        consensus_risk = None
        if consensus_report:
            rejected = consensus_report.get("claims_rejected", 0)
            total = consensus_report.get("claims_scored", 1)
            critical = len(consensus_report.get("critical_issues", []))
            consensus_risk = min(1.0, (rejected / max(1, total)) + critical * 0.2)
            risk_scores.append(consensus_risk)
            factors.append({"name": "consensus_engine", "score": consensus_risk,
                            "rejected": rejected, "critical": critical,
                            "source": "generation_consensus_engine"})
            subsystem_reports["consensus"] = consensus_report

        # Truth Infrastructure
        truth_risk = None
        if truth_report:
            hallu_count = truth_report.get("hallucinations", {}).get("total_signals", 0)
            repair_failures = truth_report.get("repairs", {}).get("failed_repairs", 0)
            truth_risk = min(1.0, (hallu_count * 0.1 + repair_failures * 0.2))
            risk_scores.append(truth_risk)
            factors.append({"name": "truth_infrastructure", "score": truth_risk,
                            "hallucinations": hallu_count,
                            "repair_failures": repair_failures,
                            "source": "truth_infrastructure"})
            subsystem_reports["truth"] = truth_report

        # Site Intelligence
        site_risk = None
        if site_graph:
            orphan_count = len(site_graph.get("orphan_pages", []))
            site_risk = min(0.5, orphan_count * 0.05)
            risk_scores.append(site_risk)
            factors.append({"name": "site_intelligence", "score": site_risk,
                            "orphans": orphan_count,
                            "source": "site_intelligence_graph"})
            subsystem_reports["site_graph"] = site_graph

        # Repair Memory
        repair_risk = None
        if repair_memory:
            if repair_memory.get("escalated"):
                repair_risk = 0.8
                escalation.append(f"Repair escalation: {repair_memory.get('escalation_reason', '')}")
                recommendations.append("Article was escalated from repair loop — review required")
            else:
                repair_risk = 0.0
            if repair_memory.get("outcomes"):
                outcomes = repair_memory["outcomes"]
                if any(o.get("mutated") for o in outcomes):
                    repair_risk = max(repair_risk or 0, 0.3)
            if repair_risk is not None:
                risk_scores.append(repair_risk)
                factors.append({"name": "repair_orchestrator", "score": repair_risk,
                                "source": "autonomous_repair_orchestrator"})
            subsystem_reports["repair"] = repair_memory

        # Use direct scores if provided
        if risk_score is not None:
            risk_scores.append(risk_score)
        if confidence is not None:
            confidence_scores.append(confidence)

        # ── 2. Compute aggregate risk ──
        if risk_scores:
            aggregate_risk = sum(risk_scores) / len(risk_scores)
        else:
            aggregate_risk = 0.5

        aggregate_risk = max(0.0, min(1.0, aggregate_risk))

        # ── 3. Compute confidence budget ──
        avg_confidence = sum(confidence_scores) / max(1, len(confidence_scores)) if confidence_scores else 0.5

        # ── 4. Policy enforcement ──
        policy_violations = self.policy_engine.enforce(aggregate_risk, avg_confidence)

        # ── 5. Budget check ──
        if not self.confidence_budget.can_publish(aggregate_risk):
            policy_violations.append({
                "policy": "confidence_budget",
                "action": "block",
                "reason": f"Confidence budget exhausted (remaining: {self.confidence_budget.remaining:.1f})",
                "value": aggregate_risk,
                "threshold": 0.0,
            })

        # ── 6. Determine verdict ──
        block_violations = [v for v in policy_violations if v["action"] == "block"]
        quarantine_violations = [v for v in policy_violations if v["action"] == "quarantine"]
        review_violations = [v for v in policy_violations if v["action"] == "review"]

        if block_violations:
            verdict = "block"
            for v in block_violations:
                recommendations.append(f"BLOCKED: {v['reason']}")
                escalation.append(f"Policy violation: {v['policy']}")
        elif quarantine_violations or aggregate_risk >= 0.65:
            verdict = "quarantine"
            recommendations.append("Quarantined for manual editorial review")
        elif review_violations or aggregate_risk >= 0.40:
            verdict = "review"
            recommendations.append("Review recommended before publishing")
        else:
            verdict = "publish"
            recommendations.append("Approved for publishing")

        # Check swarm-specific verdicts
        if swarm_report and swarm_report.get("consensus_verdict") == "block":
            verdict = "block"
            recommendations.append("BLOCKED by adversarial swarm consensus")

        # ── 7. Consume budget ──
        self.confidence_budget.consume(keyword, aggregate_risk, verdict)

        decision = GovernanceDecision(
            keyword=keyword,
            verdict=verdict,
            confidence_budget=avg_confidence,
            risk_score=aggregate_risk,
            factors=factors,
            recommendations=recommendations[:10],
            escalation_path=escalation,
            subsystem_reports=subsystem_reports,
            decided_at=time.time(),
        )

        self._decision_history.append(decision)

        # Emit event
        try:
            from event_bus import emit as _emit
            _emit("pipeline.governance", {
                "keyword": keyword,
                "verdict": verdict,
                "risk_score": aggregate_risk,
                "factors": [f["name"] for f in factors],
                "duration_ms": round((time.time() - start) * 1000, 1),
            }, source="enterprise_governor")
        except ImportError:
            pass

        return decision

    def get_history(self, keyword: Optional[str] = None, limit: int = 50) -> list[GovernanceDecision]:
        if keyword:
            return [d for d in self._decision_history if d.keyword == keyword][:limit]
        return self._decision_history[-limit:]

    def get_stats(self) -> dict:
        total = len(self._decision_history)
        verdicts = {}
        for d in self._decision_history:
            verdicts[d.verdict] = verdicts.get(d.verdict, 0) + 1
        return {
            "total_decisions": total,
            "verdicts": verdicts,
            "budget": self.confidence_budget.get_stats(),
        }


# ── Global Singleton ─────────────────────────────────────

_GOVERNOR: Optional[EnterpriseGovernor] = None


def get_governor() -> EnterpriseGovernor:
    global _GOVERNOR
    if _GOVERNOR is None:
        _GOVERNOR = EnterpriseGovernor()
    return _GOVERNOR


def reset_governor() -> None:
    global _GOVERNOR
    _GOVERNOR = None


def evaluate_publish(
    keyword: str,
    article: str = "",
    trust_report: Optional[dict] = None,
    swarm_report: Optional[dict] = None,
    temporal_report: Optional[dict] = None,
    governor_report: Optional[dict] = None,
    consensus_report: Optional[dict] = None,
    dag_report: Optional[dict] = None,
    **kwargs,
) -> GovernanceDecision:
    """Quick-access: evaluate publish decision."""
    gov = get_governor()
    return gov.evaluate(
        keyword=keyword,
        article=article,
        trust_report=trust_report,
        swarm_report=swarm_report,
        temporal_report=temporal_report,
        governor_report=governor_report,
        consensus_report=consensus_report,
        dag_report=dag_report,
        **kwargs,
    )
