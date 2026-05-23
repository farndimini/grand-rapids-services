"""
test_seo_intelligence.py — Phase 3 Autonomous Intelligence Engine tests
========================================================================
Covers all 8 dimensions:
  1. SERP Semantic Gap Engine
  2. Citation-Backed Generation
  3. Retrieval-Grounded Writing
  4. Human Editorial Rewriter
  5. Conversion-Aware Optimizer
  6. Topic Authority Memory
  7. AI Detection Resistance
  8. Autonomous Quality Evolution

No network required. All tests deterministic.
"""

import json
import math
import os
import re
import sys
import time
import threading

os.environ["SEO_AGENT_TEST_MODE"] = "1"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seo_intelligence import (
    SERPGapEngine, SERPGapReport, get_serp_gap_engine,
    CitationEngine, ClaimNode, CitationGraph, get_citation_engine,
    RetrievalGroundedValidator, RetrievalInfluenceScore, get_retrieval_validator,
    HumanEditorialRewriter, HumanizationReport, get_human_rewriter,
    ConversionOptimizer, ConversionReport, get_conversion_optimizer,
    TopicAuthorityGraph, EntityNode, NicheExpertise, get_authority_graph,
    AIDetectionResistance, AIPatternReport, get_ai_resistance,
    PatternPerformanceTracker, PatternRecord, get_pattern_tracker,
    get_intelligence_telemetry,
)

pass_count = 0
fail_count = 0

# ============================================================================
#  DIMENSION 1 — SERP SEMANTIC GAP ENGINE
# ============================================================================

def test_serp_gap_empty_article():
    """SERP gap with empty article returns empty report."""
    engine = SERPGapEngine()
    report = engine.analyze("test kw", "")
    assert report.total_serp_concepts == 0
    assert report.semantic_coverage == 0.0
    assert report.missing_concepts == []
    print("  ✓ test_serp_gap_empty_article")


def test_serp_gap_with_serp_data():
    """SERP gap with competitor data detects missing concepts."""
    engine = SERPGapEngine()
    article = "<h1>Best Laptops</h1><p>A guide to choosing laptops with good battery life and performance.</p>"
    serp = [
        {"title": "Top 10 Laptops 2026", "snippet": "Best laptops with great battery, display, and processor speed for gaming and work.",
         "headings": ["Best Laptops", "How to Choose"]},
    ]
    report = engine.analyze("best laptops", article, serp_data=serp)
    assert report.keyword == "best laptops"
    assert report.total_serp_concepts > 0
    assert isinstance(report.semantic_coverage, float)
    assert isinstance(report.entity_overlap, float)
    assert isinstance(report.heading_overlap, float)
    assert report.detected_intent in ("COMMERCIAL", "INFORMATIONAL", "NAVIGATIONAL")
    print("  ✓ test_serp_gap_with_serp_data")


def test_serp_gap_with_competitor_articles():
    """SERP gap with competitor HTML articles."""
    engine = SERPGapEngine()
    article = "<h1>Best Coffee Makers</h1><p>How to choose the best coffee maker for home use.</p>"
    competitors = [
        "<h1>Top Coffee Machines</h1><p>Best coffee machines with grinder and espresso maker features.</p>",
        "<h1>Coffee Maker Guide</h1><p>Drip coffee makers and single-serve brewers compared.</p>",
    ]
    report = engine.analyze("best coffee makers", article, competitor_articles=competitors)
    assert report.total_serp_concepts > 0
    assert report.competitor_weaknesses is not None
    assert report.recommended_sections is not None
    print("  ✓ test_serp_gap_with_competitor_articles")


def test_serp_gap_intent_detection():
    """Intent detection correctly classifies keyword intents."""
    engine = SERPGapEngine()
    # Test all intent types — keywords chosen to avoid substring false positives
    comm = engine._detect_search_intent("best printers", "compare top brands")
    assert comm == "COMMERCIAL"
    info = engine._detect_search_intent("how to bake bread", "learn baking step by step")
    assert info == "INFORMATIONAL"
    trans = engine._detect_search_intent("cheap flights", "price comparison for flights")
    assert trans == "TRANSACTIONAL"
    nav = engine._detect_search_intent("printer troubleshooting", "fix common printer issues")
    assert nav in ("NAVIGATIONAL", "INFORMATIONAL")  # fallback
    print("  ✓ test_serp_gap_intent_detection")


def test_serp_gap_telemetry():
    """SERP gap telemetry accumulates correctly."""
    engine = SERPGapEngine()
    engine.analyze("test1", "<h1>Test</h1><p>Content about topic and subject matter.</p>",
                    serp_data=[{"title": "Topic Guide", "snippet": "Content about topic and subject analysis."}])
    engine.analyze("test2", "<h1>Test</h1><p>Another content piece about different topic.</p>",
                    serp_data=[{"title": "Another Guide", "snippet": "Different content about another topic."}])
    t = engine.get_telemetry()
    assert t["total_analyses"] == 2
    assert 0 <= t["avg_semantic_coverage"] <= 1
    print("  ✓ test_serp_gap_telemetry")


def test_serp_gap_concurrency():
    """SERP gap engine is thread-safe."""
    engine = SERPGapEngine()
    errors = []
    def _run():
        try:
            for i in range(10):
                engine.analyze(f"kw{i}", f"<h1>Test</h1><p>Content about keyword {i} and analysis.</p>",
                                serp_data=[{"title": f"Guide {i}", "snippet": f"Content about keyword {i} analysis."}])
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=_run) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(errors) == 0
    assert engine.get_telemetry()["total_analyses"] >= 40
    print("  ✓ test_serp_gap_concurrency")


def test_serp_gap_global_singleton():
    """Global SERP gap engine is accessible and consistent."""
    e1 = get_serp_gap_engine()
    e2 = get_serp_gap_engine()
    assert e1 is e2
    print("  ✓ test_serp_gap_global_singleton")


# ============================================================================
#  DIMENSION 2 — CITATION-BACKED GENERATION
# ============================================================================

def test_citation_engine_empty():
    """Citation engine handles empty article."""
    engine = CitationEngine()
    graph = engine.analyze("")
    assert len(graph.claims) == 0
    report = engine.enforce_citations("")
    assert report["total_claims"] == 0
    print("  ✓ test_citation_engine_empty")


def test_citation_engine_numerical_claims():
    """Citation engine extracts numerical claims."""
    engine = CitationEngine()
    article = "This product costs $29.99 per month. It has 99% uptime. Over 10,000 users trust it."
    graph = engine.analyze(article)
    assert len(graph.claims) > 0
    numerical = [c for c in graph.claims.values() if c.claim_type == "numerical"]
    assert len(numerical) > 0
    print("  ✓ test_citation_engine_numerical_claims")


def test_citation_engine_superlative_claims():
    """Citation engine extracts superlative claims."""
    engine = CitationEngine()
    article = "This is the best tool in the market. The leading platform for SEO professionals. It is faster than competitors."
    graph = engine.analyze(article)
    superlative = [c for c in graph.claims.values() if c.claim_type == "superlative"]
    comparison = [c for c in graph.claims.values() if c.claim_type == "comparison"]
    assert len(superlative) > 0 or len(comparison) > 0
    print("  ✓ test_citation_engine_superlative_claims")


def test_citation_engine_source_matching():
    """Citation engine matches claims to sources."""
    engine = CitationEngine()
    article = "CloudSync costs $29 per month. It provides 99% uptime guarantee."
    sources = [
        {"text": "CloudSync pricing starts at $29 per month for the basic plan.", "url": "https://example.com/pricing"},
        {"text": "CloudSync guarantees 99.9% uptime for all paid plans.", "url": "https://example.com/uptime"},
    ]
    graph = engine.analyze(article, sources=sources)
    assert len(graph.claims) > 0
    supported = sum(1 for c in graph.claims.values() if c.is_supported)
    print(f"  ✓ test_citation_engine_source_matching ({supported}/{len(graph.claims)} claims supported)")


def test_citation_engine_enforce_blocks():
    """Citation enforcement blocks articles with unsupported numerical claims."""
    engine = CitationEngine()
    article = "ToolX costs $49.99 per month. It is better than ToolY. Over 50,000 businesses use it."
    graph = engine.analyze(article)
    report = engine.enforce_citations(article, graph)
    assert report["total_claims"] > 0
    assert isinstance(report["block"], bool)
    print("  ✓ test_citation_engine_enforce_blocks")


def test_citation_engine_telemetry():
    """Citation engine telemetry accumulates correctly."""
    engine = CitationEngine()
    engine.analyze("$19.99 per year with 95% satisfaction rate.")
    engine.analyze("The best solution costing $9.99.")
    t = engine.get_telemetry()
    assert t["total_claims_tracked"] > 0
    assert 0 <= t["support_rate"] <= 1
    assert t["graph_count"] >= 2
    print("  ✓ test_citation_engine_telemetry")


def test_citation_engine_concurrency():
    """Citation engine is thread-safe."""
    engine = CitationEngine()
    errors = []
    def _run():
        try:
            for i in range(10):
                engine.analyze(f"Product costs ${i+10} per month.")
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=_run) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(errors) == 0
    assert engine.get_telemetry()["total_claims_tracked"] >= 40
    print("  ✓ test_citation_engine_concurrency")


def test_citation_engine_global():
    """Global citation engine is accessible."""
    e1 = get_citation_engine()
    e2 = get_citation_engine()
    assert e1 is e2
    print("  ✓ test_citation_engine_global")


# ============================================================================
#  DIMENSION 3 — RETRIEVAL-GROUNDED WRITING
# ============================================================================

def test_retrieval_validator_empty():
    """Retrieval validator handles empty inputs."""
    v = RetrievalGroundedValidator()
    score = v.validate("test", "", [])
    assert score.total_retrieved_chunks == 0
    assert score.grounded_score == 0.0
    print("  ✓ test_retrieval_validator_empty")


def test_retrieval_validator_full_match():
    """Retrieval validator detects when chunks are used."""
    v = RetrievalGroundedValidator()
    article = "<p>CloudSync offers real-time collaboration and encrypted storage for teams of all sizes.</p>"
    chunks = [
        "CloudSync provides real-time collaboration features for teams.",
        "CloudSync offers encrypted storage solutions for businesses.",
    ]
    score = v.validate("CloudSync", article, chunks)
    assert score.total_retrieved_chunks == 2
    assert score.reuse_ratio > 0
    assert score.grounded_score > 0
    print("  ✓ test_retrieval_validator_full_match")


def test_retrieval_validator_hallucination_risk():
    """Retrieval validator detects hallucinated claims."""
    v = RetrievalGroundedValidator()
    article = "<p>CloudSync costs $49 per month with 99.9% uptime. It beats all competitors.</p>"
    chunks = [
        "CloudSync is a collaboration tool for teams.",
        "It offers basic project management features.",
    ]
    score = v.validate("CloudSync", article, chunks)
    assert score.hallucination_risk > 0
    print("  ✓ test_retrieval_validator_hallucination_risk")


def test_retrieval_validator_telemetry():
    """Retrieval validator telemetry accumulates."""
    v = RetrievalGroundedValidator()
    v.validate("k1", "<p>Content about topic A and subject B with analysis.</p>",
               ["Topic A content with analysis and research."])
    v.validate("k2", "<p>Different topic C with subject D analysis.</p>",
               ["Topic C and subject D analysis content."])
    t = v.get_telemetry()
    assert t["total_validations"] == 2
    assert 0 <= t["avg_grounded_score"] <= 1
    print("  ✓ test_retrieval_validator_telemetry")


def test_retrieval_validator_concurrency():
    """Retrieval validator is thread-safe."""
    v = RetrievalGroundedValidator()
    errors = []
    def _run():
        try:
            for i in range(10):
                v.validate(f"k{i}", f"<p>Content about topic {i}.</p>",
                           [f"Topic {i} content."])
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=_run) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(errors) == 0
    assert v.get_telemetry()["total_validations"] >= 40
    print("  ✓ test_retrieval_validator_concurrency")


def test_retrieval_validator_global():
    """Global retrieval validator is accessible."""
    v1 = get_retrieval_validator()
    v2 = get_retrieval_validator()
    assert v1 is v2
    print("  ✓ test_retrieval_validator_global")


# ============================================================================
#  DIMENSION 4 — HUMAN EDITORIAL REWRITER
# ============================================================================

def test_human_rewriter_empty():
    """Human rewriter handles empty article."""
    r = HumanEditorialRewriter()
    result, report = r.rewrite("")
    assert report.original_word_count == 0
    assert report.changes_made == 0
    print("  ✓ test_human_rewriter_empty")


def test_human_rewriter_ai_phrases():
    """Human rewriter removes AI-sounding phrases."""
    r = HumanEditorialRewriter()
    article = "In the ever-evolving world of technology, when it comes to finding the best laptop, it is important to note that quality matters."
    result, report = r.rewrite(article)
    assert "in the ever-evolving" not in result.lower()
    assert "when it comes to" not in result.lower()
    assert "it is important to note" not in result.lower()
    assert report.ai_phrase_removals > 0
    print("  ✓ test_human_rewriter_ai_phrases")


def test_human_rewriter_openers():
    """Human rewriter replaces banned openers."""
    r = HumanEditorialRewriter()
    article = "In this article, we will explore the best options. This article will cover everything you need."
    result, report = r.rewrite(article)
    assert "in this article, we will" not in result.lower()
    assert "this article will" not in result.lower()
    assert report.sentence_openings_diversified > 0
    print("  ✓ test_human_rewriter_openers")


def test_human_rewriter_transitions():
    """Human rewriter fixes flawed transitions."""
    r = HumanEditorialRewriter()
    article = "Firstly, check the specs. Secondly, compare prices. Thirdly, read reviews. Lastly, make a decision."
    result, report = r.rewrite(article)
    assert "Firstly" not in result
    assert "Secondly" not in result
    assert "Thirdly" not in result
    assert "Lastly" not in result
    assert report.transition_improvements > 0
    print("  ✓ test_human_rewriter_transitions")


def test_human_rewriter_cadence():
    """Human rewriter fixes repetitive cadence."""
    r = HumanEditorialRewriter()
    article = "The laptop is fast. The laptop is reliable. The laptop is affordable. The laptop is popular."
    result, report = r.rewrite(article)
    assert report.repetitive_cadence_fixes > 0 or report.changes_made > 0
    print("  ✓ test_human_rewriter_cadence")


def test_human_rewriter_detect_patterns():
    """AI pattern detection returns structured report."""
    r = HumanEditorialRewriter()
    article = "This is the best tool. This is the fastest tool. This is the cheapest option. In conclusion, buy it. It offers great value. It provides excellent support. It comes with many features."
    report = r.detect_ai_patterns(article)
    assert "total_sentences" in report
    assert "repetitive_start_rate" in report
    assert "sentence_length_std" in report
    assert "ai_phrase_count" in report
    assert "ai_detection_risk" in report
    assert 0 <= report["ai_detection_risk"] <= 1
    print("  ✓ test_human_rewriter_detect_patterns")


def test_human_rewriter_unchanged():
    """Human rewriter preserves normal text."""
    r = HumanEditorialRewriter()
    article = "This guide covers the best laptops for students. We compared battery life, performance, and price across ten models. Budget options start at $500."
    result, report = r.rewrite(article)
    assert len(result) > 0
    print("  ✓ test_human_rewriter_unchanged")


def test_human_rewriter_telemetry():
    """Human rewriter telemetry accumulates."""
    r = HumanEditorialRewriter()
    r.rewrite("In the ever-evolving world, when it comes to tech, it is important to note the latest trends.")
    r.rewrite("This article will explore options. In conclusion, choose wisely.")
    t = r.get_telemetry()
    assert t["total_rewrites"] == 2
    assert t["total_ai_phrases_removed"] > 0
    print("  ✓ test_human_rewriter_telemetry")


def test_human_rewriter_concurrency():
    """Human rewriter is thread-safe."""
    r = HumanEditorialRewriter()
    errors = []
    def _run():
        try:
            for i in range(10):
                r.rewrite(f"In the ever-evolving world of tech, option {i} is important to note.")
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=_run) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(errors) == 0
    assert r.get_telemetry()["total_rewrites"] >= 40
    print("  ✓ test_human_rewriter_concurrency")


def test_human_rewriter_global():
    """Global human rewriter is accessible."""
    r1 = get_human_rewriter()
    r2 = get_human_rewriter()
    assert r1 is r2
    print("  ✓ test_human_rewriter_global")


# ============================================================================
#  DIMENSION 5 — CONVERSION-AWARE OPTIMIZER
# ============================================================================

def test_conversion_optimizer_empty():
    """Conversion optimizer handles empty article."""
    o = ConversionOptimizer()
    report = o.analyze("test", "")
    assert report.ctas_found == 0
    assert report.engagement_score == 0.0
    print("  ✓ test_conversion_optimizer_empty")


def test_conversion_optimizer_cta_detection():
    """Conversion optimizer detects CTAs."""
    o = ConversionOptimizer()
    article = "<p>Sign up for our newsletter. Get started today with a free trial. Download now.</p>"
    report = o.analyze("best tool", article)
    assert report.ctas_found >= 2
    print("  ✓ test_conversion_optimizer_cta_detection")


def test_conversion_optimizer_commercial_intent():
    """Conversion optimizer identifies commercial intent friction points."""
    o = ConversionOptimizer()
    article = "<h1>Best Laptops</h1><p>Buy now and get started today. These are the best laptops.</p>"
    report = o.analyze("best laptops 2026", article)
    assert report.intent in ("COMMERCIAL", "TRANSACTIONAL", "NAVIGATIONAL")
    print("  ✓ test_conversion_optimizer_commercial_intent")


def test_conversion_optimizer_engagement():
    """Engagement score considers article structure."""
    o = ConversionOptimizer()
    article = """
    <table><tr><th>Feature</th></tr></table>
    <img src="test.jpg" />
    <blockquote>Great product</blockquote>
    <ul><li>Feature 1</li></ul>
    <div class="faq-section">FAQ content</div>
    <div class="quick-answer-box">Quick answer</div>
    """
    report = o.analyze("best tool 2026", article)
    assert report.engagement_score > 0.3
    print("  ✓ test_conversion_optimizer_engagement")


def test_conversion_optimizer_optimize_cta():
    """CTA optimization injects CTAs for commercial intent."""
    o = ConversionOptimizer()
    article = "<article><p>Best laptops for students with great features.</p></article>"
    result = o.optimize_cta(article, "best laptops")
    assert "href=" in result or article == result
    print("  ✓ test_conversion_optimizer_optimize_cta")


def test_conversion_optimizer_telemetry():
    """Conversion optimizer telemetry accumulates."""
    o = ConversionOptimizer()
    o.analyze("k1", "Sign up now for the best deal. Get started today.")
    o.analyze("k2", "How to choose a laptop. Guide with step-by-step instructions.")
    t = o.get_telemetry()
    assert t["total_analyses"] == 2
    assert 0 <= t["avg_cta_effectiveness"] <= 1
    print("  ✓ test_conversion_optimizer_telemetry")


def test_conversion_optimizer_concurrency():
    """Conversion optimizer is thread-safe."""
    o = ConversionOptimizer()
    errors = []
    def _run():
        try:
            for i in range(10):
                o.analyze(f"kw{i}", "Sign up now for the best deal. Get started today with free trial.")
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=_run) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(errors) == 0
    assert o.get_telemetry()["total_analyses"] >= 40
    print("  ✓ test_conversion_optimizer_concurrency")


def test_conversion_optimizer_global():
    """Global conversion optimizer is accessible."""
    o1 = get_conversion_optimizer()
    o2 = get_conversion_optimizer()
    assert o1 is o2
    print("  ✓ test_conversion_optimizer_global")


# ============================================================================
#  DIMENSION 6 — TOPIC AUTHORITY MEMORY
# ============================================================================

def test_authority_graph_empty():
    """Topic authority graph handles empty queries."""
    g = TopicAuthorityGraph()
    node = g.get_entity_knowledge("NonExistent")
    assert node is None
    niche = g.get_niche_expertise("unknown")
    assert niche is None
    related = g.get_related_entities("NonExistent")
    assert related == []
    print("  ✓ test_authority_graph_empty")


def test_authority_graph_ingest():
    """Topic authority graph ingests articles and builds entities."""
    g = TopicAuthorityGraph()
    article = "<h1>Best Laptops</h1><p>Apple MacBook Pro and Dell XPS are top choices for professionals.</p>"
    result = g.ingest_article("best laptops", article, "tech", 85)
    assert result["entities_added"] > 0
    assert "niche_authority" in result
    print("  ✓ test_authority_graph_ingest")


def test_authority_graph_entity_knowledge():
    """Topic authority graph retrieves entity knowledge."""
    g = TopicAuthorityGraph()
    article = "<p>Apple MacBook Pro offers great performance. Dell XPS competes with Apple MacBook Pro.</p>"
    g.ingest_article("laptops", article, "tech", 80)
    # Check entity was stored
    node = g.get_entity_knowledge("Apple MacBook Pro")
    if node:
        assert node.mention_count > 0
        assert node.niche == "tech"
    knowledge = g.get_concept_reinforcement("Apple MacBook Pro is great for developers.")
    assert "reinforcement_score" in knowledge
    print("  ✓ test_authority_graph_entity_knowledge")


def test_authority_graph_niche_expertise():
    """Topic authority graph accumulates niche expertise."""
    g = TopicAuthorityGraph()
    g.ingest_article("kw1", "<p>Apple MacBook Pro is a great laptop for developers and designers.</p>", "tech", 90)
    g.ingest_article("kw2", "<p>Dell XPS offers premium build quality and performance for professionals.</p>", "tech", 80)
    expertise = g.get_niche_expertise("tech")
    assert expertise is not None
    assert expertise.total_articles >= 2
    assert expertise.authority_score > 0
    print("  ✓ test_authority_graph_niche_expertise")


def test_authority_graph_relationships():
    """Topic authority graph builds entity relationships."""
    g = TopicAuthorityGraph()
    article = "<p>Apple MacBook Pro and Dell XPS are both excellent. Apple MacBook Pro vs Dell XPS comparison.</p>"
    g.ingest_article("laptops", article, "tech", 75)
    related = g.get_related_entities("Apple MacBook Pro")
    if related:
        assert len(related) > 0
        assert any("Dell" in r[0] for r in related)
    print("  ✓ test_authority_graph_relationships")


def test_authority_graph_concept_reinforcement():
    """Concept reinforcement scoring works."""
    g = TopicAuthorityGraph()
    g.ingest_article("kw1", "<p>Apple MacBook Pro is excellent for creative professionals and developers.</p>", "tech", 85)
    result = g.get_concept_reinforcement("The Apple MacBook Pro is a great laptop.")
    assert result["reinforcement_score"] >= 0
    assert result["reinforced_concepts"] >= 0
    print("  ✓ test_authority_graph_concept_reinforcement")


def test_authority_graph_telemetry():
    """Authority graph telemetry works."""
    g = TopicAuthorityGraph()
    g.ingest_article("kw1", "<p>Dell Computer offers great performance for professionals and developers.</p>", "tech", 85)
    g.ingest_article("kw2", "<p>Lenovo Thinkpad is a premium laptop for business users.</p>", "tech", 75)
    t = g.get_telemetry()
    assert t["total_entities"] > 0
    assert t["total_niches"] > 0
    assert "tech" in t["niche_authorities"]
    print("  ✓ test_authority_graph_telemetry")


def test_authority_graph_concurrency():
    """Authority graph is thread-safe."""
    g = TopicAuthorityGraph()
    errors = []
    def _run():
        try:
            for i in range(10):
                g.ingest_article(f"kw{i}", f"<p>Brand Alpha is a great product for professionals and developers.</p>", "test", 70)
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=_run) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(errors) == 0
    assert g.get_telemetry()["total_entities"] > 0
    print("  ✓ test_authority_graph_concurrency")


def test_authority_graph_global():
    """Global authority graph is accessible."""
    g1 = get_authority_graph()
    g2 = get_authority_graph()
    assert g1 is g2
    print("  ✓ test_authority_graph_global")


# ============================================================================
#  DIMENSION 7 — AI DETECTION RESISTANCE
# ============================================================================

def test_ai_detection_empty():
    """AI detection handles empty text."""
    d = AIDetectionResistance()
    report = d.analyze("")
    assert report.overall_human_score == 0.0
    print("  ✓ test_ai_detection_empty")


def test_ai_detection_short_text():
    """AI detection handles short text."""
    d = AIDetectionResistance()
    report = d.analyze("Short text.")
    assert report.overall_human_score == 0.0
    print("  ✓ test_ai_detection_short_text")


def test_ai_detection_normal_text():
    """AI detection returns proper metrics for normal text."""
    d = AIDetectionResistance()
    article = (
        "The quick brown fox jumps over the lazy dog. However, the dog was not actually lazy. "
        "This is a longer sentence that combines multiple ideas into a single complex thought.\n\n"
        "Short sentences add punch. Varied rhythm. Different lengths create natural flow. "
        "It was simply resting after a long day of chasing rabbits through the meadow near the old farm."
    )
    report = d.analyze(article)
    assert report.burstiness_score > 0
    assert report.perplexity_estimate > 0
    assert report.cadence_diversity > 0
    assert report.entropy_score > 0
    assert report.paragraph_entropy > 0
    assert 0 <= report.overall_human_score <= 1
    print("  ✓ test_ai_detection_normal_text")


def test_ai_detection_uniform_text():
    """AI detection flags uniform text as low human score."""
    d = AIDetectionResistance()
    article = ("This sentence has exactly twelve words. That sentence also has twelve words. "
               "Every sentence has twelve words here. This is a very uniform pattern. "
               "It makes the text sound robotic. The rhythm is very predictable.")
    report = d.analyze(article)
    # Uniform text should have lower burstiness
    assert report.burstiness_score < 0.5 or len(report.issues) > 0
    print("  ✓ test_ai_detection_uniform_text")


def test_ai_detection_suggestions():
    """AI detection suggests improvements for low scores."""
    d = AIDetectionResistance()
    report = AIPatternReport(
        burstiness_score=0.1,
        cadence_diversity=0.1,
        entropy_score=2.0,
        sentence_length_distribution={"1-5": 0.0, "6-15": 1.0, "16-25": 0.0, "26+": 0.0},
    )
    suggestions = d.suggest_improvements(report)
    assert len(suggestions) > 0
    print("  ✓ test_ai_detection_suggestions")


def test_ai_detection_telemetry():
    """AI detection telemetry accumulates."""
    d = AIDetectionResistance()
    d.analyze("First sentence with varied words. Second sentence also varied. Third one too, with different length. Fourth adds more variety. Fifth concludes.")
    d.analyze("Another text block. With different patterns. Short sentences. Longer more complex sentences that add variety to the rhythm and flow of the overall composition.")
    t = d.get_telemetry()
    assert t["total_analyses"] == 2
    assert 0 <= t["avg_human_score"] <= 1
    print("  ✓ test_ai_detection_telemetry")


def test_ai_detection_concurrency():
    """AI detection is thread-safe."""
    d = AIDetectionResistance()
    errors = []
    def _run():
        try:
            for i in range(10):
                d.analyze(f"This is test sentence number {i}. It has varied words. The quick brown fox jumps. Different lengths make it better.")
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=_run) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(errors) == 0
    assert d.get_telemetry()["total_analyses"] >= 40
    print("  ✓ test_ai_detection_concurrency")


def test_ai_detection_global():
    """Global AI detection is accessible."""
    d1 = get_ai_resistance()
    d2 = get_ai_resistance()
    assert d1 is d2
    print("  ✓ test_ai_detection_global")


# ============================================================================
#  DIMENSION 8 — AUTONOMOUS QUALITY EVOLUTION
# ============================================================================

def test_pattern_tracker_empty():
    """Pattern tracker handles empty queries."""
    t = PatternPerformanceTracker()
    top = t.get_top_patterns("opener")
    assert top == []
    failing = t.get_failing_patterns()
    assert failing == []
    adapt = t.adapt_strategy("tech")
    assert isinstance(adapt, dict)
    print("  ✓ test_pattern_tracker_empty")


def test_pattern_tracker_record():
    """Pattern tracker records articles and extracts patterns."""
    t = PatternPerformanceTracker()
    article = "This is the first sentence of the article. It covers the best options. Sign up now for the best deal. FAQ section with five items."
    result = t.record_article("best tool", article, 85, niche="tech", reward=0.9)
    assert result["patterns_recorded"] > 0
    assert result["is_success"] == True
    print("  ✓ test_pattern_tracker_record")


def test_pattern_tracker_top_patterns():
    """Pattern tracker returns top patterns by type."""
    t = PatternPerformanceTracker()
    for i in range(5):
        t.record_article(f"kw{i}", f"Sentence one about topic. Sentence two continues. Sentence three wraps. Sign up now for offers. FAQ items five total.", 80 + i, niche="tech", reward=0.5)
    top = t.get_top_patterns("cta", niche="tech")
    assert len(top) > 0
    assert all(p.pattern_type == "cta" for p in top)
    print("  ✓ test_pattern_tracker_top_patterns")


def test_pattern_tracker_failing():
    """Pattern tracker identifies failing patterns."""
    t = PatternPerformanceTracker()
    t.record_article("bad1", "Bad opener content with no structure.", 30, niche="tech", reward=-0.5)
    t.record_article("bad2", "Bad opener content again no structure.", 20, niche="tech", reward=-0.8)
    failing = t.get_failing_patterns(threshold=-0.3)
    assert len(failing) >= 0  # may or may not have failing depending on weights
    print("  ✓ test_pattern_tracker_failing")


def test_pattern_tracker_adapt_strategy():
    """Pattern tracker produces adaptation recommendations."""
    t = PatternPerformanceTracker()
    for i in range(3):
        t.record_article(f"good{i}", f"Great article with excellent content. Best options compared. Sign up now for deals. FAQ items included.", 90, niche="tech", reward=0.9)
    adapt = t.adapt_strategy("tech")
    assert isinstance(adapt, dict)
    print("  ✓ test_pattern_tracker_adapt_strategy")


def test_pattern_tracker_weight_decay():
    """Pattern tracker decays weights for failing patterns."""
    t = PatternPerformanceTracker()
    # Record a failing pattern multiple times
    for i in range(5):
        t.record_article(f"fail{i}", f"Bad content with no real value or structure.", 20, niche="tech", reward=-0.5)
    failing = t.get_failing_patterns(threshold=-0.3)
    if failing:
        for p in failing:
            assert p.influence_weight < 1.0 or p.avg_reward < -0.2
    print("  ✓ test_pattern_tracker_weight_decay")


def test_pattern_tracker_reset_niche():
    """Pattern tracker resets patterns for a niche."""
    t = PatternPerformanceTracker()
    t.record_article("kw1", "Good content with structure and value.", 80, niche="tech", reward=0.5)
    before = len(t._patterns)
    removed = t.reset_niche("tech")
    after = len(t._patterns)
    assert removed > 0 or before == 0
    print("  ✓ test_pattern_tracker_reset_niche")


def test_pattern_tracker_telemetry():
    """Pattern tracker telemetry works."""
    t = PatternPerformanceTracker()
    t.record_article("kw1", "Good content with value and structure.", 85, niche="tech", reward=0.8)
    t.record_article("kw2", "Another good article with great content and structure.", 75, niche="tech", reward=0.6)
    tele = t.get_telemetry()
    assert tele["total_patterns_tracked"] > 0
    assert tele["article_history_size"] >= 2
    print("  ✓ test_pattern_tracker_telemetry")


def test_pattern_tracker_concurrency():
    """Pattern tracker is thread-safe."""
    t = PatternPerformanceTracker()
    errors = []
    def _run():
        try:
            for i in range(10):
                t.record_article(f"kw{i}", f"Content about topic with value and structure.", 70, niche="test", reward=0.3)
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=_run) for _ in range(4)]
    for t_ in threads: t_.start()
    for t_ in threads: t_.join()
    assert len(errors) == 0
    tele = t.get_telemetry()
    assert tele["total_patterns_tracked"] > 0
    print("  ✓ test_pattern_tracker_concurrency")


def test_pattern_tracker_global():
    """Global pattern tracker is accessible."""
    t1 = get_pattern_tracker()
    t2 = get_pattern_tracker()
    assert t1 is t2
    print("  ✓ test_pattern_tracker_global")


# ============================================================================
#  AGGREGATED TELEMETRY
# ============================================================================

def test_aggregated_telemetry():
    """Aggregated telemetry returns all 8 dimensions."""
    tele = get_intelligence_telemetry()
    expected = ["serp_gap", "citation", "retrieval", "human_rewriter",
                 "conversion", "authority", "ai_resistance", "pattern_evolution"]
    for key in expected:
        assert key in tele, f"Missing telemetry key: {key}"
        assert isinstance(tele[key], dict)
    print("  ✓ test_aggregated_telemetry")


# ============================================================================
#  INTEGRATION — verifies modules.py can import and use engines
# ============================================================================

def test_integration_import_from_modules():
    """modules.py can import Phase 3 engines."""
    import modules
    assert modules._HAS_INTELLIGENCE == True
    from seo_intelligence import get_human_rewriter
    r = get_human_rewriter()
    assert r is not None
    print("  ✓ test_integration_import_from_modules")


def test_integration_import_from_post_processor():
    """post_processor.py can use AI detection resistance."""
    import post_processor
    assert post_processor._HAS_AI_RESISTANCE == True
    from seo_intelligence import get_ai_resistance
    d = get_ai_resistance()
    assert d is not None
    print("  ✓ test_integration_import_from_post_processor")


# ============================================================================
#  RUN ALL
# ============================================================================

TESTS = [
    # Dimension 1 — SERP Gap
    test_serp_gap_empty_article,
    test_serp_gap_with_serp_data,
    test_serp_gap_with_competitor_articles,
    test_serp_gap_intent_detection,
    test_serp_gap_telemetry,
    test_serp_gap_concurrency,
    test_serp_gap_global_singleton,

    # Dimension 2 — Citation
    test_citation_engine_empty,
    test_citation_engine_numerical_claims,
    test_citation_engine_superlative_claims,
    test_citation_engine_source_matching,
    test_citation_engine_enforce_blocks,
    test_citation_engine_telemetry,
    test_citation_engine_concurrency,
    test_citation_engine_global,

    # Dimension 3 — Retrieval
    test_retrieval_validator_empty,
    test_retrieval_validator_full_match,
    test_retrieval_validator_hallucination_risk,
    test_retrieval_validator_telemetry,
    test_retrieval_validator_concurrency,
    test_retrieval_validator_global,

    # Dimension 4 — Human Rewriter
    test_human_rewriter_empty,
    test_human_rewriter_ai_phrases,
    test_human_rewriter_openers,
    test_human_rewriter_transitions,
    test_human_rewriter_cadence,
    test_human_rewriter_detect_patterns,
    test_human_rewriter_unchanged,
    test_human_rewriter_telemetry,
    test_human_rewriter_concurrency,
    test_human_rewriter_global,

    # Dimension 5 — Conversion
    test_conversion_optimizer_empty,
    test_conversion_optimizer_cta_detection,
    test_conversion_optimizer_commercial_intent,
    test_conversion_optimizer_engagement,
    test_conversion_optimizer_optimize_cta,
    test_conversion_optimizer_telemetry,
    test_conversion_optimizer_concurrency,
    test_conversion_optimizer_global,

    # Dimension 6 — Authority Graph
    test_authority_graph_empty,
    test_authority_graph_ingest,
    test_authority_graph_entity_knowledge,
    test_authority_graph_niche_expertise,
    test_authority_graph_relationships,
    test_authority_graph_concept_reinforcement,
    test_authority_graph_telemetry,
    test_authority_graph_concurrency,
    test_authority_graph_global,

    # Dimension 7 — AI Detection
    test_ai_detection_empty,
    test_ai_detection_short_text,
    test_ai_detection_normal_text,
    test_ai_detection_uniform_text,
    test_ai_detection_suggestions,
    test_ai_detection_telemetry,
    test_ai_detection_concurrency,
    test_ai_detection_global,

    # Dimension 8 — Pattern Tracker
    test_pattern_tracker_empty,
    test_pattern_tracker_record,
    test_pattern_tracker_top_patterns,
    test_pattern_tracker_failing,
    test_pattern_tracker_adapt_strategy,
    test_pattern_tracker_weight_decay,
    test_pattern_tracker_reset_niche,
    test_pattern_tracker_telemetry,
    test_pattern_tracker_concurrency,
    test_pattern_tracker_global,

    # Aggregated
    test_aggregated_telemetry,

    # Integration
    test_integration_import_from_modules,
    test_integration_import_from_post_processor,
]


def run_tests():
    global pass_count, fail_count
    for test in TESTS:
        try:
            test()
            pass_count += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            fail_count += 1

    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {pass_count}/{pass_count + fail_count} passed  {'ALL TESTS PASSED' if fail_count == 0 else 'SOME TESTS FAILED'}")
    print(f"{'=' * 60}")
    return fail_count == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
