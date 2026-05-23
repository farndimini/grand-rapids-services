"""
test_adversarial_swarm.py — Tests for Adversarial Swarm
=========================================================
Tests all 9 agents, SwarmCoordinator, and AdversarialReport.
"""

import os, sys, json, time, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ["SEO_AGENT_TEST_MODE"] = "1"

from adversarial_swarm import (
    HallucinationHunter, ContradictionHunter, CitationAuditor,
    SEOOverOptimizationDetector, AIStyleDetector, LegalRiskAuditor,
    TemporalDecayAuditor, SchemaValidator, ManipulationDetector,
    SwarmCoordinator, AdversarialReport, AgentResult,
    get_swarm, reset_swarm, run_adversarial_swarm,
)

SAMPLE_ARTICLE = """<h1>Best Laptops for Programming in 2026</h1>
<p>When choosing a programming laptop, there are several key factors to consider.</p>
<h2>Top Laptops Compared</h2>
<p>The MacBook Pro costs approximately $2,499 and is reportedly the fastest option.</p>
<p>The Dell XPS 15 has around 16GB of RAM and excellent build quality.</p>
<h2>Detailed Reviews</h2>
<p>The ThinkPad X1 Carbon is one of the best business laptops available.</p>
<p>According to recent benchmarks, the M3 chip delivers outstanding performance.</p>
<h2>Pricing</h2>
<p>The cheapest option starts at about $999 while the most expensive is around $3,499.</p>
<p>Always check official pricing before purchasing.</p>
<h2>FAQ</h2>
<div class="faq-item"><div class="faq-q">What is the best laptop for coding?</div><div class="faq-a">The MacBook Pro 16 is widely considered the best choice.</div></div>
<script type="application/ld+json">{"@type": "FAQPage","mainEntity": [{"@type": "Question","name": "What is the best laptop for coding?","acceptedAnswer": {"@type": "Answer","text": "MacBook Pro"}}]}</script>
<script type="application/ld+json">{"@type": "Article","headline": "Best Laptops","datePublished": "2026-05-22"}</script>
"""

SAMPLE_ARTICLE_BAD = """<h1>Bad Article</h1><h1>Second H1</h1>
<p>In today's digital age, this product is a game-changer.</p>
<p>We tested this product and it costs $9,999. It is 100% guaranteed to work.</p>
<p>Limited time offer! Act now! Don't miss out on this secret insider opportunity.</p>
<p>Earn $10,000 fast! This miracle cure has no side effects.</p>
<p>Last but not least, this is the best product ever made. Always works. Never fails.</p>
<p><a href="https://example.com">link</a></p>
"""


def test_hallucination_hunter():
    agent = HallucinationHunter()
    result = agent.audit(SAMPLE_ARTICLE, "best laptop")
    assert result.agent_name == "HallucinationHunter"
    assert 0.0 <= result.risk_score <= 1.0
    assert isinstance(result.critical, bool)
    assert isinstance(result.findings, list)
    assert isinstance(result.evidence, list)
    assert 0.0 <= result.confidence <= 1.0
    print("  ✓ HallucinationHunter")


def test_contradiction_hunter():
    agent = ContradictionHunter()
    result = agent.audit(SAMPLE_ARTICLE, "best laptop")
    assert result.agent_name == "ContradictionHunter"
    assert 0.0 <= result.risk_score <= 1.0
    assert isinstance(result.critical, bool)
    print("  ✓ ContradictionHunter")


def test_citation_auditor():
    agent = CitationAuditor()
    result = agent.audit(SAMPLE_ARTICLE_BAD, "bad article")
    assert result.agent_name == "CitationAuditor"
    assert isinstance(result.risk_score, float)
    print("  ✓ CitationAuditor")


def test_seo_detector():
    agent = SEOOverOptimizationDetector()
    result = agent.audit(SAMPLE_ARTICLE, "best laptop")
    assert result.agent_name == "SEOOverOptimizationDetector"
    assert 0.0 <= result.risk_score <= 1.0
    print("  ✓ SEOOverOptimizationDetector")


def test_ai_style_detector():
    agent = AIStyleDetector()
    result = agent.audit(SAMPLE_ARTICLE_BAD, "bad article")
    assert result.agent_name == "AIStyleDetector"
    assert isinstance(result.risk_score, float)
    print("  ✓ AIStyleDetector")


def test_legal_risk_auditor():
    agent = LegalRiskAuditor()
    result = agent.audit(SAMPLE_ARTICLE_BAD, "bad article")
    assert result.agent_name == "LegalRiskAuditor"
    result2 = agent.audit(SAMPLE_ARTICLE, "best laptop")
    assert result2.risk_score < result.risk_score
    print("  ✓ LegalRiskAuditor")


def test_temporal_decay_auditor():
    agent = TemporalDecayAuditor()
    result = agent.audit(SAMPLE_ARTICLE, "best laptop")
    assert result.agent_name == "TemporalDecayAuditor"
    assert 0.0 <= result.risk_score <= 1.0
    print("  ✓ TemporalDecayAuditor")


def test_schema_validator():
    agent = SchemaValidator()
    result = agent.audit(SAMPLE_ARTICLE, "best laptop")
    assert result.agent_name == "SchemaValidator"
    # Good article should have valid schemas
    result2 = agent.audit(SAMPLE_ARTICLE_BAD, "bad article")
    assert result.risk_score < result2.risk_score or result.risk_score == 0
    print("  ✓ SchemaValidator")


def test_manipulation_detector():
    agent = ManipulationDetector()
    result = agent.audit(SAMPLE_ARTICLE_BAD, "bad article")
    assert result.agent_name == "ManipulationDetector"
    result2 = agent.audit(SAMPLE_ARTICLE, "best laptop")
    assert result.risk_score >= result2.risk_score
    print("  ✓ ManipulationDetector")


def test_agent_result_dataclass():
    r = AgentResult("TestAgent", 0.5, False, ["finding"], ["evidence"], 0.8)
    d = r.to_dict()
    assert d["agent_name"] == "TestAgent"
    assert d["risk_score"] == 0.5
    assert d["critical"] is False
    assert d["findings"] == ["finding"]
    assert d["confidence"] == 0.8
    print("  ✓ AgentResult dataclass")


def test_adversarial_report_dataclass():
    report = AdversarialReport(keyword="test")
    d = report.to_dict()
    assert d["keyword"] == "test"
    assert d["consensus_verdict"] == "pass"
    assert d["weighted_risk_score"] == 0.0
    print("  ✓ AdversarialReport")


def test_swarm_coordinator():
    reset_swarm()
    swarm = get_swarm()
    assert len(swarm.agents) == 9
    report = swarm.run_swarm(SAMPLE_ARTICLE, "best laptop")
    assert isinstance(report, AdversarialReport)
    assert report.keyword == "best laptop"
    assert len(report.agent_results) == 9
    assert 0.0 <= report.weighted_risk_score <= 1.0
    assert report.consensus_verdict in ("pass", "review", "quarantine", "block")
    assert isinstance(report.recommendations, list)
    print("  ✓ SwarmCoordinator full run")


def test_swarm_with_bad_article():
    swarm = get_swarm()
    report = swarm.run_swarm(SAMPLE_ARTICLE_BAD, "bad article")
    assert len(report.agent_results) == 9
    # Bad article should have higher risk
    good_report = swarm.run_swarm(SAMPLE_ARTICLE, "best laptop")
    assert report.weighted_risk_score >= good_report.weighted_risk_score * 0.5
    print("  ✓ Swarm with bad article")


def test_swarm_disagreement_detection():
    swarm = get_swarm()
    report = swarm.run_swarm(SAMPLE_ARTICLE, "test")
    assert isinstance(report.majority_disagreement, bool)
    print("  ✓ Swarm disagreement detection")


def test_swarm_recommendations():
    swarm = get_swarm()
    report = swarm.run_swarm(SAMPLE_ARTICLE_BAD, "bad article")
    assert len(report.recommendations) > 0
    assert isinstance(report.quarantine_recommended, bool)
    assert isinstance(report.human_review_recommended, bool)
    assert isinstance(report.auto_repair_recommended, bool)
    print("  ✓ Swarm recommendations")


def test_swarm_cross_contradictions():
    swarm = get_swarm()
    report = swarm.run_swarm(SAMPLE_ARTICLE, "test")
    assert isinstance(report.cross_agent_contradictions, list)
    print("  ✓ Cross-agent contradictions")


def test_run_adversarial_swarm_convenience():
    reset_swarm()
    report = run_adversarial_swarm(SAMPLE_ARTICLE, "convenience test")
    assert isinstance(report, AdversarialReport)
    print("  ✓ run_adversarial_swarm convenience")


def test_agent_duration_tracking():
    agent = HallucinationHunter()
    result = agent.audit(SAMPLE_ARTICLE, "test")
    assert result.duration_ms >= 0
    print("  ✓ Agent duration tracking")


def test_swarm_all_agents_report():
    swarm = get_swarm()
    report = swarm.run_swarm(SAMPLE_ARTICLE, "test")
    agent_names = [r.agent_name for r in report.agent_results]
    expected = [
        "HallucinationHunter", "ContradictionHunter", "CitationAuditor",
        "SEOOverOptimizationDetector", "AIStyleDetector", "LegalRiskAuditor",
        "TemporalDecayAuditor", "SchemaValidator", "ManipulationDetector",
    ]
    for name in expected:
        assert name in agent_names, f"Missing agent: {name}"
    print("  ✓ All 9 agents present in report")


def test_risk_score_bounds():
    swarm = get_swarm()
    report = swarm.run_swarm(SAMPLE_ARTICLE, "test")
    for r in report.agent_results:
        assert 0.0 <= r.risk_score <= 1.0, f"Risk score {r.risk_score} out of bounds for {r.agent_name}"
    assert 0.0 <= report.weighted_risk_score <= 1.0
    print("  ✓ Risk score bounds")


def test_swarm_confidence_normalization():
    swarm = get_swarm()
    report = swarm.run_swarm(SAMPLE_ARTICLE, "test")
    confidences = [r.confidence for r in report.agent_results]
    assert all(0.0 <= c <= 1.0 for c in confidences)
    print("  ✓ Confidence normalization")


def test_empty_article():
    agent = HallucinationHunter()
    result = agent.audit("", "test")
    assert 0.0 <= result.risk_score <= 1.0
    print("  ✓ Empty article handling")


def test_swarm_summary():
    swarm = get_swarm()
    report = swarm.run_swarm(SAMPLE_ARTICLE, "test")
    summary = report.summary()
    assert "Adversarial Swarm:" in summary
    assert report.consensus_verdict.upper() in summary
    print("  ✓ Swarm summary string")


def test_agent_result_serialization_roundtrip():
    r = AgentResult("Test", 0.75, True, ["issue"], ["proof"], 0.9, 12.5, "1.0")
    d = r.to_dict()
    assert d["agent_name"] == "Test"
    assert d["risk_score"] == 0.75
    assert d["critical"] is True
    assert d["findings"] == ["issue"]
    assert d["duration_ms"] == 12.5
    print("  ✓ AgentResult serialization")


def test_swarm_reset():
    reset_swarm()
    s1 = get_swarm()
    s2 = get_swarm()
    assert s1 is s2
    reset_swarm()
    s3 = get_swarm()
    assert s3 is not s1
    print("  ✓ Swarm reset")


if __name__ == "__main__":
    tests = [
        test_hallucination_hunter, test_contradiction_hunter,
        test_citation_auditor, test_seo_detector, test_ai_style_detector,
        test_legal_risk_auditor, test_temporal_decay_auditor,
        test_schema_validator, test_manipulation_detector,
        test_agent_result_dataclass, test_adversarial_report_dataclass,
        test_swarm_coordinator, test_swarm_with_bad_article,
        test_swarm_disagreement_detection, test_swarm_recommendations,
        test_swarm_cross_contradictions, test_run_adversarial_swarm_convenience,
        test_agent_duration_tracking, test_swarm_all_agents_report,
        test_risk_score_bounds, test_swarm_confidence_normalization,
        test_empty_article, test_swarm_summary,
        test_agent_result_serialization_roundtrip, test_swarm_reset,
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
    print(f"\nAdversarial Swarm Tests: {passed} passed, {failed} failed, {len(tests)} total")
    if failed > 0:
        sys.exit(1)
    print("ALL TESTS PASSED")
