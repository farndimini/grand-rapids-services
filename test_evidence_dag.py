"""
test_evidence_dag.py — 30+ tests for Evidence DAG.

Usage: python test_evidence_dag.py
"""

from __future__ import annotations

import sys
import time
sys.path.insert(0, ".")

from evidence_dag import (
    ClaimNode, EvidenceDAG, DAGBuilder, DAGVerifier,
    DAGConfidencePropagator, build_evidence_dag,
    get_global_dag, reset_global_dag,
    CLAIM_TYPE_PRICE, CLAIM_TYPE_PERCENTAGE, CLAIM_TYPE_YEAR,
    CLAIM_TYPE_SUPERLATIVE, RELATION_SUPPORTS, RELATION_CONTRADICTS,
)


SAMPLE_ARTICLE = """<h1>Best Laptop 2026</h1>
<p>According to recent studies, this laptop costs $1,200 which offers the best value.</p>
<p>It delivers 25% more performance than the previous model. The worst aspect is its weight.</p>
<p>It was released in 2025 and remains the most popular choice.</p>
<p>At $1,500 the premium model offers 40% more speed. This is always reliable.</p>
"""


# ── ClaimNode ─────────────────────────────────────────────

def test_claim_node_creation():
    node = ClaimNode("$1,200", CLAIM_TYPE_PRICE, confidence=0.8)
    assert node.id is not None and len(node.id) == 12
    assert node.text == "$1,200"
    assert node.claim_type == CLAIM_TYPE_PRICE
    assert node.confidence == 0.8


def test_claim_node_confidence_clamping():
    node = ClaimNode("test", confidence=1.5)
    assert node.confidence == 1.0
    node2 = ClaimNode("test2", confidence=-0.5)
    assert node2.confidence == 0.0


def test_claim_node_temporal_freshness():
    node = ClaimNode("test", extracted_at=time.time())
    assert node.temporal_freshness() > 0.99  # near 1.0
    old = ClaimNode("old", extracted_at=time.time() - 86400 * 200)  # 200 days
    assert old.temporal_freshness() == 0.0


def test_claim_node_effective_confidence():
    node = ClaimNode("test", confidence=0.8)
    node.serp_consensus = 0.5
    node.verifier_score = 0.9
    eff = node.effective_confidence()
    assert 0.0 <= eff <= 1.0
    assert eff != node.confidence  # should be modified by weights


def test_claim_node_to_dict():
    node = ClaimNode("$500", CLAIM_TYPE_PRICE, confidence=0.7,
                      source_url="https://example.com")
    d = node.to_dict()
    assert d["id"] == node.id
    assert d["text"] == "$500"
    assert d["claim_type"] == CLAIM_TYPE_PRICE
    assert d["source_url"] == "https://example.com"
    assert "effective_confidence" in d
    assert "temporal_freshness" in d


# ── EvidenceDAG ───────────────────────────────────────────

def test_dag_empty():
    dag = EvidenceDAG()
    assert dag.claim_count() == 0
    assert dag.edge_count() == 0
    assert dag.verify_acyclic() is True


def test_dag_add_claim():
    dag = EvidenceDAG()
    node = ClaimNode("$1,000", CLAIM_TYPE_PRICE)
    dag.add_claim(node)
    assert dag.claim_count() == 1
    assert dag.get_claim(node.id) is node


def test_dag_add_claim_dedup():
    dag = EvidenceDAG()
    n1 = ClaimNode("$1,000", CLAIM_TYPE_PRICE, confidence=0.5)
    n2 = ClaimNode("$1,000", CLAIM_TYPE_PRICE, confidence=0.9)  # same text = same id
    dag.add_claim(n1)
    dag.add_claim(n2)
    assert dag.claim_count() == 1
    assert dag.get_claim(n1.id).confidence == 0.9  # higher confidence wins


def test_dag_add_edge_support():
    dag = EvidenceDAG()
    a = ClaimNode("base", confidence=0.5)
    b = ClaimNode("supported", confidence=0.5)
    dag.add_claim(a)
    dag.add_claim(b)
    assert dag.add_edge(a.id, b.id, RELATION_SUPPORTS) is True
    assert dag.edge_count() == 1
    assert a.id in dag.nodes[b.id].supported_by


def test_dag_add_edge_contradicts():
    dag = EvidenceDAG()
    a = ClaimNode("best", CLAIM_TYPE_SUPERLATIVE)
    b = ClaimNode("worst", CLAIM_TYPE_SUPERLATIVE)
    dag.add_claim(a)
    dag.add_claim(b)
    assert dag.add_edge(a.id, b.id, RELATION_CONTRADICTS) is True
    # Contradictions are bidirectional
    assert a.id in dag.nodes[b.id].contradicted_by
    assert b.id in dag.nodes[a.id].contradicted_by


def test_dag_rejects_cycle():
    dag = EvidenceDAG()
    a = ClaimNode("a")
    b = ClaimNode("b")
    c = ClaimNode("c")
    for n in (a, b, c):
        dag.add_claim(n)
    dag.add_edge(a.id, b.id, RELATION_SUPPORTS)
    dag.add_edge(b.id, c.id, RELATION_SUPPORTS)
    # c -> a would create cycle a->b->c->a
    assert dag.add_edge(c.id, a.id, RELATION_SUPPORTS) is False


def test_dag_missing_node_edge():
    dag = EvidenceDAG()
    assert dag.add_edge("nope", "none", RELATION_SUPPORTS) is False


def test_dag_get_supporting_chain():
    dag = EvidenceDAG()
    a = ClaimNode("root")
    b = ClaimNode("mid")
    c = ClaimNode("leaf")
    for n in (a, b, c):
        dag.add_claim(n)
    dag.add_edge(a.id, b.id, RELATION_SUPPORTS)
    dag.add_edge(b.id, c.id, RELATION_SUPPORTS)
    chain = dag.get_supporting_chain(c.id)
    assert len(chain) == 2  # a and b


def test_dag_get_contradictions():
    dag = EvidenceDAG()
    a = ClaimNode("best", CLAIM_TYPE_SUPERLATIVE)
    b = ClaimNode("worst", CLAIM_TYPE_SUPERLATIVE)
    dag.add_claim(a)
    dag.add_claim(b)
    dag.add_edge(a.id, b.id, RELATION_CONTRADICTS)
    contra = dag.get_contradictions(a.id)
    assert len(contra) >= 1
    assert contra[0].id == b.id


def test_dag_propagate_confidence():
    dag = EvidenceDAG()
    a = ClaimNode("base", confidence=0.9)
    b = ClaimNode("target", confidence=0.3)
    c = ClaimNode("contra", confidence=0.8)
    for n in (a, b, c):
        dag.add_claim(n)
    dag.add_edge(a.id, b.id, RELATION_SUPPORTS)
    dag.add_edge(c.id, b.id, RELATION_CONTRADICTS)
    updates = dag.propagate_confidence()
    assert updates[b.id] != 0.3  # modified by propagation


def test_dag_verify_acyclic_with_edges():
    dag = EvidenceDAG()
    a = ClaimNode("a")
    b = ClaimNode("b")
    dag.add_claim(a)
    dag.add_claim(b)
    dag.add_edge(a.id, b.id, RELATION_SUPPORTS)
    assert dag.verify_acyclic() is True


def test_dag_to_dict():
    dag = EvidenceDAG()
    dag.add_claim(ClaimNode("$100", CLAIM_TYPE_PRICE))
    d = dag.to_dict()
    assert d["claim_count"] == 1
    assert d["is_acyclic"] is True
    assert "nodes" in d
    assert "edges" in d


def test_dag_to_json():
    dag = EvidenceDAG()
    dag.add_claim(ClaimNode("test"))
    js = dag.to_json()
    assert '"claim_count": 1' in js


# ── DAGBuilder ────────────────────────────────────────────

def test_builder_empty():
    builder = DAGBuilder()
    dag = builder.build("")
    assert dag.claim_count() == 0


def test_builder_extracts_prices():
    builder = DAGBuilder()
    dag = builder.build("Costs $500 and $1,200 respectively.")
    price_nodes = [n for n in dag.nodes.values() if n.claim_type == CLAIM_TYPE_PRICE]
    assert len(price_nodes) >= 2


def test_builder_extracts_percentages():
    builder = DAGBuilder()
    dag = builder.build("Improves by 25% and reduces by 10%.")
    pct_nodes = [n for n in dag.nodes.values() if n.claim_type == CLAIM_TYPE_PERCENTAGE]
    assert len(pct_nodes) >= 2


def test_builder_extracts_years():
    builder = DAGBuilder()
    dag = builder.build("Released in 2025, updated in 2026.")
    yr_nodes = [n for n in dag.nodes.values() if n.claim_type == CLAIM_TYPE_YEAR]
    assert len(yr_nodes) >= 2


def test_builder_extracts_superlatives():
    builder = DAGBuilder()
    dag = builder.build("This is the best laptop and the worst choice.")
    sup_nodes = [n for n in dag.nodes.values() if n.claim_type == CLAIM_TYPE_SUPERLATIVE]
    assert len(sup_nodes) >= 2


def test_builder_full_article():
    builder = DAGBuilder()
    dag = builder.build(SAMPLE_ARTICLE, "https://example.com")
    assert dag.claim_count() >= 6
    for node in dag.nodes.values():
        if node.source_url:
            assert node.source_url == "https://example.com"


# ── DAGVerifier ───────────────────────────────────────────

def test_verifier_detects_contradictions():
    dag = EvidenceDAG()
    dag.add_claim(ClaimNode("best", CLAIM_TYPE_SUPERLATIVE))
    dag.add_claim(ClaimNode("worst", CLAIM_TYPE_SUPERLATIVE))
    verifier = DAGVerifier()
    verifier.verify(dag)
    assert dag.edge_count() >= 1


def test_verifier_propagates():
    dag = EvidenceDAG()
    a = ClaimNode("base", confidence=0.9)
    b = ClaimNode("target", confidence=0.3)
    for n in (a, b):
        dag.add_claim(n)
    dag.edges.append((a.id, b.id, RELATION_SUPPORTS))
    dag.nodes[b.id].supported_by.append(a.id)
    verifier = DAGVerifier()
    verifier.verify(dag)
    # After propagation, target confidence should have changed
    updated = dag.nodes[b.id].confidence
    assert updated != 0.3  # should have been boosted


# ── DAGConfidencePropagator ───────────────────────────────

def test_propagator_basic():
    dag = EvidenceDAG()
    a = ClaimNode("base", confidence=0.9)
    b = ClaimNode("target", confidence=0.3)
    for n in (a, b):
        dag.add_claim(n)
    dag.edges.append((a.id, b.id, RELATION_SUPPORTS))
    dag.nodes[b.id].supported_by.append(a.id)
    prop = DAGConfidencePropagator()
    prop.propagate(dag, iterations=3)
    assert dag.nodes[b.id].confidence > 0.3


def test_propagator_empty():
    dag = EvidenceDAG()
    prop = DAGConfidencePropagator()
    result = prop.propagate(dag)
    assert result.claim_count() == 0


# ── build_evidence_dag ────────────────────────────────────

def test_build_evidence_dag_full():
    dag = build_evidence_dag(SAMPLE_ARTICLE, "https://example.com")
    assert dag.claim_count() >= 6
    assert dag.verify_acyclic() is True


def test_build_evidence_dag_no_source():
    dag = build_evidence_dag("Costs $100.")
    assert dag.claim_count() == 1


# ── Global singleton ──────────────────────────────────────

def test_global_dag():
    reset_global_dag()
    dag = get_global_dag()
    assert dag.claim_count() == 0
    dag2 = get_global_dag()
    assert dag2 is dag  # same instance


def test_reset_global():
    reset_global_dag()
    d1 = get_global_dag()
    d1.add_claim(ClaimNode("test"))
    assert d1.claim_count() == 1
    reset_global_dag()
    d2 = get_global_dag()
    assert d2.claim_count() == 0
    assert d2 is not d1


# ── Edge cases ────────────────────────────────────────────

def test_get_nonexistent_claim():
    dag = EvidenceDAG()
    assert dag.get_claim("nope") is None


def test_get_supporting_chain_nonexistent():
    dag = EvidenceDAG()
    assert dag.get_supporting_chain("nope") == []


def test_get_contradictions_nonexistent():
    dag = EvidenceDAG()
    assert dag.get_contradictions("nope") == []


def test_consensus_groups_empty():
    dag = EvidenceDAG()
    assert dag.get_consensus_groups() == []


def test_build_evidence_dag_empty():
    dag = build_evidence_dag("", verify=True, propagate=True)
    assert dag.claim_count() == 0


# ── Run all ───────────────────────────────────────────────

def test_all():
    test_claim_node_creation()
    test_claim_node_confidence_clamping()
    test_claim_node_temporal_freshness()
    test_claim_node_effective_confidence()
    test_claim_node_to_dict()
    test_dag_empty()
    test_dag_add_claim()
    test_dag_add_claim_dedup()
    test_dag_add_edge_support()
    test_dag_add_edge_contradicts()
    test_dag_rejects_cycle()
    test_dag_missing_node_edge()
    test_dag_get_supporting_chain()
    test_dag_get_contradictions()
    test_dag_propagate_confidence()
    test_dag_verify_acyclic_with_edges()
    test_dag_to_dict()
    test_dag_to_json()
    test_builder_empty()
    test_builder_extracts_prices()
    test_builder_extracts_percentages()
    test_builder_extracts_years()
    test_builder_extracts_superlatives()
    test_builder_full_article()
    test_verifier_detects_contradictions()
    test_verifier_propagates()
    test_propagator_basic()
    test_propagator_empty()
    test_build_evidence_dag_full()
    test_build_evidence_dag_no_source()
    test_global_dag()
    test_reset_global()
    test_get_nonexistent_claim()
    test_get_supporting_chain_nonexistent()
    test_get_contradictions_nonexistent()
    test_consensus_groups_empty()
    test_build_evidence_dag_empty()
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    test_all()
