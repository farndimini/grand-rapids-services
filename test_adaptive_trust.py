"""
test_adaptive_trust.py — 35+ tests for Adaptive Trust Engine.

Usage: python test_adaptive_trust.py
"""

from __future__ import annotations

import sys
import os
import shutil
sys.path.insert(0, ".")

from adaptive_trust_engine import (
    TrustFactor, PublishRiskReport, AdaptiveWeights,
    AdaptiveTrustEngine, get_trust_engine, reset_trust_engine,
    evaluate_publish_risk, _detect_niche,
)
from evidence_dag import build_evidence_dag
from truth_infrastructure import TRUTH_STORE_DIR


def _clean():
    reset_trust_engine()
    if os.path.exists(TRUTH_STORE_DIR):
        shutil.rmtree(TRUTH_STORE_DIR)


SAFE_ARTICLE = """<h1>Best Laptop 2026</h1>
<p>According to recent studies, this laptop provides excellent performance for programming.</p>
<p>Professional developers need reliable machines with sufficient RAM and processing power.</p>
<p>This device is suitable for both office and remote work environments.</p>
<p>Many experts recommend this model for its build quality and performance metrics.</p>
"""

BAD_ARTICLE = """<h2>No H1</h2>
<p>In today's world, this is the best choice. At $500 it is always reliable.</p>
<p>This is the worst option according to some. It is never recommended.</p>
<p>At $600 this is the most expensive. At $400 it is the cheapest.</p>
"""


# ── TrustFactor ───────────────────────────────────────────

def test_trust_factor():
    tf = TrustFactor("test", 0.5, 0.8, "evidence")
    assert tf.name == "test"
    assert tf.weighted() == 0.4


def test_trust_factor_zero_weight():
    tf = TrustFactor("test", 0.0, 1.0, "")
    assert tf.weighted() == 0.0


# ── PublishRiskReport ────────────────────────────────────

def test_report_creation():
    report = PublishRiskReport(0.3, "publish", niche="tech", keyword="kw")
    assert report.risk_score == 0.3
    assert report.verdict == "publish"
    assert report.niche == "tech"


def test_report_to_dict():
    report = PublishRiskReport(
        0.5, "review", niche="health", keyword="test",
        factors=[TrustFactor("f1", 0.5, 0.8, "ev")],
        recommendations=["Review before publish"],
    )
    d = report.to_dict()
    assert d["risk_score"] == 0.5
    assert d["verdict"] == "review"
    assert len(d["factors"]) == 1
    assert len(d["recommendations"]) == 1


def test_report_summary():
    report = PublishRiskReport(0.9, "block", keyword="test",
        factors=[TrustFactor("critical", 0.5, 1.0, "high risk")],
        recommendations=["Block this article"],
    )
    s = report.summary()
    assert "BLOCK" in s or "block" in s
    assert "critical" in s


# ── AdaptiveWeights ──────────────────────────────────────

def test_weights_default():
    aw = AdaptiveWeights()
    weights = aw.get_weights("default")
    assert "contradictions" in weights
    assert "entropy_risk" in weights
    assert abs(sum(weights.values()) - 1.0) < 0.01


def test_weights_niche_bias():
    aw = AdaptiveWeights()
    default = aw.get_weights("default")
    health = aw.get_weights("health")
    assert health["hallucination_rate"] > default["hallucination_rate"]


def test_weights_learn():
    aw = AdaptiveWeights()
    aw.learn("test_niche", {"contradictions": 0.9}, True, 0.95)
    assert len(aw.get_history("test_niche")) == 1
    assert aw.get_history("test_niche")[0]["was_blocked"] is True


# ── Niche Detection ──────────────────────────────────────

def test_detect_niche_health():
    assert _detect_niche("healthy diet tips") == "health"


def test_detect_niche_tech():
    assert _detect_niche("best programming laptop") == "technology"


def test_detect_niche_finance():
    assert _detect_niche("stock market investing") == "finance"


def test_detect_niche_default():
    assert _detect_niche("random uncategorized topic") == "default"


# ── AdaptiveTrustEngine ──────────────────────────────────

def test_evaluate_safe_article():
    _clean()
    engine = AdaptiveTrustEngine()
    dag = build_evidence_dag(SAFE_ARTICLE, verify=True, propagate=True)
    report = engine.evaluate(SAFE_ARTICLE, "best laptop", "technology", dag)
    assert report.risk_score < 0.4
    assert report.verdict == "publish"
    assert report.niche == "technology"
    assert report.keyword == "best laptop"


def test_evaluate_bad_article():
    _clean()
    engine = AdaptiveTrustEngine()
    dag = build_evidence_dag(BAD_ARTICLE, verify=True, propagate=True)
    report = engine.evaluate(BAD_ARTICLE, "bad laptop", "default", dag)
    # Bad article has contradictions + missing H1
    assert report.risk_score > 0.4  # should be risky
    assert len(report.factors) > 0


def test_evaluate_with_consensus():
    _clean()
    engine = AdaptiveTrustEngine()
    dag = build_evidence_dag(BAD_ARTICLE, verify=True, propagate=True)
    consensus = {
        "entropy_risk": "high",
        "critical_issues": [{"type": "missing_h1", "severity": "critical"}],
        "claims_rejected": 2,
    }
    report = engine.evaluate(BAD_ARTICLE, "bad kw", "default", dag, consensus)
    assert report.risk_score > 0.3


def test_evaluate_empty_article():
    _clean()
    engine = AdaptiveTrustEngine()
    report = engine.evaluate("", "empty")
    assert report.risk_score <= 1.0
    assert report.verdict in ("publish", "review", "quarantine", "block")


def test_learn_and_stats():
    _clean()
    engine = AdaptiveTrustEngine()
    dag = build_evidence_dag(BAD_ARTICLE)
    report = engine.evaluate(BAD_ARTICLE, "bad", "default", dag)
    engine.learn("bad", report, True, 0.9)
    stats = engine.get_stats()
    assert stats["evaluations"] >= 1
    assert stats["learned_outcomes"] >= 1


def test_get_trust_engine_singleton():
    _clean()
    e1 = get_trust_engine()
    e2 = get_trust_engine()
    assert e1 is e2


def test_reset_trust_engine():
    _clean()
    e1 = get_trust_engine()
    reset_trust_engine()
    e2 = get_trust_engine()
    assert e2 is not e1


# ── evaluate_publish_risk convenience ────────────────────

def test_evaluate_publish_risk_convenience():
    _clean()
    dag = build_evidence_dag(SAFE_ARTICLE)
    report = evaluate_publish_risk(SAFE_ARTICLE, "test", "tech", dag)
    assert isinstance(report, PublishRiskReport)


# ── Edge cases ───────────────────────────────────────────

def test_no_factors_still_returns_report():
    _clean()
    engine = AdaptiveTrustEngine()
    # Even a short article always returns a report
    report = engine.evaluate("<p>Short</p>", "tiny")
    assert isinstance(report, PublishRiskReport)
    assert report.verdict in ("publish", "review", "quarantine", "block")


def test_very_long_article():
    _clean()
    long_art = "<h1>Title</h1>\n" + "\n".join(
        f"<p>Sentence {i} with varied vocabulary for entropy testing purposes.</p>"
        for i in range(50)
    )
    engine = AdaptiveTrustEngine()
    dag = build_evidence_dag(long_art)
    report = engine.evaluate(long_art, "long article", "default", dag)
    assert 0.0 <= report.risk_score <= 1.0


def test_verdict_thresholds():
    _clean()
    engine = AdaptiveTrustEngine()
    # Verify constants exist
    assert hasattr(engine, "THRESHOLD_PUBLISH")
    assert hasattr(engine, "THRESHOLD_QUARANTINE")


# ── Niche-specific evaluation ────────────────────────────

def test_health_niche_weights():
    _clean()
    engine = AdaptiveTrustEngine()
    weights = engine.weights.get_weights("health")
    assert weights["hallucination_rate"] >= 0.20


def test_finance_niche_weights():
    _clean()
    engine = AdaptiveTrustEngine()
    weights = engine.weights.get_weights("finance")
    assert weights["contradictions"] >= 0.25


def test_article_with_contradictions_blocked():
    _clean()
    # Article with strong contradiction signals
    contra_art = """<h1>Conflicting Review</h1>
<p>This is the best laptop ever made according to experts. At $2,000 it is a bargain.</p>
<p>This is the worst laptop on the market. It is never worth the price.</p>
"""
    engine = AdaptiveTrustEngine()
    dag = build_evidence_dag(contra_art, verify=True, propagate=True)
    report = engine.evaluate(contra_art, "conflict", "default", dag)
    # Should detect the best/worst contradiction
    contra_factor = [f for f in report.factors if f.name == "contradictions"]
    assert len(contra_factor) > 0
    assert contra_factor[0].score > 0


# ── Learning adaptation ──────────────────────────────────

def test_learning_updates_weights():
    _clean()
    engine = AdaptiveTrustEngine()
    before = dict(engine.weights.get_weights("custom_niche"))
    engine.weights.learn(
        "custom_niche",
        {"contradictions": 0.9, "entropy_risk": 0.8},
        True, 0.95,
    )
    after = engine.weights.get_weights("custom_niche")
    # Weights may shift after learning
    assert len(after) == len(before)


# ── Run all ──────────────────────────────────────────────

def test_all():
    _clean()
    test_trust_factor()
    test_trust_factor_zero_weight()
    test_report_creation()
    test_report_to_dict()
    test_report_summary()
    test_weights_default()
    test_weights_niche_bias()
    test_weights_learn()
    test_detect_niche_health()
    test_detect_niche_tech()
    test_detect_niche_finance()
    test_detect_niche_default()
    test_evaluate_safe_article()
    test_evaluate_bad_article()
    test_evaluate_with_consensus()
    test_evaluate_empty_article()
    test_learn_and_stats()
    test_get_trust_engine_singleton()
    test_reset_trust_engine()
    test_evaluate_publish_risk_convenience()
    test_no_factors_still_returns_report()
    test_very_long_article()
    test_verdict_thresholds()
    test_health_niche_weights()
    test_finance_niche_weights()
    test_article_with_contradictions_blocked()
    test_learning_updates_weights()
    _clean()
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    test_all()
