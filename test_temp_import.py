"""Quick import check."""
import sys, os, shutil, time, math
sys.path.insert(0, '.')
from generation_state import GenerationState
from temporal_intelligence import (
    TemporalClaim, FreshnessDecayEngine, CitationExpiryTracker,
    TemporalContradictionTracker, RecencyPropagation,
    HistoricalTruthSnapshot, HistoricalTruthStore,
    TemporalIntelligenceEngine, get_temporal_engine, reset_temporal_engine,
    DECAY_LAMBDA_DEFAULT,
)
print("All imports OK")

# GenerationState
gs = GenerationState("test keyword", "test-model")
gs.article = "<h1>Test</h1><p>Content.</p>"
gs.word_count = 10
gs.mark_stage("test")
assert gs.keyword == "test keyword"
d = gs.to_dict()
assert d["word_count"] == 10
gs.add_event("test.event", {"key": "val"})
assert len(gs.events) == 1
print(f"GenState: {gs.summary()}")

# TemporalClaim
tc = TemporalClaim("$1,200 is the best price", "price", 0.9)
assert tc.effective_confidence() <= 0.9
old = TemporalClaim("old data", "factual", 0.9)
old.birth_time = time.time() - 86400 * 200
assert old.is_stale()
print(f"TemporalClaim: {tc}")

# FreshnessDecayEngine
fde = FreshnessDecayEngine()
result = fde.decay_claim(tc)
assert "effective_confidence" in result
assert "stale" in result
niche_lambda = fde.adjust_lambda_for_niche("technology")
assert niche_lambda > DECAY_LAMBDA_DEFAULT

# CitationExpiryTracker
cet = CitationExpiryTracker(max_age_days=30)
r = cet.check_citation("https://example.com", time.time() - 86400 * 60)
assert r["expired"] is True
assert "VERIFY" in r["action"]

# TemporalContradictionTracker
tct = TemporalContradictionTracker()
cr = tct.record_contradiction("best", "worst", "id1", "id2", "kw")
assert cr["claim_a_text"] == "best"
assert tct.get_unresolved()[0]["claim_a_text"] == "best"
tct.resolve(cr["id"], "claim_a_wins")
assert tct.get_unresolved() == []

# RecencyPropagation
rp = RecencyPropagation()
a = TemporalClaim("base", confidence=0.9)
b = TemporalClaim("target", confidence=0.5)
a.source_freshness = 0.8
b.source_freshness = 0.5
rp.propagate([a, b], [(a.id, b.id, "supports")])
assert b.source_freshness > 0.5  # boosted

# HistoricalTruthStore
hts = HistoricalTruthStore()
snap = hts.take_snapshot("kw", [tc])
assert snap.avg_confidence > 0
snap2 = hts.take_snapshot("kw", [old])
comp = hts.compare(snap2, snap)
assert "confidence_change" in comp

# TemporalIntelligenceEngine
tie = TemporalIntelligenceEngine()
report = tie.process_article("<p>test</p>", "kw", claims=[tc, old], niche="technology")
assert report["effective_confidence"] > 0
assert len(report["decayed_claims"]) == 2

# Singleton
reset_temporal_engine()
e1 = get_temporal_engine()
e2 = get_temporal_engine()
assert e1 is e2

print("\nALL TESTS PASSED")
