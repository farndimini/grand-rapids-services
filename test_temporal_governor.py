"""
test_temporal_governor.py — Tests for Temporal Governor
========================================================
Tests ExpiryPolicy, FreshnessPolicy, CitationDecayMonitor,
StaleArticleScanner, DecayAlertSystem, and TemporalGovernor.
"""

import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ["SEO_AGENT_TEST_MODE"] = "1"

from temporal_governor import (
    ExpiryPolicy, FreshnessPolicy, CitationDecayMonitor,
    StaleArticleScanner, DecayAlertSystem,
    TemporalGovernor, FreshnessReport, ExpiredClaim, DecayAlert,
    get_temporal_governor, reset_temporal_governor, run_temporal_governance,
)

FRESH_ARTICLE = """
<h1>Best Laptops for Programming in 2026</h1>
<p>According to recent studies, the MacBook Pro is currently the top choice for developers in 2026.</p>
<p>The latest models start at approximately $2,499.</p>
<p>As of 2026, Apple's M4 chip delivers about 25% better performance.</p>
<a href="https://apple.com">source</a>
"""

STALE_ARTICLE = """
<h1>Best Laptops for Programming</h1>
<p>In 2020, the MacBook Pro was the best choice.</p>
<p>A few years ago, prices started at $1,999.</p>
<p>Traditionally, Dell has been the market leader historically.</p>
<p>As of 2021, we recommended the ThinkPad as our top pick.</p>
<p>As of 2022, the old pricing was approximately $1,500.</p>
<a href="https://old-source.com">old source</a>
"""


def test_expiry_policy_defaults():
    policy = ExpiryPolicy()
    max_age = policy.get_max_age("price", "default")
    assert max_age == 90.0
    max_age_factual = policy.get_max_age("factual", "default")
    assert max_age_factual == 180.0
    print("  ✓ ExpiryPolicy defaults")


def test_expiry_policy_niche():
    policy = ExpiryPolicy()
    tech_price = policy.get_max_age("price", "technology")
    assert tech_price == 60.0  # technology prices stale faster
    legal_factual = policy.get_max_age("factual", "legal")
    assert legal_factual == 365.0
    print("  ✓ ExpiryPolicy niche adjustments")


def test_expiry_policy_is_expired():
    policy = ExpiryPolicy()
    expired, reason = policy.is_expired("price", 200.0, "default")
    assert expired is True
    assert "exceeded" in reason
    not_expired, _ = policy.is_expired("price", 10.0, "default")
    assert not_expired is False
    print("  ✓ ExpiryPolicy is_expired")


def test_freshness_policy():
    policy = FreshnessPolicy(min_freshness_score=0.4)
    status, violations = policy.check_sla(0.5, 0.1, 0)
    assert status == "compliant"
    assert len(violations) == 0
    print("  ✓ FreshnessPolicy compliant")


def test_freshness_policy_breach():
    policy = FreshnessPolicy(min_freshness_score=0.4, max_expired_citations=1)
    status, violations = policy.check_sla(0.2, 0.5, 3)
    assert status == "breached"
    assert len(violations) >= 2
    print("  ✓ FreshnessPolicy breach")


def test_freshness_policy_warning():
    policy = FreshnessPolicy(min_freshness_score=0.4)
    status, violations = policy.check_sla(0.3, 0.1, 0)
    assert status == "warning"
    assert len(violations) == 1
    print("  ✓ FreshnessPolicy warning")


def test_citation_decay_monitor():
    monitor = CitationDecayMonitor(max_citation_age_days=180)
    now = time.time()
    fresh = monitor.check_citation("https://fresh.com", now - 10)
    assert fresh["expired"] is False
    assert fresh["freshness"] > 0.9
    expired = monitor.check_citation("https://old.com", now - 200*86400)
    assert expired["expired"] is True
    assert expired["freshness"] < 0.5
    print("  ✓ CitationDecayMonitor")


def test_citation_decay_batch():
    monitor = CitationDecayMonitor()
    now = time.time()
    citations = [
        {"url": "https://fresh.com", "extracted_at": now - 10, "domain": "fresh.com"},
        {"url": "https://old.com", "extracted_at": now - 365*86400, "domain": "old.com"},
    ]
    results = monitor.check_citations_batch(citations)
    assert len(results) == 2
    expired_count = sum(1 for r in results if r.get("expired"))
    assert expired_count >= 1
    print("  ✓ CitationDecayMonitor batch")


def test_stale_article_scanner_fresh():
    scanner = StaleArticleScanner()
    report = scanner.scan(FRESH_ARTICLE, "laptop 2026", "technology")
    assert isinstance(report, FreshnessReport)
    assert report.overall_freshness > 0.5
    print("  ✓ StaleArticleScanner fresh article")


def test_stale_article_scanner_stale():
    scanner = StaleArticleScanner()
    report = scanner.scan(STALE_ARTICLE, "old laptop", "technology")
    assert report.overall_freshness < 0.8
    assert len(report.expired_claims) > 0
    assert report.stale_statistics > 0
    assert report.outdated_recommendations > 0
    print("  ✓ StaleArticleScanner stale article")


def test_stale_article_scanner_with_claims():
    scanner = StaleArticleScanner()
    claims = [
        {"id": "c1", "text": "price $999", "claim_type": "price",
         "age_days": 200, "confidence": 0.8},
        {"id": "c2", "text": "2024 statistics", "claim_type": "percentage",
         "age_days": 10, "confidence": 0.9},
    ]
    report = scanner.scan(STALE_ARTICLE, "test", claims=claims)
    assert len(report.expired_claims) >= 1
    print("  ✓ StaleArticleScanner with claims")


def test_decay_alert_system():
    system = DecayAlertSystem()
    alert = DecayAlert(
        alert_type="claim_expired",
        keyword="test kw",
        severity="warning",
        message="Test alert",
        score=0.5,
    )
    system.record_alert(alert)
    alerts = system.get_alerts(keyword="test kw")
    assert len(alerts) >= 1
    assert alerts[0].alert_type == "claim_expired"
    print("  ✓ DecayAlertSystem")


def test_decay_alert_stats():
    system = DecayAlertSystem()
    stats = system.get_stats()
    assert "total_alerts" in stats
    assert "by_severity" in stats
    assert "by_type" in stats
    print("  ✓ DecayAlertSystem stats")


def test_freshness_report_dataclass():
    report = FreshnessReport(keyword="test", overall_freshness=0.8)
    d = report.to_dict()
    assert d["keyword"] == "test"
    assert d["overall_freshness"] == 0.8
    assert d["sla_status"] == "compliant"
    print("  ✓ FreshnessReport")


def test_freshness_report_with_claims():
    claim = ExpiredClaim(
        claim_id="c1", claim_text="old price",
        claim_type="price", keyword="test",
        policy_name="expiry", expiry_reason="too old",
        age_days=200, original_confidence=0.5,
    )
    report = FreshnessReport(
        keyword="test", overall_freshness=0.3,
        expired_claims=[claim],
    )
    d = report.to_dict()
    assert len(d["expired_claims"]) == 1
    assert d["expired_claims"][0]["claim_text"] == "old price"
    print("  ✓ FreshnessReport with claims")


def test_temporal_governor():
    reset_temporal_governor()
    governor = get_temporal_governor()
    assert governor is not None
    assert governor.expiry_policy is not None
    assert governor.freshness_policy is not None
    print("  ✓ TemporalGovernor singleton")


def test_governor_audit_fresh():
    governor = get_temporal_governor()
    report = governor.audit_article(FRESH_ARTICLE, "laptop 2026", "technology")
    assert report.overall_freshness > 0.3
    assert isinstance(report.quarantine_recommended, bool)
    print("  ✓ Governor audit fresh article")


def test_governor_audit_stale():
    governor = get_temporal_governor()
    report = governor.audit_article(STALE_ARTICLE, "old laptop", "default")
    assert len(report.alerts) > 0
    print("  ✓ Governor audit stale article")


def test_governor_quarantine_candidates():
    governor = get_temporal_governor()
    articles = [
        {"keyword": "fresh", "article": FRESH_ARTICLE, "niche": "technology"},
        {"keyword": "stale", "article": STALE_ARTICLE, "niche": "default"},
    ]
    candidates = governor.get_quarantine_candidates(articles)
    assert isinstance(candidates, list)
    print("  ✓ Governor quarantine candidates")


def test_governor_stats():
    governor = get_temporal_governor()
    stats = governor.get_stats()
    assert "alert_stats" in stats
    print("  ✓ Governor stats")


def test_run_temporal_governance_convenience():
    reset_temporal_governor()
    report = run_temporal_governance(FRESH_ARTICLE, "convenience test", "default")
    assert isinstance(report, FreshnessReport)
    assert report.keyword == "convenience test"
    print("  ✓ run_temporal_governance convenience")


def test_expired_claim_dataclass():
    claim = ExpiredClaim(
        claim_id="test123", claim_text="$999",
        claim_type="price", keyword="laptop",
        policy_name="price_expiry", expiry_reason="too old",
        age_days=100, original_confidence=0.8,
    )
    d = claim.to_dict()
    assert d["claim_id"] == "test123"
    assert d["age_days"] == 100.0
    assert d["original_confidence"] == 0.8
    print("  ✓ ExpiredClaim dataclass")


def test_decay_alert_dataclass():
    alert = DecayAlert(
        alert_type="sla_breach",
        keyword="test",
        severity="critical",
        message="SLA breached",
        affected_items=["item1"],
        score=0.2,
    )
    d = alert.to_dict()
    assert d["alert_type"] == "sla_breach"
    assert d["severity"] == "critical"
    assert d["score"] == 0.2
    print("  ✓ DecayAlert dataclass")


def test_governor_reset():
    reset_temporal_governor()
    g1 = get_temporal_governor()
    g2 = get_temporal_governor()
    assert g1 is g2
    reset_temporal_governor()
    g3 = get_temporal_governor()
    assert g3 is not g1
    print("  ✓ Governor reset")


def test_governor_audit_with_citations():
    governor = get_temporal_governor()
    citations = [
        {"url": "https://old.com", "extracted_at": time.time() - 365*86400, "domain": "old.com"},
    ]
    report = governor.audit_article(
        FRESH_ARTICLE, "test",
        citations=citations,
    )
    assert report.expired_citations >= 1
    print("  ✓ Governor audit with citations")


if __name__ == "__main__":
    tests = [
        test_expiry_policy_defaults, test_expiry_policy_niche,
        test_expiry_policy_is_expired,
        test_freshness_policy, test_freshness_policy_breach,
        test_freshness_policy_warning,
        test_citation_decay_monitor, test_citation_decay_batch,
        test_stale_article_scanner_fresh, test_stale_article_scanner_stale,
        test_stale_article_scanner_with_claims,
        test_decay_alert_system, test_decay_alert_stats,
        test_freshness_report_dataclass, test_freshness_report_with_claims,
        test_temporal_governor,
        test_governor_audit_fresh, test_governor_audit_stale,
        test_governor_quarantine_candidates, test_governor_stats,
        test_run_temporal_governance_convenience,
        test_expired_claim_dataclass, test_decay_alert_dataclass,
        test_governor_reset, test_governor_audit_with_citations,
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
    print(f"\nTemporal Governor Tests: {passed} passed, {failed} failed, {len(tests)} total")
    if failed > 0:
        sys.exit(1)
    print("ALL TESTS PASSED")
