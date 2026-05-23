"""
test_temporal_intelligence.py — 30+ tests for Temporal Intelligence.

Usage: python test_temporal_intelligence.py
"""
from __future__ import annotations
import sys, time, math
sys.path.insert(0, '.')
from temporal_intelligence import (
    TemporalClaim, FreshnessDecayEngine, CitationExpiryTracker,
    TemporalContradictionTracker, RecencyPropagation,
    HistoricalTruthSnapshot, HistoricalTruthStore,
    TemporalIntelligenceEngine, get_temporal_engine, reset_temporal_engine,
    DECAY_LAMBDA_DEFAULT, DECAY_LAMBDA_FAST, DECAY_LAMBDA_SLOW,
)
from generation_state import GenerationState


# ── TemporalClaim ──

def test_temporal_claim_creation():
    tc = TemporalClaim("$1,200", "price", 0.8, keyword="laptop")
    assert tc.id and len(tc.id) == 16
    assert tc.claim_type == "price"
    assert tc.decay_lambda == DECAY_LAMBDA_FAST

def test_effective_confidence_fresh():
    tc = TemporalClaim("test", "factual", 1.0)
    assert tc.effective_confidence() == 1.0  # just born

def test_effective_confidence_decays():
    tc = TemporalClaim("test", "factual", 1.0)
    tc.birth_time = time.time() - 86400 * 100  # 100 days ago
    assert tc.effective_confidence() < 0.5

def test_is_stale():
    tc = TemporalClaim("old", "factual", 0.5)
    tc.birth_time = time.time() - 86400 * 200
    assert tc.is_stale()
    tc.birth_time = time.time()
    assert not tc.is_stale()

def test_to_dict():
    tc = TemporalClaim("test", keyword="kw")
    d = tc.to_dict()
    assert "id" in d and "effective_confidence" in d and "age_days" in d


# ── FreshnessDecayEngine ──

def test_decay_claim():
    fde = FreshnessDecayEngine()
    tc = TemporalClaim("test", "factual", 0.9)
    tc.birth_time = time.time() - 86400 * 50
    result = fde.decay_claim(tc)
    assert result["original_confidence"] == 0.9
    assert result["effective_confidence"] < 0.9
    assert "stale" in result

def test_decay_all():
    fde = FreshnessDecayEngine()
    claims = [TemporalClaim(f"c{i}", "factual") for i in range(5)]
    results = fde.decay_all(claims)
    assert len(results) == 5

def test_niche_adjustment():
    fde = FreshnessDecayEngine()
    assert fde.adjust_lambda_for_niche("technology") > DECAY_LAMBDA_DEFAULT
    assert fde.adjust_lambda_for_niche("legal") < DECAY_LAMBDA_DEFAULT
    assert fde.adjust_lambda_for_niche("unknown") == DECAY_LAMBDA_DEFAULT


# ── CitationExpiryTracker ──

def test_citation_valid():
    cet = CitationExpiryTracker(max_age_days=30)
    r = cet.check_citation("https://example.com", time.time() - 5)
    assert r["expired"] is False
    assert r["action"] == "valid"

def test_citation_expired():
    cet = CitationExpiryTracker(max_age_days=30)
    r = cet.check_citation("https://old.com", time.time() - 86400 * 60)
    assert r["expired"] is True
    assert "VERIFY" in r["action"]

def test_citation_batch():
    cet = CitationExpiryTracker(max_age_days=30)
    cites = [
        {"url": "https://fresh.com", "extracted_at": time.time() - 5},
        {"url": "https://old.com", "extracted_at": time.time() - 86400 * 90},
    ]
    results = cet.check_citations_batch(cites)
    assert len(results) == 2
    assert results[0]["expired"] is False
    assert results[1]["expired"] is True

def test_expire_in_article():
    cet = CitationExpiryTracker(max_age_days=30)
    article = 'Read more at https://old.com for details.'
    cites = [{"url": "https://old.com", "expired": True, "age_days": 60, "domain": "old.com"}]
    modified = cet.expire_in_article(article, cites)
    assert "[VERIFY" in modified


# ── TemporalContradictionTracker ──

def test_contradiction_record():
    tct = TemporalContradictionTracker()
    r = tct.record_contradiction("best", "worst", "id1", "id2", "kw")
    assert r["claim_a_text"] == "best"
    assert len(tct.get_recent()) == 1

def test_contradiction_resolve():
    tct = TemporalContradictionTracker()
    r = tct.record_contradiction("a", "b", "id1", "id2")
    assert tct.get_unresolved()[0]["id"] == r["id"]
    tct.resolve(r["id"], "claim_a_wins")
    assert tct.get_unresolved() == []

def test_contradiction_rate():
    tct = TemporalContradictionTracker()
    r = tct.record_contradiction("x", "y", "id1", "id2")
    tct.resolve(r["id"], "claim_a_wins")
    assert tct.contradiction_rate(days=1) > 0


# ── RecencyPropagation ──

def test_propagation_support():
    rp = RecencyPropagation()
    a = TemporalClaim("base", confidence=0.9)
    b = TemporalClaim("target", confidence=0.5)
    a.source_freshness = 0.8
    b.source_freshness = 0.5
    rp.propagate([a, b], [(a.id, b.id, "supports")])
    assert b.source_freshness > 0.5

def test_propagation_contradiction():
    rp = RecencyPropagation()
    a = TemporalClaim("a", confidence=0.9)
    b = TemporalClaim("b", confidence=0.9)
    a.source_freshness = 0.8
    b.source_freshness = 0.8
    rp.propagate([a, b], [(a.id, b.id, "contradicts")])
    assert a.source_freshness < 0.8
    assert b.source_freshness < 0.8


# ── HistoricalTruthStore ──

def test_snapshot():
    tc = TemporalClaim("test", confidence=0.8)
    snap = HistoricalTruthSnapshot("kw", [tc])
    assert snap.avg_confidence > 0
    assert snap.stale_count == 0

def test_store_snapshot():
    hts = HistoricalTruthStore()
    tc = TemporalClaim("test")
    s1 = hts.take_snapshot("kw", [tc])
    s2 = hts.take_snapshot("kw", [tc])
    assert len(hts.get_snapshots("kw")) == 2

def test_compare_snapshots():
    hts = HistoricalTruthStore()
    fresh = TemporalClaim("fresh", confidence=0.9)
    stale = TemporalClaim("stale", confidence=0.9)
    stale.birth_time = time.time() - 86400 * 200
    s1 = hts.take_snapshot("kw", [fresh])
    s2 = hts.take_snapshot("kw", [stale])
    comp = hts.compare(s2, s1)
    assert comp["confidence_change"] < 0


# ── TemporalIntelligenceEngine ──

def test_engine_process():
    tie = TemporalIntelligenceEngine()
    tc = TemporalClaim("$1,200", "price", 0.9)
    tc.birth_time = time.time() - 86400 * 50
    report = tie.process_article("<p>test</p>", "laptop", claims=[tc], niche="technology")
    assert report["effective_confidence"] < 0.9
    assert len(report["decayed_claims"]) == 1

def test_engine_with_citations():
    tie = TemporalIntelligenceEngine()
    cites = [{"url": "https://old.com", "extracted_at": time.time() - 86400 * 200}]
    report = tie.process_article("<p>test</p>", "kw", citations=cites)
    assert len(report["expired_citations"]) == 1

def test_engine_with_edges():
    tie = TemporalIntelligenceEngine()
    a = TemporalClaim("base", confidence=0.9)
    b = TemporalClaim("target", confidence=0.5)
    a.source_freshness = 0.8
    a.birth_time = time.time() - 86400 * 10
    b.birth_time = time.time() - 86400 * 10
    report = tie.process_article("<p>test</p>", "kw", claims=[a, b],
                                  dag_edges=[(a.id, b.id, "supports")])
    assert report["effective_confidence"] > 0

def test_engine_summary():
    tie = TemporalIntelligenceEngine()
    report = tie.process_article("<p>test</p>", "kw")
    s = tie.get_summary(report)
    assert "Temporal:" in s


# ── Global singleton ──

def test_singleton():
    reset_temporal_engine()
    e1 = get_temporal_engine()
    e2 = get_temporal_engine()
    assert e1 is e2

def test_reset():
    reset_temporal_engine()
    e1 = get_temporal_engine()
    reset_temporal_engine()
    e2 = get_temporal_engine()
    assert e2 is not e1


# ── GenerationState ──

def test_generation_state():
    gs = GenerationState("kw", "model1")
    assert gs.keyword == "kw"
    assert gs.model == "model1"
    gs.article = "<h1>Test</h1>"
    gs.word_count = 5
    assert gs.to_dict()["word_count"] == 5

def test_state_timings():
    gs = GenerationState("kw")
    gs.mark_stage("phase1")
    dur = gs.duration_since("phase1")
    assert dur > 0

def test_state_events():
    gs = GenerationState("kw")
    gs.add_event("test.event", {"key": "val"})
    assert len(gs.events) == 1
    assert gs.events[0]["type"] == "test.event"

def test_state_summary():
    gs = GenerationState("test kw")
    s = gs.summary()
    assert "test kw" in s
    assert "Governance" in s


# ── Run all ──

def test_all():
    test_temporal_claim_creation()
    test_effective_confidence_fresh()
    test_effective_confidence_decays()
    test_is_stale()
    test_to_dict()
    test_decay_claim()
    test_decay_all()
    test_niche_adjustment()
    test_citation_valid()
    test_citation_expired()
    test_citation_batch()
    test_expire_in_article()
    test_contradiction_record()
    test_contradiction_resolve()
    test_contradiction_rate()
    test_propagation_support()
    test_propagation_contradiction()
    test_snapshot()
    test_store_snapshot()
    test_compare_snapshots()
    test_engine_process()
    test_engine_with_citations()
    test_engine_with_edges()
    test_engine_summary()
    test_singleton()
    test_reset()
    test_generation_state()
    test_state_timings()
    test_state_events()
    test_state_summary()
    print("ALL TESTS PASSED")

if __name__ == "__main__":
    test_all()
