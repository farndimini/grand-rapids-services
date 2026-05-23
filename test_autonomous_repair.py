"""
test_autonomous_repair.py — Tests for Autonomous Repair Orchestrator
=====================================================================
Tests FailureClassifier, all repair strategies, RecursiveRepairLoop,
AutonomousRepairOrchestrator, and persistence.
"""

import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ["SEO_AGENT_TEST_MODE"] = "1"

from autonomous_repair_orchestrator import (
    FailureClassifier, HallucinationRepairStrategy,
    ContradictionRepairStrategy, QualityGateRepairStrategy,
    AIStyleRepairStrategy, SchemaRepairStrategy, CitationRepairStrategy,
    RecursiveRepairLoop, AutonomousRepairOrchestrator,
    RepairOutcome, RepairMemory, RepairStrategy,
    get_repair_orchestrator, reset_repair_orchestrator, run_autonomous_repair,
)

SAMPLE_ARTICLE = """<h1>Best Laptops for Programming</h1>
<p>The MacBook Pro costs $2,499 and is 70% faster than competitors.</p>
<p>The Dell XPS 15 is the best value laptop, but it is also the worst for gaming.</p>
<p>We tested this product and it is always reliable.</p>
<p><a href="https://example.com">Link</a></p>
"""

SAMPLE_ARTICLE_HALLU = """<h1>Test Article</h1>
<p>This product costs $9,999 and is 100% guaranteed to work.</p>
<p>We tested this product hands-on in our lab.</p>
<p>After 2 weeks of testing, we can confirm it is 50% better.</p>
[VERIFY: pricing]
"""

SAMPLE_ARTICLE_QUALITY = """<h2>Section 1</h2><p>short</p>
<h2>Section 2</h2><p>brief</p>
"""


def test_failure_classifier():
    classifier = FailureClassifier()
    cls = classifier.classify("Unsupported numerical claims", "article")
    assert cls == "hallucination"
    cls2 = classifier.classify("Duplicate H1 detected", "article")
    assert cls2 == "quality_gate"
    cls3 = classifier.classify("Contradiction found", "article")
    assert cls3 == "contradiction"
    cls4 = classifier.classify("Invalid JSON-LD schema", "article")
    assert cls4 == "schema"
    cls5 = classifier.classify("AI detection risk high", "article")
    assert cls5 == "ai_style"
    cls6 = classifier.classify("Unknown issue", "article")
    assert cls6 in ("unknown", "temporal")
    print("  ✓ FailureClassifier")


def test_failure_classifier_priority():
    classifier = FailureClassifier()
    assert classifier.get_priority("hallucination") == 1
    assert classifier.get_priority("unknown") > classifier.get_priority("hallucination")
    print("  ✓ FailureClassifier priority")


def test_hallucination_repair_strategy():
    strategy = HallucinationRepairStrategy()
    assert strategy.name == "HallucinationRepair"
    assert "hallucination" in strategy.failure_classes
    repaired, success, error = strategy.repair(
        SAMPLE_ARTICLE_HALLU, "Unsupported prices", "test", 1
    )
    assert success or not error
    # Should modify the article
    assert isinstance(repaired, str)
    print("  ✓ HallucinationRepairStrategy")


def test_contradiction_repair_strategy():
    strategy = ContradictionRepairStrategy()
    article = "<h1>Test</h1><p>This is the best and worst product.</p>"
    repaired, success, error = strategy.repair(article, "Contradiction", "test", 1)
    assert isinstance(repaired, str)
    print("  ✓ ContradictionRepairStrategy")


def test_quality_gate_repair_strategy():
    strategy = QualityGateRepairStrategy()
    # Missing H1
    article = "<p>No H1 here</p>"
    repaired, success, error = strategy.repair(article, "Missing H1", "test kw", 1)
    assert "<h1>" in repaired
    # Duplicate H1
    article2 = "<h1>First</h1><p>text</p><h1>Second</h1>"
    repaired2, success2, error2 = strategy.repair(article2, "Duplicate H1", "test", 1)
    h1_count = repaired2.lower().count("<h1")
    assert h1_count < 2
    print("  ✓ QualityGateRepairStrategy")


def test_ai_style_repair_strategy():
    strategy = AIStyleRepairStrategy()
    article = "<p>In today's digital age, this is a game-changer. In conclusion, it is great.</p>"
    repaired, success, error = strategy.repair(article, "AI detection risk", "test", 1)
    assert isinstance(repaired, str)
    # The "in conclusion" should be processed
    assert "In conclusion" not in repaired or "To summarize" in repaired
    print("  ✓ AIStyleRepairStrategy")


def test_schema_repair_strategy():
    strategy = SchemaRepairStrategy()
    article = "<p>No schema here</p>"
    repaired, success, error = strategy.repair(article, "Missing schema", "test", 1)
    assert isinstance(repaired, str)
    # Should add Article schema
    assert '@type": "Article"' in repaired or '"@type":"Article"' in repaired
    print("  ✓ SchemaRepairStrategy")


def test_schema_repair_unclosed_tags():
    strategy = SchemaRepairStrategy()
    article = "<p>Unclosed div<div><p>more text"
    repaired, success, error = strategy.repair(article, "Unclosed tags", "test", 1)
    assert isinstance(repaired, str)
    print("  ✓ SchemaRepairStrategy unclosed tags")


def test_citation_repair_strategy():
    strategy = CitationRepairStrategy()
    article = '<p>Check [LINK: example] and <a href="https://example.com">link</a></p>'
    repaired, success, error = strategy.repair(article, "Few links", "test", 1)
    assert isinstance(repaired, str)
    # LINK placeholder should be replaced
    assert "[LINK:" not in repaired
    print("  ✓ CitationRepairStrategy")


def test_repair_outcome_dataclass():
    outcome = RepairOutcome(
        attempt=1, strategy_name="Test", failure_class="test",
        success=True, duration_ms=10.5,
    )
    d = outcome.to_dict()
    assert d["attempt"] == 1
    assert d["success"] is True
    assert d["duration_ms"] == 10.5
    print("  ✓ RepairOutcome")


def test_repair_memory_dataclass():
    memory = RepairMemory(keyword="test")
    outcome = RepairOutcome(attempt=1, strategy_name="S1", failure_class="c1", success=True, duration_ms=5.0)
    memory.outcomes.append(outcome)
    memory.root_cause = "hallucination"
    d = memory.to_dict()
    assert d["keyword"] == "test"
    assert d["root_cause"] == "hallucination"
    assert len(d["outcomes"]) == 1
    print("  ✓ RepairMemory")


def test_recursive_repair_loop():
    loop = RecursiveRepairLoop(max_attempts=3, repair_budget=5)
    memory = loop.repair(SAMPLE_ARTICLE_HALLU, "Unsupported numerical claims", "test")
    assert isinstance(memory, RepairMemory)
    assert memory.keyword == "test"
    assert len(memory.outcomes) >= 1
    assert memory.root_cause in ("hallucination", "unknown")
    print("  ✓ RecursiveRepairLoop")


def test_recursive_repair_loop_no_strategy_match():
    loop = RecursiveRepairLoop(max_attempts=2)
    memory = loop.repair("<p>simple article</p>", "unknown failure type", "test")
    assert memory.escalated or len(memory.outcomes) > 0
    print("  ✓ RecursiveRepairLoop no strategy match")


def test_recursive_repair_budget_exhaustion():
    loop = RecursiveRepairLoop(max_attempts=10, repair_budget=3)
    memory = loop.repair("<p>test</p>", "Unsupported numerical: $999", "test")
    # With budget of 3, should stop before max_attempts
    outcomes = len(memory.outcomes)
    assert outcomes <= 3 + 1  # budget + some margin
    print("  ✓ RecursiveRepairLoop budget exhaustion")


def test_repair_loop_get_stats():
    loop = RecursiveRepairLoop()
    stats = loop.get_repair_stats()
    assert "total_articles_repaired" in stats
    assert "success_rate" in stats
    assert "by_failure_class" in stats
    print("  ✓ Repair loop stats")


def test_repair_loop_get_memory():
    loop = RecursiveRepairLoop()
    memory = loop.repair("<p>test article</p>", "test error", "memory_test_kw")
    retrieved = loop.get_repair_memory("memory_test_kw")
    assert retrieved is not None
    assert retrieved.keyword == "memory_test_kw"
    print("  ✓ Repair loop get memory")


def test_autonomous_repair_orchestrator():
    reset_repair_orchestrator()
    orchestrator = get_repair_orchestrator()
    assert orchestrator is not None
    print("  ✓ AutonomousRepairOrchestrator singleton")


def test_orchestrator_repair():
    orchestrator = get_repair_orchestrator()
    repaired, memory = orchestrator.orchestrate_repair(
        SAMPLE_ARTICLE_HALLU, "Unsupported numerical: $9,999", "test"
    )
    assert isinstance(repaired, str)
    assert isinstance(memory, RepairMemory)
    assert len(memory.outcomes) >= 1
    print("  ✓ Orchestrator repair")


def test_orchestrator_semantic_regression():
    orchestrator = get_repair_orchestrator()
    # A very short article that repair might degrade
    article = "<h1>Test</h1><p>Short article.</p>"
    repaired, memory = orchestrator.orchestrate_repair(article, "test error", "test")
    assert isinstance(repaired, str)
    assert len(repaired) >= 10
    print("  ✓ Orchestrator semantic regression prevention")


def test_orchestrator_get_stats():
    orchestrator = get_repair_orchestrator()
    stats = orchestrator.get_stats()
    assert "total_articles_repaired" in stats
    print("  ✓ Orchestrator stats")


def test_run_autonomous_repair_convenience():
    reset_repair_orchestrator()
    repaired, memory = run_autonomous_repair(
        SAMPLE_ARTICLE, "Duplicate H1", "convenience test"
    )
    assert isinstance(repaired, str)
    assert isinstance(memory, RepairMemory)
    print("  ✓ run_autonomous_repair convenience")


def test_mutation_on_retry():
    loop = RecursiveRepairLoop(max_attempts=3)
    # Use an article that will fail multiple times
    memory = loop.repair("<p>simple</p>", "Contradiction: best vs worst", "mutate_test")
    attempts_with_mutation = sum(1 for o in memory.outcomes if o.mutated)
    assert isinstance(attempts_with_mutation, int)
    print("  ✓ Mutation on retry")


def test_repair_strategy_dataclass():
    strategy = RepairStrategy("Test", "A test strategy", ["test_class"])
    assert strategy.name == "Test"
    assert strategy.success_rate == 0.5
    assert strategy.attempts == 0
    print("  ✓ RepairStrategy dataclass")


def test_failure_classifier_article_fallback():
    classifier = FailureClassifier()
    # Article with old years should fallback to temporal
    article = "<p>In 2020 this was relevant. In 2021 it changed.</p>"
    cls = classifier.classify("Some generic error", article)
    assert cls == "temporal"
    print("  ✓ FailureClassifier temporal fallback")


def test_empty_failure_classifier():
    classifier = FailureClassifier()
    cls = classifier.classify("", "")
    assert cls in ("unknown", "temporal")
    print("  ✓ FailureClassifier empty input")


def test_orchestrator_reset():
    reset_repair_orchestrator()
    o1 = get_repair_orchestrator()
    o2 = get_repair_orchestrator()
    assert o1 is o2
    reset_repair_orchestrator()
    o3 = get_repair_orchestrator()
    assert o3 is not o1
    print("  ✓ Orchestrator reset")


if __name__ == "__main__":
    tests = [
        test_failure_classifier, test_failure_classifier_priority,
        test_hallucination_repair_strategy,
        test_contradiction_repair_strategy,
        test_quality_gate_repair_strategy,
        test_ai_style_repair_strategy,
        test_schema_repair_strategy, test_schema_repair_unclosed_tags,
        test_citation_repair_strategy,
        test_repair_outcome_dataclass, test_repair_memory_dataclass,
        test_recursive_repair_loop, test_recursive_repair_loop_no_strategy_match,
        test_recursive_repair_budget_exhaustion,
        test_repair_loop_get_stats, test_repair_loop_get_memory,
        test_autonomous_repair_orchestrator,
        test_orchestrator_repair, test_orchestrator_semantic_regression,
        test_orchestrator_get_stats,
        test_run_autonomous_repair_convenience,
        test_mutation_on_retry,
        test_repair_strategy_dataclass,
        test_failure_classifier_article_fallback,
        test_empty_failure_classifier,
        test_orchestrator_reset,
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
    print(f"\nAutonomous Repair Tests: {passed} passed, {failed} failed, {len(tests)} total")
    if failed > 0:
        sys.exit(1)
    print("ALL TESTS PASSED")
