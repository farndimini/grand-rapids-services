"""
test_consensus.py — 24+ tests for Generation Consensus Engine.

Usage: python -m pytest test_consensus.py -v
       python test_consensus.py   (auto-run)
"""

from __future__ import annotations

import sys
import re
sys.path.insert(0, ".")

from generation_consensus_engine import (
    CritiqueModel, FactModel, EntropyModel,
    ConfidenceScorer, ConsensusEngine, GenerationConsensusEngine,
    run_consensus,
)


# ── Fixtures ──────────────────────────────────────────────

GOOD_ARTICLE = """<h1>Best Laptop 2026 for Programming</h1>
<p>According to recent studies, the best programming laptop costs around $1,200 and provides 25% more performance than previous models.</p>
<p>Professional developers need reliable machines with sufficient RAM and processing power.</p>
<p>This laptop is estimated to last at least 5 years according to consumer reports. The price may vary by region.</p>
<p>With its powerful processor and long battery life, this device is suitable for both office and remote work.</p>
<p>Many experts recommend this model for its build quality and performance.</p>
"""

BAD_ARTICLE = """<h2>Some Content</h2>
<p>In today's world, you need a powerful machine.</p>
<p>It is always the right choice for professionals. At $500, this is the best deal. At $600, you get 10% more.</p>
<p>It is never a bad option. It is definitely the best option on the market.</p>
<p>At $700, it offers 15% improvement. At $800, 20% more. At $900, 30% more.</p>
"""


# ── CritiqueModel ─────────────────────────────────────────

def test_critique_good_article():
    cm = CritiqueModel()
    issues = cm.critique(GOOD_ARTICLE, "best laptop")
    # Good article should have no high/critical issues
    critical = [i for i in issues if i["severity"] in ("critical", "high")]
    assert len(critical) == 0, f"Unexpected critical issues: {critical}"


def test_critique_banned_opener():
    cm = CritiqueModel()
    issues = cm.critique(BAD_ARTICLE, "laptop")
    types = [i["type"] for i in issues]
    assert "banned_opener" in types


def test_critique_missing_h1():
    cm = CritiqueModel()
    issues = cm.critique(BAD_ARTICLE, "laptop")
    types = [i["type"] for i in issues]
    assert "missing_h1" in types or "duplicate_h1" in types


def test_critique_faq_mismatch():
    cm = CritiqueModel()
    faq_good = """<h1>FAQ</h1><div class="faq-q">Q1</div><div class="faq-a">A1</div>"""
    issues = cm.critique(faq_good, "faq")
    faq_types = [i for i in issues if i["type"] == "faq_mismatch"]
    assert len(faq_types) == 0, "Balanced FAQ should not flag mismatch"
    # Mismatched FAQ should flag
    faq_bad = """<h1>FAQ</h1><div class="faq-q">Q1</div>"""
    issues2 = cm.critique(faq_bad, "faq")
    faq_types2 = [i for i in issues2 if i["type"] == "faq_mismatch"]
    assert len(faq_types2) >= 1, "Unbalanced FAQ should flag mismatch"


def test_critique_keyword_missing_h1():
    cm = CritiqueModel()
    # Article with keyword in H1
    issues_hit = cm.critique(GOOD_ARTICLE, "best laptop")
    kw_miss = [i for i in issues_hit if i["type"] == "keyword_missing_h1"]
    assert len(kw_miss) == 0, "Keyword should be found in H1"
    # Article without keyword
    issues_miss = cm.critique(GOOD_ARTICLE, "nonexistentkeywordxyz")
    kw_miss2 = [i for i in issues_miss if i["type"] == "keyword_missing_h1"]
    assert len(kw_miss2) == 1


def test_critique_bare_paragraph():
    cm = CritiqueModel()
    # Text inside non-p/h1-h6/div/li/td/th tag gets flagged by regex
    bare = "<span>bare span text</span><p>ok</p>"
    issues = cm.critique(bare, "title")
    types = [i["type"] for i in issues]
    assert "bare_paragraph" in types


# ── FactModel ─────────────────────────────────────────────

def test_fact_finds_prices():
    fm = FactModel()
    results = fm.verify("Costs $1,200 and $500 respectively.")
    prices = [r for r in results if r["type"] == "price"]
    assert len(prices) >= 2


def test_fact_finds_percentages():
    fm = FactModel()
    results = fm.verify("Improves by 25% and reduces cost by 10%.")
    pcts = [r for r in results if r["type"] == "percentage"]
    assert len(pcts) >= 2


def test_fact_support_detection():
    fm = FactModel()
    with_src = "According to a study, it costs $1,200."
    no_src = "It costs $1,200."
    r1 = fm.verify(with_src)
    r2 = fm.verify(no_src)
    if r1 and r2:
        assert r1[0]["supported"] is True
        assert r2[0]["supported"] is False


def test_fact_context_trimming():
    fm = FactModel()
    ctx = fm._context("a" * 50 + "$500" + "b" * 100, "$500")
    assert len(ctx) <= 165  # 80 + len("$500") + 80


# ── EntropyModel ──────────────────────────────────────────

def test_entropy_good_article():
    em = EntropyModel()
    result = em.analyze(GOOD_ARTICLE)
    assert result["sentence_count"] >= 3
    assert "pass" in result
    assert "ai_risk" in result


def test_entropy_repetitive_starts():
    em = EntropyModel()
    monotone = ["The laptop is good", "The laptop is fast", "The laptop is cheap"]
    rs = em._repetitive_starts(monotone)
    assert rs >= 0.5  # highly repetitive (all start with "the")


def test_entropy_varied_starts():
    em = EntropyModel()
    varied = ["The laptop is good", "However it is fast", "Despite this it is cheap"]
    rs = em._repetitive_starts(varied)
    assert rs < 0.5  # low repetition


def test_entropy_empty_sentences():
    em = EntropyModel()
    result = em.analyze("<p>Short.</p>")
    assert result["pass"] is False
    assert result["reason"] == "No sentences"


# ── ConfidenceScorer ──────────────────────────────────────

def test_scorer_approves_supported_claim():
    scorer = ConfidenceScorer()
    claim = {"claim": "$1,200", "type": "price", "confidence": 0.6, "supported": True}
    result = scorer.score(claim, [])
    assert result["verdict"] == "approved"
    assert result["adjusted_confidence"] >= 0.6


def test_scorer_rejects_unsupported_claim():
    scorer = ConfidenceScorer()
    claim = {"claim": "$500", "type": "price", "confidence": 0.3, "supported": False}
    result = scorer.score(claim, [])
    assert result["verdict"] == "rejected"
    assert result["adjusted_confidence"] < 0.5


# ── ConsensusEngine ───────────────────────────────────────

def test_consensus_merge_basic():
    ce = ConsensusEngine()
    art, report = ce.merge(GOOD_ARTICLE, [], [], {"pass": True, "ai_risk": "low"})
    assert "critique_count" in report
    assert "fact_verified" in report
    assert report["entropy_pass"] is True


def test_consensus_adds_verify_tags():
    ce = ConsensusEngine()
    facts = [
        {"claim": "$500", "type": "price", "supported": False, "context": "", "confidence": 0.3},
    ]
    art, _ = ce.merge("Costs $500.", [], facts, {"pass": True})
    assert "[VERIFY]" in art


# ── GenerationConsensusEngine ─────────────────────────────

def test_full_pipeline():
    gce = GenerationConsensusEngine()
    art, report = gce.run(GOOD_ARTICLE, "best laptop")
    assert "duration_ms" in report
    assert "claims_scored" in report
    assert "claims_approved" in report
    assert "claims_rejected" in report
    assert len(art) > 0


def test_full_pipeline_with_bad_article():
    gce = GenerationConsensusEngine()
    art, report = gce.run(BAD_ARTICLE, "laptop")
    # Bad article should have banned openers flagged
    assert report["critique_count"] >= 1


def test_run_consensus_global():
    art, report = run_consensus(GOOD_ARTICLE, "best laptop")
    assert "entropy_risk" in report


# ── Integration: wire into modules.py ─────────────────────

def test_modules_import_consensus():
    """Verify the consensus import path in modules.py works."""
    from modules import write_article
    # We can't easily call write_article here (needs keyword, LLM, etc.),
    # but we can verify the import doesn't error
    assert callable(write_article)


# ── Edge cases ────────────────────────────────────────────

def test_critique_no_content():
    cm = CritiqueModel()
    issues = cm.critique("", "keyword")
    assert isinstance(issues, list)


def test_fact_no_content():
    fm = FactModel()
    results = fm.verify("")
    assert results == []


def test_entropy_no_content():
    em = EntropyModel()
    result = em.analyze("")
    assert result["pass"] is False


# ── Run directly ──────────────────────────────────────────

def test_all():
    """Run all tests."""
    test_critique_good_article()
    test_critique_banned_opener()
    test_critique_missing_h1()
    test_critique_faq_mismatch()
    test_critique_keyword_missing_h1()
    test_critique_bare_paragraph()
    test_fact_finds_prices()
    test_fact_finds_percentages()
    test_fact_support_detection()
    test_fact_context_trimming()
    test_entropy_good_article()
    test_entropy_repetitive_starts()
    test_entropy_varied_starts()
    test_entropy_empty_sentences()
    test_scorer_approves_supported_claim()
    test_scorer_rejects_unsupported_claim()
    test_consensus_merge_basic()
    test_consensus_adds_verify_tags()
    test_full_pipeline()
    test_full_pipeline_with_bad_article()
    test_run_consensus_global()
    test_modules_import_consensus()
    test_critique_no_content()
    test_fact_no_content()
    test_entropy_no_content()
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    test_all()
