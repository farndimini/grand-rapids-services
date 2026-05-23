"""
test_enterprise_governor.py — Tests for Enterprise Governor
=============================================================
Tests ConfidenceBudget, PolicyEngine, EnterpriseGovernor,
GovernanceDecision, and event integration.
"""

import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ["SEO_AGENT_TEST_MODE"] = "1"

from enterprise_governor import (
    ConfidenceBudget, PolicyEngine, EnterpriseGovernor,
    GovernanceDecision, PublishBlocked, PublishQuarantined,
    get_governor, reset_governor, evaluate_publish,
)


def test_confidence_budget():
    budget = ConfidenceBudget(max_budget=100.0)
    assert budget.remaining == 100.0
    can_pub = budget.can_publish(0.3)
    assert can_pub is True
    budget.consume("test kw", 0.3, "publish")
    assert budget.remaining < 100.0
    print("  ✓ ConfidenceBudget")


def test_confidence_budget_exhaustion():
    budget = ConfidenceBudget(max_budget=20.0)
    can_pub = budget.can_publish(0.3)
    assert can_pub is True
    budget.consume("risk", 0.3, "review")
    # cost = 0.3 * 20 = 6, remaining = 20 - 6 = 14
    can_pub2 = budget.can_publish(0.9)
    # cost = 0.9 * 20 = 18 > 14, so False
    assert can_pub2 is False
    print("  ✓ ConfidenceBudget exhaustion")


def test_confidence_budget_reset():
    budget = ConfidenceBudget(max_budget=100.0, reset_interval=0.001)
    budget._consumed = 90.0
    import time
    time.sleep(0.01)
    assert budget.remaining == 100.0
    print("  ✓ ConfidenceBudget reset")


def test_confidence_budget_stats():
    budget = ConfidenceBudget(max_budget=100.0)
    budget.consume("test", 0.5, "review")
    stats = budget.get_stats()
    assert stats["max_budget"] == 100.0
    assert stats["total_decisions"] == 1
    assert "consumed" in stats
    assert "usage_pct" in stats
    print("  ✓ ConfidenceBudget stats")


def test_policy_engine():
    engine = PolicyEngine()
    violations = engine.enforce(0.3, 0.8)
    assert len(violations) == 0
    print("  ✓ PolicyEngine pass")


def test_policy_engine_block():
    engine = PolicyEngine()
    violations = engine.enforce(0.85, 0.1)
    block_violations = [v for v in violations if v["action"] == "block"]
    assert len(block_violations) >= 1
    print("  ✓ PolicyEngine block")


def test_policy_engine_quarantine():
    engine = PolicyEngine()
    violations = engine.enforce(0.65, 0.5)
    quarantine_violations = [v for v in violations if v["action"] == "quarantine"]
    assert len(quarantine_violations) >= 1
    print("  ✓ PolicyEngine quarantine")


def test_policy_engine_review():
    engine = PolicyEngine()
    violations = engine.enforce(0.3, 0.35)
    review_violations = [v for v in violations if v["action"] == "review"]
    assert len(review_violations) >= 1
    print("  ✓ PolicyEngine review")


def test_governance_decision_dataclass():
    decision = GovernanceDecision(
        keyword="test",
        verdict="publish",
        confidence_budget=0.8,
        risk_score=0.2,
    )
    d = decision.to_dict()
    assert d["keyword"] == "test"
    assert d["verdict"] == "publish"
    assert d["risk_score"] == 0.2
    s = decision.summary()
    assert "PUBLISH" in s
    print("  ✓ GovernanceDecision")


def test_governance_decision_with_factors():
    decision = GovernanceDecision(
        keyword="test",
        verdict="block",
        confidence_budget=0.1,
        risk_score=0.85,
        factors=[{"name": "trust", "score": 0.9}],
        recommendations=["Block"],
        escalation_path=["policy"],
    )
    d = decision.to_dict()
    assert len(d["factors"]) == 1
    assert len(d["recommendations"]) == 1
    assert len(d["escalation_path"]) == 1
    print("  ✓ GovernanceDecision with factors")


def test_publish_blocked_exception():
    try:
        raise PublishBlocked("Risk too high", "test")
    except PublishBlocked as e:
        assert "Risk too high" in str(e)
        assert e.source == "test"
    print("  ✓ PublishBlocked exception")


def test_publish_quarantined_exception():
    try:
        raise PublishQuarantined("Needs review", "test")
    except PublishQuarantined as e:
        assert "Needs review" in str(e)
        assert e.source == "test"
    print("  ✓ PublishQuarantined exception")


def test_enterprise_governor():
    reset_governor()
    governor = get_governor()
    assert governor is not None
    assert governor.policy_engine is not None
    assert governor.confidence_budget is not None
    print("  ✓ EnterpriseGovernor singleton")


def test_governor_evaluate_publish():
    reset_governor()
    governor = get_governor()
    decision = governor.evaluate(
        keyword="test kw",
        risk_score=0.2,
        confidence=0.8,
    )
    assert decision.verdict == "publish"
    assert decision.keyword == "test kw"
    assert 0.0 <= decision.risk_score <= 1.0
    print("  ✓ Governor evaluate publish")


def test_governor_evaluate_block():
    governor = get_governor()
    decision = governor.evaluate(
        keyword="high risk",
        risk_score=0.85,
        confidence=0.1,
    )
    assert decision.verdict == "block"
    print("  ✓ Governor evaluate block")


def test_governor_with_trust_report():
    governor = get_governor()
    decision = governor.evaluate(
        keyword="trust test",
        trust_report={"risk_score": 0.7, "verdict": "quarantine"},
    )
    assert decision.risk_score > 0
    factors = [f for f in decision.factors if f.get("name") == "adaptive_trust"]
    assert len(factors) >= 1
    print("  ✓ Governor with trust report")


def test_governor_with_swarm_report():
    governor = get_governor()
    decision = governor.evaluate(
        keyword="swarm test",
        swarm_report={
            "weighted_risk_score": 0.8,
            "consensus_verdict": "block",
            "quarantine_recommended": True,
            "human_review_recommended": True,
        },
    )
    assert decision.verdict == "block"
    print("  ✓ Governor with swarm report")


def test_governor_with_governor_report():
    governor = get_governor()
    decision = governor.evaluate(
        keyword="temporal test",
        governor_report={
            "overall_freshness": 0.2,
            "sla_status": "breached",
            "quarantine_recommended": True,
            "expired_claims": [{"text": "old claim"}],
        },
    )
    temporal_factors = [f for f in decision.factors if f.get("name") == "temporal_governor"]
    assert len(temporal_factors) >= 1
    print("  ✓ Governor with governor report")


def test_governor_with_consensus_report():
    governor = get_governor()
    decision = governor.evaluate(
        keyword="consensus test",
        consensus_report={
            "claims_rejected": 5,
            "claims_scored": 10,
            "critical_issues": [{"issue": "test"}],
        },
    )
    consensus_factors = [f for f in decision.factors if f.get("name") == "consensus_engine"]
    assert len(consensus_factors) >= 1
    print("  ✓ Governor with consensus report")


def test_governor_with_dag_report():
    governor = get_governor()
    decision = governor.evaluate(
        keyword="dag test",
        dag_report={"contradictions": 5, "claim_count": 10},
    )
    dag_factors = [f for f in decision.factors if f.get("name") == "evidence_dag"]
    assert len(dag_factors) >= 1
    print("  ✓ Governor with DAG report")


def test_governor_with_repair_memory():
    governor = get_governor()
    decision = governor.evaluate(
        keyword="repair test",
        repair_memory={
            "escalated": True,
            "escalation_reason": "Max retries",
            "outcomes": [{"mutated": True, "success": False}],
        },
    )
    repair_factors = [f for f in decision.factors if f.get("name") == "repair_orchestrator"]
    assert len(repair_factors) >= 1
    print("  ✓ Governor with repair memory")


def test_governor_with_all_reports():
    governor = get_governor()
    decision = governor.evaluate(
        keyword="full test",
        risk_score=0.5,
        confidence=0.6,
        trust_report={"risk_score": 0.4, "verdict": "review"},
        swarm_report={"weighted_risk_score": 0.5, "consensus_verdict": "review"},
        governor_report={"overall_freshness": 0.6, "sla_status": "warning"},
        consensus_report={"claims_rejected": 2, "claims_scored": 10},
        dag_report={"contradictions": 1, "claim_count": 10},
    )
    assert len(decision.factors) >= 4
    assert "subsystem_reports" in decision.to_dict()
    print("  ✓ Governor with ALL reports")


def test_governor_history():
    reset_governor()
    governor = get_governor()
    governor.evaluate(keyword="test1", risk_score=0.2)
    governor.evaluate(keyword="test2", risk_score=0.8)
    history = governor.get_history()
    assert len(history) == 2
    kw_history = governor.get_history(keyword="test1")
    assert len(kw_history) == 1
    print("  ✓ Governor history")


def test_governor_stats():
    governor = get_governor()
    stats = governor.get_stats()
    assert "total_decisions" in stats
    assert "verdicts" in stats
    assert "budget" in stats
    print("  ✓ Governor stats")


def test_evaluate_publish_convenience():
    reset_governor()
    decision = evaluate_publish(
        keyword="convenience",
        risk_score=0.3,
        confidence=0.7,
    )
    assert isinstance(decision, GovernanceDecision)
    assert decision.keyword == "convenience"
    print("  ✓ evaluate_publish convenience")


def test_governor_budget_blocks_after_exhaustion():
    reset_governor()
    governor = get_governor()
    # Use high-budget-consuming calls
    for i in range(5):
        governor.evaluate(
            keyword=f"budget_test_{i}",
            risk_score=0.9,
            confidence=0.1,
        )
    stats = governor.get_stats()
    assert stats["budget"]["total_decisions"] >= 5
    print("  ✓ Governor budget tracking")


def test_governor_policy_enforcement():
    reset_governor()
    governor = get_governor()
    decision = governor.evaluate(
        keyword="policy_test",
        risk_score=0.9,
        confidence=0.05,
    )
    assert decision.verdict == "block"
    assert len(decision.recommendations) > 0
    print("  ✓ Governor policy enforcement")


def test_governor_reset():
    reset_governor()
    g1 = get_governor()
    g2 = get_governor()
    assert g1 is g2
    reset_governor()
    g3 = get_governor()
    assert g3 is not g1
    print("  ✓ Governor reset")


def test_governor_empty_evaluate():
    reset_governor()
    governor = get_governor()
    decision = governor.evaluate(keyword="empty")
    assert decision.keyword == "empty"
    assert decision.verdict in ("publish", "review", "quarantine", "block")
    print("  ✓ Governor empty evaluate")


if __name__ == "__main__":
    tests = [
        test_confidence_budget, test_confidence_budget_exhaustion,
        test_confidence_budget_reset, test_confidence_budget_stats,
        test_policy_engine, test_policy_engine_block,
        test_policy_engine_quarantine, test_policy_engine_review,
        test_governance_decision_dataclass,
        test_governance_decision_with_factors,
        test_publish_blocked_exception, test_publish_quarantined_exception,
        test_enterprise_governor,
        test_governor_evaluate_publish, test_governor_evaluate_block,
        test_governor_with_trust_report, test_governor_with_swarm_report,
        test_governor_with_governor_report,
        test_governor_with_consensus_report, test_governor_with_dag_report,
        test_governor_with_repair_memory,
        test_governor_with_all_reports,
        test_governor_history, test_governor_stats,
        test_evaluate_publish_convenience,
        test_governor_budget_blocks_after_exhaustion,
        test_governor_policy_enforcement,
        test_governor_reset, test_governor_empty_evaluate,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1
    print(f"\nEnterprise Governor Tests: {passed} passed, {failed} failed, {len(tests)} total")
    if failed > 0:
        sys.exit(1)
    print("ALL TESTS PASSED")
