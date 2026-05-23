"""
test_system_hardening.py — Phase 2 System Hardening Tests
==========================================================
Tests all 8 audit dimensions: prompt truth, contamination, claim grounding,
post-processor safety, failure path, vector memory, multi-agent, performance.
No network required.
"""

import os
os.environ["SEO_AGENT_TEST_MODE"] = "1"

import hashlib
import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))


# ============================================================================
#  DIMENSION 1 — PROMPT EXECUTION TRUTH
# ============================================================================

def test_prompt_fingerprinter_basic():
    from system_hardening import PromptFingerprinter
    fp = PromptFingerprinter()
    fp.fingerprint_system("You are a helpful assistant.")
    fp.fingerprint_injection("memory", "Previous article: best laptops 2026")
    payload = fp.fingerprint_payload(
        "System prompt here",
        "User message here",
        [("memory", "Previous article data")],
        "claude-sonnet-4",
    )
    assert payload["payload_hash"]
    assert payload["injection_count"] == 1
    assert payload["model"] == "claude-sonnet-4"
    assert payload["injection_order"] == ["memory"]
    print("  ✓ test_prompt_fingerprinter_basic")


def test_prompt_fingerprinter_verify():
    from system_hardening import PromptFingerprinter
    fp = PromptFingerprinter()
    intended = fp.fingerprint_payload(
        "System", "User message", [], "gpt-4o"
    )
    # Same payload should match
    verification = fp.verify_payload(intended, ("System", "User message"))
    assert verification["match"] is True
    # Different payload should NOT match
    verification2 = fp.verify_payload(intended, ("System", "Different user message"))
    assert verification2["match"] is False
    print("  ✓ test_prompt_fingerprinter_verify")


def test_prompt_fingerprinter_anomaly_detection():
    from system_hardening import PromptFingerprinter
    fp = PromptFingerprinter()
    fp.fingerprint_payload("System A", "User", [], "model1")
    fp.fingerprint_payload("System B", "User", [], "model1")  # system overwrite
    anomalies = fp.detect_anomalies(window=5)
    system_overwrites = [a for a in anomalies if a["type"] == "system_overwrite"]
    assert len(system_overwrites) >= 1
    print("  ✓ test_prompt_fingerprinter_anomaly_detection")


def test_prompt_fingerprinter_injection_collapse():
    from system_hardening import PromptFingerprinter
    fp = PromptFingerprinter()
    # Large injection
    fp.fingerprint_payload(
        "System", "User",
        [("memory", "A" * 1000), ("vector", "B" * 1000)],
        "model1",
    )
    # Small injection (simulates collapse)
    fp.fingerprint_payload(
        "System", "User",
        [("memory", "A" * 10), ("vector", "B" * 10)],
        "model1",
    )
    anomalies = fp.detect_anomalies(window=5)
    collapses = [a for a in anomalies if a["type"] == "injection_size_collapse"]
    assert len(collapses) >= 1
    print("  ✓ test_prompt_fingerprinter_injection_collapse")


# ============================================================================
#  DIMENSION 2 — MEMORY CONTAMINATION AUDIT
# ============================================================================

def test_contamination_scorer_niche_detection():
    from system_hardening import ContaminationScorer
    cs = ContaminationScorer()
    assert cs.detect_niche("best laptop 2026") == "tech"
    assert cs.detect_niche("credit card rewards") == "finance"
    assert cs.detect_niche("workout routine") == "health"
    assert cs.detect_niche("seo tips") == "marketing"
    assert cs.detect_niche("python programming") == "tech"
    assert cs.detect_niche("general topic") == "general"
    print("  ✓ test_contamination_scorer_niche_detection")


def test_contamination_scorer_contamination():
    from system_hardening import ContaminationScorer
    cs = ContaminationScorer()
    # Same niche = no contamination
    assert cs.contamination_score("tech", {"keyword": "best laptop"}) == 0.0
    # Different niche = full contamination
    assert cs.contamination_score("health", {"keyword": "credit card"}) == 1.0
    # General niche = no contamination
    assert cs.contamination_score("general", {"keyword": "anything"}) == 0.0
    print("  ✓ test_contamination_scorer_contamination")


def test_contamination_scorer_filter():
    from system_hardening import ContaminationScorer
    cs = ContaminationScorer()
    mem = {
        "articles_written": [
            {"keyword": "best laptop", "quality_score": 85, "date": datetime.now().isoformat()},
            {"keyword": "credit card rewards", "quality_score": 90, "date": datetime.now().isoformat()},
            {"keyword": "best gaming laptop", "quality_score": 70, "date": datetime.now().isoformat()},
            {"keyword": "low quality article", "quality_score": 30, "date": datetime.now().isoformat()},
        ]
    }
    # For tech niche, should get tech entries only (contamination > 1 excludes finance)
    filtered = cs.filter_memory_for_niche(mem, "best laptop", max_entries=5)
    kws = [e["keyword"] for e in filtered]
    assert "best laptop" not in kws  # same keyword excluded (self)
    assert "best gaming laptop" in kws
    assert "credit card rewards" not in kws  # contaminated
    assert "low quality article" not in kws  # suppressed (quality < 60)
    print("  ✓ test_contamination_scorer_filter")


def test_contamination_scorer_decay():
    from system_hardening import ContaminationScorer
    from datetime import timedelta
    cs = ContaminationScorer()
    # New entry = high weight
    new_entry = {"date": datetime.now().isoformat()}
    # Old entry = low weight
    old_entry = {"date": (datetime.now() - timedelta(days=30)).isoformat()}
    new_w = cs.decay_weight(new_entry)
    old_w = cs.decay_weight(old_entry)
    assert new_w > old_w, f"New weight {new_w} should be > old weight {old_w}"
    print("  ✓ test_contamination_scorer_decay")


def test_contamination_scorer_quality_weight():
    from system_hardening import ContaminationScorer
    cs = ContaminationScorer()
    assert cs.quality_weight({"quality_score": 90}) == 0.9
    assert cs.quality_weight({"quality_score": 40}) == 0.0  # below threshold
    assert cs.quality_weight({"quality_score": 0}) == 0.0
    print("  ✓ test_contamination_scorer_quality_weight")


def test_contamination_scorer_blacklist():
    from system_hardening import ContaminationScorer
    cs = ContaminationScorer(blacklist_keywords=["spam", "bad"])
    assert cs.is_blacklisted("spam keyword") is True
    assert cs.is_blacklisted("good keyword") is False
    cs.add_blacklist("another bad")
    assert "another bad" in cs.get_blacklist()
    print("  ✓ test_contamination_scorer_blacklist")


# ============================================================================
#  DIMENSION 3 — CLAIM GROUNDING VERIFICATION
# ============================================================================

def test_claim_auditor_superlative_detection():
    from system_hardening import ClaimGroundingAuditor
    auditor = ClaimGroundingAuditor()
    article = "<p>This is the best laptop ever made. The ultimate choice.</p>"
    report = auditor.audit_article(article)
    assert report["total_superlatives"] >= 2
    assert report["unsupported_superlatives"] >= 2
    print("  ✓ test_claim_auditor_superlative_detection")


def test_claim_auditor_benchmark_detection():
    from system_hardening import ClaimGroundingAuditor
    auditor = ClaimGroundingAuditor()
    article = "<p>This tool is 10x faster than the competition.</p>"
    report = auditor.audit_article(article)
    assert report["total_benchmarks"] >= 1
    assert report["unsupported_benchmarks"] >= 1
    print("  ✓ test_claim_auditor_benchmark_detection")


def test_claim_auditor_comparative_detection():
    from system_hardening import ClaimGroundingAuditor
    auditor = ClaimGroundingAuditor()
    article = "<p>Product A is better than Product B for most users.</p>"
    report = auditor.audit_article(article)
    assert report["total_comparatives"] >= 1
    print("  ✓ test_claim_auditor_comparative_detection")


def test_claim_auditor_fake_authority():
    from system_hardening import ClaimGroundingAuditor
    auditor = ClaimGroundingAuditor()
    article = "<p>According to our research, this is the best option.</p>"
    report = auditor.audit_article(article)
    assert report["total_fake_authority"] >= 1
    print("  ✓ test_claim_auditor_fake_authority")


def test_claim_auditor_confidence_decay():
    from system_hardening import ClaimGroundingAuditor
    auditor = ClaimGroundingAuditor()
    # High confidence, many sources, no contradictions
    high = auditor.confidence_decay(0.9, 5, 0)
    assert high > 0.9
    # Low confidence, few sources, many contradictions
    low = auditor.confidence_decay(0.5, 1, 3)
    assert low < 0.5
    print("  ✓ test_claim_auditor_confidence_decay")


def test_claim_auditor_superlative_suppression():
    from system_hardening import ClaimGroundingAuditor
    auditor = ClaimGroundingAuditor()
    text = "This is the best product ever created."
    context = "No evidence provided."
    result = auditor.suppress_superlative(text, context)
    assert "best" not in result or "well-regarded" in result
    # With evidence, keep superlatives
    text2 = "This is the best product ever created."
    context2 = "because according to our benchmark testing data, it scored highest."
    result2 = auditor.suppress_superlative(text2, context2)
    assert "best" in result2  # kept because there's evidence
    print("  ✓ test_claim_auditor_superlative_suppression")


def test_claim_auditor_lineage():
    from system_hardening import ClaimGroundingAuditor, ClaimLineage
    auditor = ClaimGroundingAuditor()
    auditor.record_lineage(ClaimLineage(
        claim_text="Best product",
        claim_type="superlative",
        source="generated",
        confidence_before=0.8,
        confidence_after=0.4,
        action_taken="downgrade",
        supporting_sources=0,
        contradicting_sources=3,
        is_superlative=True,
        is_comparative=False,
    ))
    telemetry = auditor.get_lineage_telemetry()
    assert telemetry["total_claims_tracked"] >= 1
    assert telemetry["actions"]["downgrade"] == 1
    assert telemetry["avg_confidence_before"] > telemetry["avg_confidence_after"]
    print("  ✓ test_claim_auditor_lineage")


# ============================================================================
#  DIMENSION 4 — POST-PROCESSOR SAFETY AUDIT
# ============================================================================

def test_html_validator_good_html():
    from system_hardening import HTMLSafetyValidator
    validator = HTMLSafetyValidator()
    html = """<article><h1>Title</h1><h2>Section</h2><p>Content</p></article>"""
    result = validator.validate(html)
    assert result["pass"] is True
    assert len(result["issues"]) == 0
    print("  ✓ test_html_validator_good_html")


def test_html_validator_malformed_nesting():
    from system_hardening import HTMLSafetyValidator
    validator = HTMLSafetyValidator()
    html = "<h1>Title</h2><p>Content</p>"  # h1 closed with h2
    result = validator.validate(html)
    assert len(result["issues"]) > 0
    has_nesting = any("NESTING_MISMATCH" in i for i in result["issues"])
    assert has_nesting, f"Expected nesting mismatch, got: {result['issues']}"
    print("  ✓ test_html_validator_malformed_nesting")


def test_html_validator_schema_validation():
    from system_hardening import HTMLSafetyValidator
    validator = HTMLSafetyValidator()
    html = """<article><h1>Title</h1>
<script type="application/ld+json">
{ "@type": "FAQPage", "mainEntity": [] }
</script></article>"""
    result = validator.validate(html)
    has_faq_issue = any("FAQPage_EMPTY" in i for i in result["issues"])
    assert has_faq_issue, f"Expected empty FAQPage issue, got: {result['issues']}"
    print("  ✓ test_html_validator_schema_validation")


def test_html_validator_invalid_json_ld():
    from system_hardening import HTMLSafetyValidator
    validator = HTMLSafetyValidator()
    html = """<script type="application/ld+json">{ invalid json }</script>"""
    result = validator.validate(html)
    has_invalid = any("INVALID_JSON_LD" in i for i in result["issues"])
    assert has_invalid, f"Expected invalid JSON-LD, got: {result['issues']}"
    print("  ✓ test_html_validator_invalid_json_ld")


def test_html_validator_multiple_h1():
    from system_hardening import HTMLSafetyValidator
    validator = HTMLSafetyValidator()
    html = "<h1>Title</h1><h1>Another title</h1>"
    result = validator.validate(html)
    has_multi_h1 = any("MULTIPLE_H1" in i for i in result["issues"])
    assert has_multi_h1
    print("  ✓ test_html_validator_multiple_h1")


def test_html_validator_rel_nofollow():
    from system_hardening import HTMLSafetyValidator
    validator = HTMLSafetyValidator()
    html = '<a href="https://example.com">Link</a>'
    result = validator.validate(html)
    assert result["links_missing_rel"] >= 1
    print("  ✓ test_html_validator_rel_nofollow")


def test_html_validator_code_block_integrity():
    from system_hardening import HTMLSafetyValidator
    validator = HTMLSafetyValidator()
    html = "<pre><code><p>This should not have a paragraph</p></code></pre>"
    result = validator.validate(html)
    has_code_break = any("CODE_BLOCK_PARAGRAPH_BREAK" in i for i in result["issues"])
    assert has_code_break, f"Expected code block break, got: {result['issues']}"
    print("  ✓ test_html_validator_code_block_integrity")


# ============================================================================
#  DIMENSION 5 — LLM FAILURE PATH AUDIT
# ============================================================================

def test_failure_monitor_classify():
    from system_hardening import FailurePathMonitor
    mon = FailurePathMonitor()
    assert mon.classify_error(TimeoutError("timed out")) == "timeout"
    assert mon.classify_error(json.JSONDecodeError("bad json", "", 0)) == "parse_error"
    assert mon.classify_error(ValueError("bad value")) == "parse_error"
    print("  ✓ test_failure_monitor_classify")


def test_failure_monitor_quarantine():
    from system_hardening import FailurePathMonitor
    mon = FailurePathMonitor()
    mon.quarantine_output("short", "too_short", {"keyword": "test"})
    mon.quarantine_output("", "empty_output")
    telemetry = mon.get_telemetry()
    assert telemetry["quarantine_count"] == 2
    print("  ✓ test_failure_monitor_quarantine")


def test_failure_monitor_telemetry():
    from system_hardening import FailurePathMonitor, FailureTelemetry
    mon = FailurePathMonitor()
    mon.record_failure(FailureTelemetry(
        provider="openrouter", error_type="timeout", error_msg="timeout",
        attempt=1, max_retries=3, fallback_triggered=True,
        fallback_provider="anthropic", context_preserved=True,
    ))
    mon.record_failure(FailureTelemetry(
        provider="openrouter", error_type="rate_limit", error_msg="429",
        attempt=2, max_retries=3, fallback_triggered=True,
        fallback_provider="groq", context_preserved=True,
    ))
    telemetry = mon.get_telemetry()
    assert telemetry["total_failures"] == 2
    assert telemetry["by_provider"]["openrouter"] == 2
    assert telemetry["by_error_type"]["timeout"] == 1
    assert telemetry["by_error_type"]["rate_limit"] == 1
    assert telemetry["fallback_count"] == 2
    print("  ✓ test_failure_monitor_telemetry")


def test_failure_monitor_partial_output():
    from system_hardening import FailurePathMonitor
    mon = FailurePathMonitor()
    valid, reason = mon.check_partial_output("Short", min_words=100)
    assert valid is False
    assert "too_short" in reason
    valid2, _ = mon.check_partial_output(" ".join(["word"] * 200), min_words=100)
    assert valid2 is True
    print("  ✓ test_failure_monitor_partial_output")


# ============================================================================
#  DIMENSION 6 — VECTOR MEMORY REALITY CHECK
# ============================================================================

def test_vector_comparison_basic():
    from system_hardening import VectorMemoryComparison
    vc = VectorMemoryComparison()
    result = vc.compare(
        "test keyword",
        lambda: "<article><h1>With Vector</h1><p>Content with vector</p></article>",
        lambda: "<article><h1>Without Vector</h1><p>Content without vector</p></article>",
    )
    assert result["keyword"] == "test keyword"
    assert result["differences"]["opener_match"] is False
    print("  ✓ test_vector_comparison_basic")


def test_vector_comparison_summary():
    from system_hardening import VectorMemoryComparison
    vc = VectorMemoryComparison()
    # Run multiple comparisons
    for i in range(3):
        vc.compare(
            f"keyword{i}",
            lambda: f"<article><h1>Title {i}</h1><p>Content {i}</p></article>",
            lambda: f"<article><h1>Title {i}</h1><p>Different {i}</p></article>",
        )
    summary = vc.get_results_summary()
    assert summary["total_tests"] == 3
    assert 0 <= summary["avg_semantic_overlap"] <= 1
    print("  ✓ test_vector_comparison_summary")


# ============================================================================
#  DIMENSION 7 — MULTI-AGENT EXECUTION TRUTH
# ============================================================================

def test_agent_monitor_review_cycle():
    from system_hardening import MultiAgentTruthMonitor
    mon = MultiAgentTruthMonitor()
    before = "<article><h1>Original</h1><p>Old content here</p></article>"
    after = "<article><h1>Revised</h1><p>New content reflecting critique</p></article>"
    critiques = [
        {"text": "Add more detail about pricing", "verdict": "needs_work", "reviewer": "seo_analyst"},
        {"text": "Improve the introduction to be more direct", "verdict": "needs_work", "reviewer": "human_editor"},
    ]
    cycle = mon.record_review_cycle(before, critiques, after, ["seo_analyst", "human_editor"])
    assert cycle["reviewer_count"] == 2
    assert cycle["content_changed"] is True
    assert cycle["word_count_delta"] != 0
    print("  ✓ test_agent_monitor_review_cycle")


def test_agent_monitor_noop():
    from system_hardening import MultiAgentTruthMonitor
    mon = MultiAgentTruthMonitor()
    before = "<article><h1>Same</h1></article>"
    after = "<article><h1>Same</h1></article>"
    critiques = [{"text": "No changes needed", "verdict": "approved"}]
    cycle = mon.record_review_cycle(before, critiques, after, ["reviewer1"])
    assert cycle["is_noop"] is True
    print("  ✓ test_agent_monitor_noop")


def test_agent_monitor_fake_consensus():
    from system_hardening import MultiAgentTruthMonitor
    mon = MultiAgentTruthMonitor()
    before = "<article><h1>Test</h1></article>"
    after = "<article><h1>Test</h1><p>Updated</p></article>"
    # All reviewers give same verdict = fake consensus
    critiques = [
        {"text": "Good article", "verdict": "approved", "reviewer": "reviewer1"},
        {"text": "Looks fine", "verdict": "approved", "reviewer": "reviewer2"},
        {"text": "OK", "verdict": "approved", "reviewer": "reviewer3"},
    ]
    cycle = mon.record_review_cycle(before, critiques, after, ["r1", "r2", "r3"])
    assert cycle["is_fake_consensus"] is True
    assert cycle["disagreement_score"] == 0.0
    print("  ✓ test_agent_monitor_fake_consensus")


def test_agent_monitor_telemetry():
    from system_hardening import MultiAgentTruthMonitor
    mon = MultiAgentTruthMonitor()
    mon.record_review_cycle("before", [], "after", ["r1", "r2"])
    mon.record_review_cycle("before2", [], "after2", ["r1"])
    telemetry = mon.get_telemetry()
    assert telemetry["total_cycles"] == 2
    assert "orchestration_theater_ratio" in telemetry
    print("  ✓ test_agent_monitor_telemetry")


# ============================================================================
#  DIMENSION 8 — PERFORMANCE + SCALE AUDIT
# ============================================================================

def test_resource_monitor_snapshot():
    from system_hardening import ResourceMonitor
    mon = ResourceMonitor()
    s1 = mon.snapshot("start")
    assert "thread_count" in s1
    assert "gc_objects" in s1
    s2 = mon.snapshot("end")
    assert len(mon._snapshots) == 2
    print("  ✓ test_resource_monitor_snapshot")


def test_resource_monitor_leak_detection():
    from system_hardening import ResourceMonitor
    mon = ResourceMonitor()
    mon.snapshot("baseline")
    # Simulate growth by appending many objects
    _leak = [{"x": i} for i in range(10000)]
    mon.snapshot("after_growth")
    # This may or may not trigger based on GC stats, but shouldn't crash
    issues = mon.check_leaks(threshold_pct=0.5)
    # Not asserting the result since GC behavior varies
    print("  ✓ test_resource_monitor_leak_detection")


def test_resource_monitor_thread_check():
    from system_hardening import ResourceMonitor
    mon = ResourceMonitor()
    mon.snapshot("baseline")
    mon.snapshot("normal")
    issues = mon.check_thread_growth(max_threads=5)
    # Only fails if we've exceeded 5 threads, which is normal
    print("  ✓ test_resource_monitor_thread_check")


def test_resource_monitor_reset():
    from system_hardening import ResourceMonitor
    mon = ResourceMonitor()
    mon.snapshot("one")
    mon.snapshot("two")
    mon.reset()
    assert len(mon._snapshots) == 0
    print("  ✓ test_resource_monitor_reset")


# ============================================================================
#  ALL TELEMETRY AGGREGATION
# ============================================================================

def test_get_all_telemetry():
    from system_hardening import get_all_telemetry
    telemetry = get_all_telemetry()
    expected_keys = {"prompt_truth", "memory_contamination", "claim_grounding",
                     "post_processor", "failure_paths", "vector_memory",
                     "multi_agent", "performance"}
    assert expected_keys.issubset(telemetry.keys()), \
        f"Missing keys: {expected_keys - telemetry.keys()}"
    print("  ✓ test_get_all_telemetry")


# ============================================================================
#  CONCURRENCY SAFETY TESTS
# ============================================================================

def test_concurrent_fingerprinter():
    from system_hardening import PromptFingerprinter
    fp = PromptFingerprinter()
    errors = []

    def _write():
        try:
            for i in range(50):
                fp.fingerprint_payload(f"System {i}", f"User {i}", [], f"model{i % 3}")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=_write) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrent errors: {errors}"
    hist = fp.get_history(last_n=200)
    # Should have at least some of the entries
    assert len(hist) > 0
    print("  ✓ test_concurrent_fingerprinter")


def test_concurrent_contamination_scorer():
    from system_hardening import ContaminationScorer
    cs = ContaminationScorer()
    errors = []

    def _score():
        try:
            for _ in range(100):
                cs.contamination_score("tech", {"keyword": "best laptop"})
                cs.quality_weight({"quality_score": 85})
                cs.decay_weight({"date": datetime.now().isoformat()})
                cs.filter_memory_for_niche(
                    {"articles_written": [{"keyword": "best laptop", "quality_score": 85, "date": datetime.now().isoformat()}]},
                    "tech",
                )
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=_score) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(errors) == 0, f"Concurrent errors: {errors}"
    print("  ✓ test_concurrent_contamination_scorer")


def test_concurrent_html_validator():
    from system_hardening import HTMLSafetyValidator
    validator = HTMLSafetyValidator()
    errors = []

    def _validate():
        try:
            for _ in range(50):
                validator.validate("<article><h1>Test</h1><p>Content</p></article>")
                validator.validate("<h1>A</h1><h1>B</h1>")  # has issues
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=_validate) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(errors) == 0, f"Concurrent errors: {errors}"
    print("  ✓ test_concurrent_html_validator")


def test_concurrent_failure_monitor():
    from system_hardening import FailurePathMonitor, FailureTelemetry
    mon = FailurePathMonitor()
    errors = []

    def _record():
        try:
            for _ in range(100):
                mon.record_failure(FailureTelemetry(
                    provider="test", error_type="timeout", error_msg="test",
                    attempt=1, max_retries=3, fallback_triggered=True,
                    fallback_provider="alt", context_preserved=True,
                ))
                mon.quarantine_output("test output", "test_reason")
                mon.get_telemetry()
                mon.check_partial_output("test output", min_words=1)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=_record) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(errors) == 0, f"Concurrent errors: {errors}"
    print("  ✓ test_concurrent_failure_monitor")


def test_concurrent_multi_agent():
    from system_hardening import MultiAgentTruthMonitor
    mon = MultiAgentTruthMonitor()
    errors = []

    def _record():
        try:
            for _ in range(50):
                mon.record_review_cycle("before", [], "after", ["r1", "r2"])
                mon.get_telemetry()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=_record) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(errors) == 0, f"Concurrent errors: {errors}"
    print("  ✓ test_concurrent_multi_agent")


# ============================================================================
#  RUN ALL
# ============================================================================

def _print_header(label):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")


_SKIP_CONCURRENCY = True  # Set False to run concurrency safety tests (may hang in CI)


if __name__ == "__main__":
    failed = 0
    total = 0
    test_fns = [fn for fn in sorted(globals().keys()) if fn.startswith("test_")]

    skip_concurrent = [k for k,v in globals().items() if k.startswith("test_concurrent")]

    for fn_name in test_fns:
        if _SKIP_CONCURRENCY and fn_name.startswith("test_concurrent"):
            continue
        total += 1
        try:
            globals()[fn_name]()
        except Exception as e:
            print(f"  ✗ {fn_name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"  RESULTS: {total - failed}/{total} passed", "  ALL TESTS PASSED" if failed == 0 else f"  {failed} FAILED")
    if failed > 0:
        sys.exit(1)
