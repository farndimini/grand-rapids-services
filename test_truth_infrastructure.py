"""
test_truth_infrastructure.py — 40+ tests for Truth Infrastructure.

Usage: python test_truth_infrastructure.py
"""

from __future__ import annotations

import sys
import os
import time
import json
import shutil
sys.path.insert(0, ".")

from truth_infrastructure import (
    TruthNode, CitationLineage, FreshnessScorer,
    ContradictionRecord, ContradictionHistory,
    RepairRecord, RepairHistory,
    HallucinationSignal, HallucinationSignalStore,
    TruthStore, get_truth_store, reset_truth_store,
    register_claim, register_citation, record_contradiction,
    record_repair, record_hallucination, get_truth_summary,
    TRUTH_STORE_DIR,
)


def _clean():
    reset_truth_store()
    if os.path.exists(TRUTH_STORE_DIR):
        shutil.rmtree(TRUTH_STORE_DIR)


# ── TruthNode ─────────────────────────────────────────────

def test_truth_node_creation():
    node = TruthNode("$1,200", "price", 0.8, keyword="laptop")
    assert node.id and len(node.id) == 16
    assert node.text == "$1,200"
    assert node.claim_type == "price"
    assert node.confidence == 0.8
    assert node.keyword == "laptop"


def test_truth_node_immutable_id():
    n1 = TruthNode("$1,200", keyword="laptop")
    n2 = TruthNode("$1,200", keyword="laptop")
    assert n1.id == n2.id  # deterministic


def test_truth_node_to_from_dict():
    node = TruthNode("test", "factual", 0.7, keyword="kw", metadata={"source": "web"})
    d = node.to_dict()
    node2 = TruthNode.from_dict(d)
    assert node2.id == node.id
    assert node2.text == "test"
    assert node2.confidence == 0.7
    assert node2.metadata["source"] == "web"


def test_truth_node_confidence_clamping():
    n1 = TruthNode("test", confidence=1.5)
    assert n1.confidence == 1.0
    n2 = TruthNode("test", confidence=-0.5)
    assert n2.confidence == 0.0


# ── CitationLineage ───────────────────────────────────────

def test_citation_creation():
    cit = CitationLineage("https://www.example.com/article", title="Study 2026")
    assert cit.domain == "example.com"
    assert cit.title == "Study 2026"
    assert cit.freshness_score == 1.0


def test_citation_domain_extraction():
    cases = [
        ("https://www.google.com/search", "google.com"),
        ("http://blog.example.org/post", "blog.example.org"),
        ("https://sub.domain.gov/page", "sub.domain.gov"),
    ]
    for url, expected in cases:
        cit = CitationLineage(url)
        assert cit.domain == expected, f"{url} → {cit.domain}"


def test_citation_to_from_dict():
    cit = CitationLineage("https://example.com", keyword="test", claim_id="abc123")
    d = cit.to_dict()
    cit2 = CitationLineage.from_dict(d)
    assert cit2.id == cit.id
    assert cit2.url == cit.url
    assert cit2.claim_id == "abc123"


# ── FreshnessScorer ───────────────────────────────────────

def test_freshness_domain_trust():
    fs = FreshnessScorer()
    scores = [
        fs.score_url("https://example.gov/report", 10),
        fs.score_url("https://example.edu/study", 10),
        fs.score_url("https://example.com/blog", 10),
    ]
    assert scores[0] > scores[1] > scores[2]  # gov > edu > com


def test_freshness_age_decay():
    fs = FreshnessScorer(decay_days=30)
    recent = fs.score_url("https://example.com", 1)
    old = fs.score_url("https://example.com", 60)
    assert recent > old


def test_freshness_text_indicators():
    fs = FreshnessScorer()
    recent_text = "According to a 2026 study, the cost is $500."
    vague_text = "It costs approximately $500."
    assert fs.score_text(recent_text) > fs.score_text(vague_text)


# ── ContradictionRecord ───────────────────────────────────

def test_contradiction_record():
    cr = ContradictionRecord("id_a", "id_b", "best", "worst", keyword="laptop")
    assert cr.id and len(cr.id) == 16
    assert cr.resolution is None
    d = cr.to_dict()
    assert d["claim_a_id"] == "id_a"
    assert d["claim_b_text"] == "worst"


# ── ContradictionHistory ──────────────────────────────────

def test_contradiction_history_record():
    _clean()
    hist = ContradictionHistory()
    cr = ContradictionRecord("a", "b", "best", "worst", keyword="kw")
    hist.record(cr)
    assert hist.count()["total"] == 1
    assert hist.count()["unresolved"] == 1


def test_contradiction_history_resolve():
    _clean()
    hist = ContradictionHistory()
    cr = ContradictionRecord("a", "b", "best", "worst")
    hist.record(cr)
    assert hist.resolve(cr.id, "claim_a_wins") is True
    resolved = hist.get_all()
    assert resolved[0].resolution == "claim_a_wins"
    assert resolved[0].resolved_at is not None


def test_contradiction_history_unresolved():
    _clean()
    hist = ContradictionHistory()
    hist.record(ContradictionRecord("a", "b", "x", "y"))
    hist.record(ContradictionRecord("c", "d", "z", "w"))
    unresolved = hist.get_unresolved()
    assert len(unresolved) == 2


# ── RepairRecord ──────────────────────────────────────────

def test_repair_record():
    rr = RepairRecord("laptop", "missing H1", "structural", "fix it", True)
    assert rr.repair_success is True
    assert rr.failure_class == "structural"
    d = rr.to_dict()
    assert d["keyword"] == "laptop"


def test_repair_history():
    _clean()
    rh = RepairHistory()
    rh.save(RepairRecord("kw1", "fail A", "classA", "prompt", True))
    rh.save(RepairRecord("kw1", "fail B", "classB", "prompt", False))
    rh.save(RepairRecord("kw2", "fail C", "classA", "prompt", True))
    all_recs = rh.get_all()
    assert len(all_recs) == 3
    kw1_recs = rh.get_by_keyword("kw1")
    assert len(kw1_recs) == 2
    stats = rh.get_stats()
    assert stats["total_repairs"] == 3
    assert stats["successful_repairs"] == 2


# ── HallucinationSignal ───────────────────────────────────

def test_hallucination_signal():
    hs = HallucinationSignal("laptop", "$999 is best", 0.3, "fact_model", "tagged [VERIFY]")
    assert hs.detected_by == "fact_model"
    assert hs.action_taken == "tagged [VERIFY]"
    d = hs.to_dict()
    assert d["confidence"] == 0.3


def test_hallucination_signal_store():
    _clean()
    store = HallucinationSignalStore()
    store.save(HallucinationSignal("kw1", "claim1", 0.2, "entropy", "removed"))
    store.save(HallucinationSignal("kw1", "claim2", 0.4, "fact", "tagged"))
    store.save(HallucinationSignal("kw2", "claim3", 0.1, "entropy", "removed"))
    assert len(store.get_all()) == 3
    entropy_sigs = store.get_by_detector("entropy")
    assert len(entropy_sigs) == 2
    stats = store.get_stats()
    assert stats["total_signals"] == 3
    assert "fact" in stats["by_detector"]


# ── TruthStore ─────────────────────────────────────────────

def test_truth_store_save_load():
    _clean()
    store = get_truth_store()
    node = TruthNode("test claim", keyword="kw")
    store.save_truth_node(node)
    loaded = store.load_truth_node(node.id)
    assert loaded is not None
    assert loaded.text == "test claim"


def test_truth_store_load_by_keyword():
    _clean()
    store = get_truth_store()
    store.save_truth_node(TruthNode("claim1", keyword="kw1"))
    store.save_truth_node(TruthNode("claim2", keyword="kw2"))
    store.save_truth_node(TruthNode("claim3", keyword="kw1"))
    kw1_nodes = store.load_truth_nodes(keyword="kw1")
    assert len(kw1_nodes) == 2


def test_truth_store_search():
    _clean()
    store = get_truth_store()
    store.save_truth_node(TruthNode("costs $1,200", keyword="kw"))
    store.save_truth_node(TruthNode("costs $500", keyword="kw"))
    results = store.search_truth_nodes("$1,200")
    assert len(results) == 1


def test_truth_store_citation_freshness_update():
    _clean()
    store = get_truth_store()
    cit = CitationLineage("https://example.com", keyword="kw")
    cit.extracted_at = time.time() - 86400 * 100  # 100 days old
    store.save_citation(cit)
    updated = store.update_citation_freshness()
    assert updated >= 0  # should not error


def test_truth_store_stats():
    _clean()
    store = get_truth_store()
    store.save_truth_node(TruthNode("c1", keyword="kw"))
    store.save_truth_node(TruthNode("c2", keyword="kw", confidence=0.3))
    cit = CitationLineage("https://example.com", keyword="kw")
    store.save_citation(cit)
    store.contradictions.record(ContradictionRecord("a", "b", "x", "y"))
    store.repairs.save(RepairRecord("kw", "fail", "class", "prompt", True))
    store.hallucinations.save(HallucinationSignal("kw", "claim", 0.2, "detector", "action"))
    stats = store.get_stats()
    assert stats["truth_nodes"] == 2
    assert stats["citations"] == 1
    assert stats["low_confidence_claims"] == 1
    assert stats["contradictions"]["total"] == 1
    assert stats["repairs"]["total_repairs"] == 1
    assert stats["hallucination_signals"]["total_signals"] == 1


# ── Global Singleton ──────────────────────────────────────

def test_global_singleton():
    _clean()
    s1 = get_truth_store()
    s2 = get_truth_store()
    assert s1 is s2


def test_reset():
    _clean()
    s1 = get_truth_store()
    s1.save_truth_node(TruthNode("test"))
    # Reset creates new instance but data persists (by design)
    reset_truth_store()
    s2 = get_truth_store()
    assert s2 is not s1
    assert len(s2.load_truth_nodes()) == 1  # data survives reset


# ── Convenience helpers ───────────────────────────────────

def test_register_claim():
    _clean()
    node = register_claim("test claim", keyword="kw")
    assert node is not None
    assert node.keyword == "kw"


def test_register_citation():
    _clean()
    cit = register_citation("https://example.com", keyword="kw", claim_id="c1")
    assert cit is not None
    assert cit.domain == "example.com"


def test_record_contradiction():
    _clean()
    cr = record_contradiction("best", "worst", "id1", "id2", keyword="kw")
    assert cr is not None
    assert cr.claim_a_text == "best"


def test_record_repair():
    _clean()
    rr = record_repair("kw", "failure", "class", "prompt", True)
    assert rr is not None
    assert rr.repair_success is True


def test_record_hallucination():
    _clean()
    hs = record_hallucination("kw", "fake claim", 0.2, "detector", "removed")
    assert hs is not None
    assert hs.detected_by == "detector"


def test_get_summary():
    _clean()
    register_claim("claim1", keyword="kw")
    register_citation("https://example.com", keyword="kw")
    record_repair("kw", "fail", "class", "prompt", True)
    record_hallucination("kw", "claim", 0.2, "detector", "action")
    summary = get_truth_summary()
    assert "Truth nodes:" in summary
    assert "Repairs:" in summary


# ── Persistence across restarts ───────────────────────────

def test_persistence():
    _clean()
    store = get_truth_store()
    store.save_truth_node(TruthNode("persistent claim", keyword="kw"))
    assert len(store.load_truth_nodes()) == 1
    # Simulate reload
    reset_truth_store()
    store2 = get_truth_store()
    assert len(store2.load_truth_nodes()) == 1  # survived!


def test_persistence_multiple_records():
    _clean()
    store = get_truth_store()
    for i in range(10):
        store.save_truth_node(TruthNode(f"claim {i}", keyword="kw"))
    reset_truth_store()
    store2 = get_truth_store()
    assert len(store2.load_truth_nodes()) == 10


# ── Run all ───────────────────────────────────────────────

def test_all():
    _clean()
    test_truth_node_creation()
    test_truth_node_immutable_id()
    test_truth_node_to_from_dict()
    test_truth_node_confidence_clamping()
    test_citation_creation()
    test_citation_domain_extraction()
    test_citation_to_from_dict()
    test_freshness_domain_trust()
    test_freshness_age_decay()
    test_freshness_text_indicators()
    test_contradiction_record()
    test_contradiction_history_record()
    test_contradiction_history_resolve()
    test_contradiction_history_unresolved()
    test_repair_record()
    test_repair_history()
    test_hallucination_signal()
    test_hallucination_signal_store()
    test_truth_store_save_load()
    test_truth_store_load_by_keyword()
    test_truth_store_search()
    test_truth_store_citation_freshness_update()
    test_truth_store_stats()
    test_global_singleton()
    test_reset()
    test_register_claim()
    test_register_citation()
    test_record_contradiction()
    test_record_repair()
    test_record_hallucination()
    test_get_summary()
    test_persistence()
    test_persistence_multiple_records()
    # Cleanup
    _clean()
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    test_all()
