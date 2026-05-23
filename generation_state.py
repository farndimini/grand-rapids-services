"""generation_state.py — Unified State Object for Entire Pipeline

Carries ALL pipeline data in one object: evidence, temporal, consensus,
DAG, truth, trust, editorial score, benchmarks, governance.

Supports:
  - save() / load() for replay and debugging
  - summary() for CLI output
  - to_dict() for serialization
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("gen_state")

REPLAY_DIR = Path(__file__).resolve().parent / "replay_store"


class GenerationState:
    """Unified state object for the entire generation pipeline."""

    def __init__(self, keyword: str, model: str = "default"):
        # ── Identity ──
        self.keyword = keyword
        self.model = model
        self.niche: str = "default"
        self.intent: str = "informational"
        self.created_at = time.time()
        self.state_id: str = f"{keyword.replace(' ', '_')}_{int(self.created_at)}"

        # ── Article ──
        self.article: str = ""
        self.word_count: int = 0
        self.strategy: dict = {}

        # ── Evidence Pack ──
        self.evidence_pack: dict = {}
        self.evidence_block: str = ""
        self.evidence_entity_count: int = 0
        self.competitors_analyzed: int = 0

        # ── Temporal Grounding ──
        self.temporal_constraint_block: str = ""
        self.temporal_violations: list[dict] = []
        self.temporal_violations_high: int = 0
        self.temporal_compliant: bool = True

        # ── Coverage Validator ──
        self.coverage_result: dict = {}
        self.coverage_auto_fixed: bool = False
        self.coverage_sections_before: int = 0
        self.coverage_sections_after: int = 0

        # ── Superlative Suppressor ──
        self.superlative_report: dict = {}
        self.superlatives_suppressed: int = 0
        self.superlatives_total: int = 0

        # ── Consensus ──
        self.consensus_report: dict = {}
        self.critique_issues: list[dict] = []
        self.claims_approved: int = 0
        self.claims_rejected: int = 0
        self.entropy_risk: str = "unknown"

        # ── Evidence DAG ──
        self.dag_claim_count: int = 0
        self.dag_edge_count: int = 0
        self.dag_acyclic: bool = True
        self.contradiction_count: int = 0
        self.contradictions: list[dict] = []

        # ── Truth Infrastructure ──
        self.truth_node_count: int = 0
        self.citation_count: int = 0
        self.hallucination_signals: list[dict] = []
        self.repair_history: list[dict] = []

        # ── Adaptive Trust ──
        self.trust_risk_score: float = 0.0
        self.trust_verdict: str = "unknown"
        self.trust_factors: list[dict] = []

        # ── Editorial Score ──
        self.editorial_score: float = 0.0
        self.editorial_verdict: str = "unknown"
        self.editorial_components: list[dict] = []

        # ── Benchmark Arena ──
        self.benchmark_results: dict = {}
        self.benchmark_overall: float = 0.0

        # ── Temporal Intelligence ──
        self.temporal_claims: list[dict] = []
        self.effective_confidence: float = 0.0
        self.freshness_score: float = 1.0
        self.decayed_claims: list[dict] = []
        self.expired_citations: list[dict] = []

        # ── Site Intelligence ──
        self.related_articles: list[str] = []
        self.entity_consistency_score: float = 1.0
        self.topical_authority: float = 0.0

        # ── Adversarial Swarm ──
        self.swarm_report: dict = {}
        self.swarm_risk_score: float = 0.0
        self.swarm_verdict: str = "pass"

        # ── Temporal Governor ──
        self.governor_report: dict = {}
        self.governor_freshness: float = 1.0
        self.governor_sla_status: str = "compliant"
        self.governor_expired_claims: list[dict] = []

        # ── Repair Orchestrator ──
        self.repair_orchestrator_report: dict = {}
        self.repair_escalated: bool = False
        self.repair_root_cause: str = ""

        # ── Enterprise Governor ──
        self.governance_decision: dict = {}
        self.governance_verdict: str = "unknown"
        self.confidence_budget_remaining: float = 100.0

        # ── Governance ──
        self.publish_blocked: bool = False
        self.block_reason: str = ""
        self.repair_attempts: int = 0
        self.max_repairs: int = 2
        self.quarantine_path: str = ""

        # ── Events ──
        self.events: list[dict] = []

        # ── Timing ──
        self.stage_timings: dict[str, float] = {}

    # ── Timestamps ──

    def mark_stage(self, stage: str) -> None:
        self.stage_timings[stage] = time.time()

    def duration_since(self, stage: str) -> float:
        start = self.stage_timings.get(stage, self.created_at)
        return (time.time() - start) * 1000

    @property
    def total_duration_ms(self) -> float:
        if not self.stage_timings:
            return 0.0
        first = min(self.stage_timings.values())
        last = max(self.stage_timings.values())
        return (last - first) * 1000

    # ── Events ──

    def add_event(self, event_type: str, payload: Optional[dict] = None) -> None:
        self.events.append({
            "type": event_type,
            "payload": payload or {},
            "timestamp": time.time(),
        })
        try:
            from event_bus import emit as _emit
            _emit(event_type, payload, source="generation_state")
        except ImportError:
            pass

    # ── Serialization ──

    def to_dict(self) -> dict:
        return {
            "state_id": self.state_id,
            "keyword": self.keyword,
            "model": self.model,
            "niche": self.niche,
            "intent": self.intent,
            "created_at": self.created_at,
            "word_count": self.word_count,
            "evidence": {
                "entity_count": self.evidence_entity_count,
                "competitors_analyzed": self.competitors_analyzed,
            },
            "temporal": {
                "violations_high": self.temporal_violations_high,
                "compliant": self.temporal_compliant,
            },
            "coverage": {
                "auto_fixed": self.coverage_auto_fixed,
                "sections_before": self.coverage_sections_before,
                "sections_after": self.coverage_sections_after,
            },
            "superlative": {
                "suppressed": self.superlatives_suppressed,
                "total": self.superlatives_total,
            },
            "consensus": {
                "claims_approved": self.claims_approved,
                "claims_rejected": self.claims_rejected,
                "entropy_risk": self.entropy_risk,
                "critique_count": len(self.critique_issues),
            },
            "dag": {
                "claim_count": self.dag_claim_count,
                "edge_count": self.dag_edge_count,
                "acyclic": self.dag_acyclic,
                "contradictions": self.contradiction_count,
            },
            "truth": {
                "node_count": self.truth_node_count,
                "citation_count": self.citation_count,
                "hallucinations": len(self.hallucination_signals),
                "repairs": len(self.repair_history),
            },
            "trust": {
                "risk_score": round(self.trust_risk_score, 3),
                "verdict": self.trust_verdict,
                "factor_count": len(self.trust_factors),
            },
            "editorial_score": {
                "score": round(self.editorial_score, 1),
                "verdict": self.editorial_verdict,
                "components": self.editorial_components,
            },
            "benchmarks": {
                "overall": round(self.benchmark_overall, 1),
                "details": {
                    k: {"score": v.get("score", 0)} if isinstance(v, dict) else v
                    for k, v in self.benchmark_results.items()
                    if k != "overall"
                },
            },
            "governance": {
                "publish_blocked": self.publish_blocked,
                "block_reason": self.block_reason,
                "verdict": self.governance_verdict,
                "repair_attempts": self.repair_attempts,
            },
            "stage_timings": dict(self.stage_timings),
            "total_duration_ms": round(self.total_duration_ms, 1),
            "event_count": len(self.events),
        }

    def summary(self) -> str:
        d = self.to_dict()
        lines = [
            "╔══════════════════════════════════════════════════════════",
            f"║  STATE: {self.keyword}  [{self.state_id[:20]}...]",
            "╠══════════════════════════════════════════════════════════",
            f"║  Article:     {d['word_count']} words",
            f"║  Evidence:    {d['evidence']['entity_count']} entities from {d['evidence']['competitors_analyzed']} competitors",
            f"║  Temporal:    {d['temporal']['violations_high']} high violations, compliant={d['temporal']['compliant']}",
            f"║  Coverage:    auto_fixed={d['coverage']['auto_fixed']}, sections {d['coverage']['sections_before']}→{d['coverage']['sections_after']}",
            f"║  Superlative: {d['superlative']['suppressed']} suppressed / {d['superlative']['total']} total",
            f"║  Consensus:   {d['consensus']['claims_approved']} approved, {d['consensus']['claims_rejected']} rejected",
            f"║  DAG:         {d['dag']['claim_count']} claims, {d['dag']['contradictions']} contradictions",
            f"║  Trust:       risk={d['trust']['risk_score']:.2f} → {d['trust']['verdict']}",
            f"║  Editorial:   {d['editorial_score']['score']}/100 → {d['editorial_score']['verdict']}",
            f"║  Benchmarks:  {d['benchmarks']['overall']}/100",
            f"║  Governance:  blocked={d['governance']['publish_blocked']}, verdict={d['governance']['verdict']}",
            f"║  Duration:    {d['total_duration_ms']:.0f}ms  Events: {d['event_count']}",
            "╚══════════════════════════════════════════════════════════",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"GenState({self.keyword}, risk={self.trust_risk_score:.2f})"

    # ── Persistence for Replay ──

    def save(self, path: Optional[str] = None) -> str:
        """Save state to replay_store/ for later debugging."""
        REPLAY_DIR.mkdir(parents=True, exist_ok=True)
        if not path:
            path = str(REPLAY_DIR / f"state_{self.state_id}.json")
        payload = self.to_dict()
        payload["article"] = self.article
        payload["strategy"] = self.strategy
        payload["_timestamp_iso"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(self.created_at))
        Path(path).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        log.info("[STATE] Saved to %s", path)
        return path

    @classmethod
    def load(cls, path: str) -> "GenerationState":
        """Load state from a replay file."""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        state = cls(payload.get("keyword", "unknown"), payload.get("model", "default"))
        state.state_id = payload.get("state_id", state.state_id)
        state.article = payload.get("article", "")
        state.word_count = payload.get("word_count", 0)
        state.strategy = payload.get("strategy", {})
        state.created_at = payload.get("created_at", time.time())

        # Restore nested structures
        ev = payload.get("evidence", {})
        state.evidence_entity_count = ev.get("entity_count", 0)
        state.competitors_analyzed = ev.get("competitors_analyzed", 0)

        te = payload.get("temporal", {})
        state.temporal_violations_high = te.get("violations_high", 0)
        state.temporal_compliant = te.get("compliant", True)

        cov = payload.get("coverage", {})
        state.coverage_auto_fixed = cov.get("auto_fixed", False)
        state.coverage_sections_before = cov.get("sections_before", 0)
        state.coverage_sections_after = cov.get("sections_after", 0)

        sup = payload.get("superlative", {})
        state.superlatives_suppressed = sup.get("suppressed", 0)
        state.superlatives_total = sup.get("total", 0)

        con = payload.get("consensus", {})
        state.claims_approved = con.get("claims_approved", 0)
        state.claims_rejected = con.get("claims_rejected", 0)
        state.entropy_risk = con.get("entropy_risk", "unknown")

        dag = payload.get("dag", {})
        state.dag_claim_count = dag.get("claim_count", 0)
        state.dag_contradictions = dag.get("contradictions", 0)

        tr = payload.get("trust", {})
        state.trust_risk_score = tr.get("risk_score", 0.0)
        state.trust_verdict = tr.get("verdict", "unknown")

        es = payload.get("editorial_score", {})
        state.editorial_score = es.get("score", 0.0)
        state.editorial_verdict = es.get("verdict", "unknown")
        state.editorial_components = es.get("components", [])

        bm = payload.get("benchmarks", {})
        state.benchmark_overall = bm.get("overall", 0.0)

        gov = payload.get("governance", {})
        state.publish_blocked = gov.get("publish_blocked", False)
        state.block_reason = gov.get("block_reason", "")
        state.governance_verdict = gov.get("verdict", "unknown")
        state.repair_attempts = gov.get("repair_attempts", 0)

        return state

    @classmethod
    def list_replays(cls, keyword: Optional[str] = None) -> list[dict]:
        """List available replay files."""
        if not REPLAY_DIR.exists():
            return []
        replays = []
        for f in sorted(REPLAY_DIR.glob("state_*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if keyword and keyword.lower() not in data.get("keyword", "").lower():
                    continue
                replays.append({
                    "path": str(f),
                    "keyword": data.get("keyword", "?"),
                    "score": data.get("editorial_score", {}).get("score", "?"),
                    "verdict": data.get("editorial_score", {}).get("verdict", "?"),
                    "blocked": data.get("governance", {}).get("publish_blocked", False),
                    "timestamp": data.get("_timestamp_iso", "?"),
                    "words": data.get("word_count", 0),
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return replays[:20]
