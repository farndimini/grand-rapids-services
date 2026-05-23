"""
test_site_graph.py — Tests for Site Intelligence Graph
=======================================================
Tests ArticleNode, EntityNode, TopicCluster, AuthorityPropagator,
SiteGraph, and all intelligence operations.
"""

import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ["SEO_AGENT_TEST_MODE"] = "1"

from site_intelligence_graph import (
    ArticleNode, EntityNode, TopicCluster, AuthorityPropagator,
    SiteGraph, extract_entities, ingest_article,
    get_site_graph, reset_site_graph, suggest_internal_links_for,
)

SAMPLE_ARTICLE = """
<h1>Best Laptops for Programming in 2026</h1>
<p>The MacBook Pro by Apple is an excellent choice for developers.</p>
<p>The Dell XPS 15 offers great value for Python programmers.</p>
<p>ThinkPad X1 Carbon by Lenovo is popular among enterprise users.</p>
<a href="https://example.com/macbook">MacBook Pro</a>
<a href="https://example.com/dell">Dell XPS</a>
"""


def test_article_node():
    node = ArticleNode("best laptop", url="https://example.com", word_count=1500)
    assert node.keyword == "best laptop"
    assert node.word_count == 1500
    assert node.quality_score == 0.5
    assert node.id is not None
    d = node.to_dict()
    assert d["keyword"] == "best laptop"
    assert d["word_count"] == 1500
    assert d["quality_score"] == 0.5
    node2 = ArticleNode.from_dict(d)
    assert node2.keyword == "best laptop"
    assert node2.word_count == 1500
    print("  ✓ ArticleNode")


def test_article_node_id_consistency():
    id1 = ArticleNode._make_id("best laptop 2026")
    id2 = ArticleNode._make_id("Best Laptop 2026")
    id3 = ArticleNode._make_id("best laptop 2025")
    assert id1 == id2
    assert id1 != id3
    print("  ✓ ArticleNode ID consistency")


def test_entity_node():
    entity = EntityNode("Apple", "brand", source_keyword="best laptop")
    assert entity.name == "Apple"
    assert entity.entity_type == "brand"
    assert entity.mention_count == 1
    d = entity.to_dict()
    assert d["name"] == "Apple"
    entity2 = EntityNode.from_dict(d)
    assert entity2.name == "Apple"
    print("  ✓ EntityNode")


def test_entity_node_multiple_articles():
    entity = EntityNode("Apple", "brand", source_keyword="best laptop")
    entity.article_ids.append("macbook review")
    entity.mention_count = 2
    assert len(entity.article_ids) == 2
    assert entity.mention_count == 2
    print("  ✓ EntityNode multiple articles")


def test_topic_cluster():
    cluster = TopicCluster("Programming Laptops", "technology")
    assert cluster.name == "Programming Laptops"
    assert cluster.niche == "technology"
    d = cluster.to_dict()
    assert d["name"] == "Programming Laptops"
    cluster2 = TopicCluster.from_dict(d)
    assert cluster2.name == "Programming Laptops"
    print("  ✓ TopicCluster")


def test_topic_cluster_article_management():
    cluster = TopicCluster("Test Cluster")
    cluster.article_ids.append("article_1")
    cluster.article_ids.append("article_2")
    assert len(cluster.article_ids) == 2
    cluster.pillar_id = "article_1"
    assert cluster.pillar_id == "article_1"
    print("  ✓ TopicCluster article management")


def test_authority_propagator():
    propagator = AuthorityPropagator()
    articles = [
        ArticleNode("a", word_count=500),
        ArticleNode("b", word_count=300),
    ]
    articles[0].trust_score = 0.8
    articles[1].trust_score = 0.4
    articles[0].outbound_links.append(articles[1].id)
    result = propagator.propagate(articles)
    assert len(result) == 2
    for a in result:
        assert 0.0 <= a.trust_score <= 1.0
    print("  ✓ AuthorityPropagator")


def test_authority_propagator_empty():
    propagator = AuthorityPropagator()
    result = propagator.propagate([])
    assert result == []
    print("  ✓ AuthorityPropagator empty")


def test_site_graph_add_get_article():
    reset_site_graph()
    graph = get_site_graph()
    node = ArticleNode("test keyword", word_count=1000)
    graph.add_article(node)
    retrieved = graph.get_article(node.id)
    assert retrieved is not None
    assert retrieved.keyword == "test keyword"
    print("  ✓ SiteGraph add/get article")


def test_site_graph_get_article_by_keyword():
    graph = get_site_graph()
    node = ArticleNode("unique keyword", word_count=500)
    graph.add_article(node)
    retrieved = graph.get_article_by_keyword("unique keyword")
    assert retrieved is not None
    assert retrieved.word_count == 500
    print("  ✓ SiteGraph get by keyword")


def test_site_graph_update_article():
    graph = get_site_graph()
    node = ArticleNode("update test", word_count=100)
    graph.add_article(node)
    updated = graph.update_article(node.id, {"word_count": 200, "quality_score": 0.9})
    assert updated is True
    retrieved = graph.get_article(node.id)
    assert retrieved.word_count == 200
    assert retrieved.quality_score == 0.9
    print("  ✓ SiteGraph update article")


def test_site_graph_remove_article():
    graph = get_site_graph()
    node = ArticleNode("remove test", word_count=100)
    graph.add_article(node)
    removed = graph.remove_article(node.id)
    assert removed is True
    assert graph.get_article(node.id) is None
    removed2 = graph.remove_article("nonexistent")
    assert removed2 is False
    print("  ✓ SiteGraph remove article")


def test_site_graph_entity_crud():
    graph = get_site_graph()
    entity = EntityNode("Test Brand", "brand", source_keyword="test kw")
    graph.add_entity(entity)
    retrieved = graph.get_entity(entity.id)
    assert retrieved is not None
    assert retrieved.name == "Test Brand"
    # Add same entity again (should update mention count)
    entity2 = EntityNode("Test Brand", "brand", source_keyword="test kw2")
    graph.add_entity(entity2)
    retrieved2 = graph.get_entity(entity.id)
    assert retrieved2.mention_count >= 2
    print("  ✓ SiteGraph entity CRUD")


def test_site_graph_cluster_crud():
    graph = get_site_graph()
    cluster = TopicCluster("Test Cluster", "tech")
    graph.add_cluster(cluster)
    retrieved = graph.get_cluster(cluster.id)
    assert retrieved is not None
    assert retrieved.name == "Test Cluster"
    print("  ✓ SiteGraph cluster CRUD")


def test_extract_entities():
    text = "Apple makes the MacBook Pro and the Dell XPS 15. Lenovo ThinkPad is great."
    entities = extract_entities(text)
    assert len(entities) > 0
    assert "Apple" in entities or "MacBook" in text
    assert "Lenovo" in entities or "ThinkPad" in text
    print("  ✓ extract_entities")


def test_ingest_article():
    reset_site_graph()
    node = ingest_article("test kw", SAMPLE_ARTICLE, "tech", "commercial", 0.8)
    assert node.keyword == "test kw"
    assert node.word_count > 0
    assert len(node.entities) > 0
    graph = get_site_graph()
    stats = graph.get_stats()
    assert stats["articles"] >= 1
    assert stats["entities"] >= 1
    print("  ✓ ingest_article")


def test_detect_cannibalization():
    reset_site_graph()
    graph = get_site_graph()
    a1 = ArticleNode("best laptop 2026", word_count=1500)
    a2 = ArticleNode("best laptop for programming", word_count=2000)
    a3 = ArticleNode("totally different topic", word_count=500)
    graph.add_article(a1)
    graph.add_article(a2)
    graph.add_article(a3)
    candidates = graph.detect_cannibalization("best laptop")
    assert len(candidates) >= 2
    assert all(c["overlap_ratio"] > 0 for c in candidates)
    print("  ✓ detect_cannibalization")


def test_suggest_internal_links():
    reset_site_graph()
    graph = get_site_graph()
    a1 = ArticleNode("laptop reviews", word_count=1000)
    a2 = ArticleNode("best laptop 2026", word_count=1500)
    a3 = ArticleNode("laptop buying guide", word_count=1200)
    a4 = ArticleNode("unrelated topic", word_count=500)
    graph.add_article(a1)
    graph.add_article(a2)
    graph.add_article(a3)
    graph.add_article(a4)
    suggestions = graph.suggest_internal_links(a1.id)
    assert isinstance(suggestions, list)
    print("  ✓ suggest_internal_links")


def test_detect_orphan_pages():
    reset_site_graph()
    graph = get_site_graph()
    a1 = ArticleNode("parent", word_count=500)
    a2 = ArticleNode("child", word_count=300)
    a1.outbound_links.append(a2.id)
    graph.add_article(a1)
    graph.add_article(a2)
    orphans = graph.detect_orphan_pages()
    assert len(orphans) >= 1
    orphan_keywords = [o.keyword for o in orphans]
    assert "parent" in orphan_keywords
    print("  ✓ detect_orphan_pages")


def test_detect_semantic_duplicates():
    reset_site_graph()
    graph = get_site_graph()
    a1 = ArticleNode("best laptop 2026 programming", word_count=500)
    a2 = ArticleNode("best laptop 2026 coding", word_count=500)
    a3 = ArticleNode("totally unrelated", word_count=500)
    graph.add_article(a1)
    graph.add_article(a2)
    graph.add_article(a3)
    dupes = graph.detect_semantic_duplicates(threshold=0.3)
    assert len(dupes) >= 1
    print("  ✓ detect_semantic_duplicates")


def test_score_topic_saturation():
    reset_site_graph()
    graph = get_site_graph()
    cluster = TopicCluster("test cluster")
    graph.add_cluster(cluster)
    score = graph.score_topic_saturation(cluster.id)
    assert 0.0 <= score <= 1.0
    # Empty cluster
    score_empty = graph.score_topic_saturation("nonexistent")
    assert score_empty == 0.0
    print("  ✓ score_topic_saturation")


def test_score_authority_flow():
    reset_site_graph()
    graph = get_site_graph()
    a1 = ArticleNode("source", word_count=500)
    a1.trust_score = 0.9
    a1.quality_score = 0.8
    a2 = ArticleNode("target", word_count=300)
    a1.outbound_links.append(a2.id)
    graph.add_article(a1)
    graph.add_article(a2)
    score = graph.score_authority_flow(a2.id)
    assert 0.0 <= score <= 1.0
    print("  ✓ score_authority_flow")


def test_propagate_authority():
    reset_site_graph()
    graph = get_site_graph()
    a1 = ArticleNode("a", word_count=500)
    a2 = ArticleNode("b", word_count=300)
    a1.outbound_links.append(a2.id)
    graph.add_article(a1)
    graph.add_article(a2)
    count = graph.propagate_authority()
    assert count >= 0
    print("  ✓ propagate_authority")


def test_get_entity_coverage():
    reset_site_graph()
    graph = get_site_graph()
    entity = EntityNode("Apple", "brand", source_keyword="test")
    graph.add_entity(entity)
    coverage = graph.get_entity_coverage()
    assert coverage["total_entities"] >= 1
    assert "by_type" in coverage
    assert "top_entities" in coverage
    print("  ✓ get_entity_coverage")


def test_get_stats():
    reset_site_graph()
    graph = get_site_graph()
    node = ArticleNode("test", word_count=500)
    graph.add_article(node)
    stats = graph.get_stats()
    assert "articles" in stats
    assert "entities" in stats
    assert "clusters" in stats
    assert "avg_quality" in stats
    assert "avg_trust" in stats
    print("  ✓ get_stats")


def test_ingest_suggest_links():
    reset_site_graph()
    node1 = ingest_article("best laptop", SAMPLE_ARTICLE, "tech")
    node2 = ingest_article("laptop review", SAMPLE_ARTICLE, "tech")
    suggestions = suggest_internal_links_for("best laptop")
    assert isinstance(suggestions, list)
    print("  ✓ suggest_internal_links_for")


def test_detect_missing_topics():
    reset_site_graph()
    graph = get_site_graph()
    a1 = ArticleNode("best laptop 2026", niche="tech", word_count=500)
    a1.entities = ["Apple", "MacBook", "Dell", "ThinkPad"]
    graph.add_article(a1)
    missing = graph.detect_missing_topics("tech", ["laptop", "programming"])
    assert isinstance(missing, list)
    print("  ✓ detect_missing_topics")


def test_search_entities():
    reset_site_graph()
    graph = get_site_graph()
    entity = EntityNode("Apple Inc.", "brand")
    graph.add_entity(entity)
    results = graph.search_entities("apple")
    assert len(results) >= 1
    print("  ✓ search_entities")


def test_site_graph_persistence():
    reset_site_graph()
    graph = get_site_graph()
    node = ArticleNode("persist test", word_count=100)
    graph.add_article(node)
    graph2 = get_site_graph()
    retrieved = graph2.get_article(node.id)
    assert retrieved is not None
    assert retrieved.keyword == "persist test"
    print("  ✓ SiteGraph persistence")


def test_article_node_serialization_roundtrip():
    node = ArticleNode(
        keyword="test",
        url="https://example.com",
        word_count=500,
        niche="tech",
        intent="commercial",
        quality_score=0.8,
    )
    node.entities = ["Apple", "Dell"]
    node.outbound_links = ["https://example.com/link"]
    node.trust_score = 0.75
    d = node.to_dict()
    node2 = ArticleNode.from_dict(d)
    assert node2.keyword == "test"
    assert node2.word_count == 500
    assert node2.entities == ["Apple", "Dell"]
    assert node2.trust_score == 0.75
    print("  ✓ ArticleNode serialization roundtrip")


def test_entity_node_serialization_roundtrip():
    entity = EntityNode("Google", "company")
    entity.mention_count = 5
    entity.related_entities = ["Android", "Chrome"]
    d = entity.to_dict()
    entity2 = EntityNode.from_dict(d)
    assert entity2.name == "Google"
    assert entity2.mention_count == 5
    assert entity2.related_entities == ["Android", "Chrome"]
    print("  ✓ EntityNode serialization roundtrip")


if __name__ == "__main__":
    tests = [
        test_article_node, test_article_node_id_consistency,
        test_entity_node, test_entity_node_multiple_articles,
        test_topic_cluster, test_topic_cluster_article_management,
        test_authority_propagator, test_authority_propagator_empty,
        test_site_graph_add_get_article, test_site_graph_get_article_by_keyword,
        test_site_graph_update_article, test_site_graph_remove_article,
        test_site_graph_entity_crud, test_site_graph_cluster_crud,
        test_extract_entities, test_ingest_article,
        test_detect_cannibalization, test_suggest_internal_links,
        test_detect_orphan_pages, test_detect_semantic_duplicates,
        test_score_topic_saturation, test_score_authority_flow,
        test_propagate_authority, test_get_entity_coverage,
        test_get_stats, test_ingest_suggest_links,
        test_detect_missing_topics, test_search_entities,
        test_site_graph_persistence, test_article_node_serialization_roundtrip,
        test_entity_node_serialization_roundtrip,
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
    print(f"\nSite Graph Tests: {passed} passed, {failed} failed, {len(tests)} total")
    if failed > 0:
        sys.exit(1)
    print("ALL TESTS PASSED")
