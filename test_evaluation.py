"""
test_evaluation.py — Tests for evaluation harness (Phase 3).
Run: python test_evaluation.py
"""

import sys
sys.path.insert(0, '.')

print("=== Testing Scorers ===")
from evaluation.scorers import SemanticScorer, StructureScorer, SERPScorer, ReadabilityScorer

sem = SemanticScorer()
r = sem.score("The best CRM software in 2026 includes Salesforce and HubSpot with detailed comparison.", "best CRM software")
assert 0 <= r.score <= 100
assert "cosine_similarity" in r.details
print(f"  SemanticScorer: {r.score:.1f}")

struct = StructureScorer()
r2 = struct.score("<h1>Best CRM</h1><h2>Comparison</h2><h2>FAQ</h2><table><tr><td>A</td></tr></table><script type=\"application/ld+json\">{\"@type\":\"Article\"}</script><script type=\"application/ld+json\">{\"@type\":\"FAQPage\"}</script>", "best CRM")
assert r2.score >= 70  # has H1, H2s, table, schemas
print(f"  StructureScorer: {r2.score:.1f}")

serp = SERPScorer()
r3 = serp.score("<h1>Best CRM</h1><p>" + "word " * 1500 + "</p>", "best CRM", {"average_word_count": 2000, "content_gaps": ["pricing", "integration"]})
assert 0 <= r3.score <= 100
print(f"  SERPScorer: {r3.score:.1f}")

read = ReadabilityScorer()
r4 = read.score("The quick brown fox jumps over the lazy dog. " * 50)
assert 0 <= r4.score <= 100
assert "flesch_kincaid_ease" in r4.details
print(f"  ReadabilityScorer: {r4.score:.1f}")

print("\n=== Testing BenchmarkRunner ===")
from evaluation.benchmark_runner import BenchmarkRunner
import tempfile

with tempfile.TemporaryDirectory() as td:
    runner = BenchmarkRunner(dataset_dir=td)
    html = "<h1>Best Laptop</h1><h2>Comparison</h2><h2>FAQ</h2><table><tr><td>X</td></tr></table><div class='quick-answer-box'>Answer</div><script type=\"application/ld+json\">{\"@type\":\"Article\"}</script><script type=\"application/ld+json\">{\"@type\":\"FAQPage\"}</script>" + "<p>" + ("content " * 400) + "</p>"
    report = runner.evaluate(html, "best laptop", serp_data={"average_word_count": 1800, "content_gaps": ["hidden costs"]}, model="gpt-4o")
    assert 0 <= report.final_score <= 100
    assert report.verdict
    assert "semantic" in report.dimension_scores
    print(f"  BenchmarkRunner final: {report.final_score:.1f} [{report.verdict}]")

    # Leaderboard
    leaders = runner.leaderboard("best_laptop")
    assert len(leaders) >= 1
    print(f"  Leaderboard entries: {len(leaders)}")

print("\n=== Testing Datasets ===")
from evaluation.datasets import EvaluationDataset

with tempfile.TemporaryDirectory() as td:
    ds = EvaluationDataset(base_dir=td)
    from evaluation.datasets import DatasetEntry
    ds.add(DatasetEntry(keyword="k1", model="m1", prompt_variant="v1", final_score=75, article_hash="abc"))
    ds.add(DatasetEntry(keyword="k1", model="m2", prompt_variant="v2", final_score=85, article_hash="def"))
    baseline = ds.get_baseline("k1")
    assert baseline is not None
    reg = ds.regression_check("k1", 70)
    assert reg["regression"] is True  # 70 < baseline ~80
    best = ds.best_for_keyword("k1")
    assert best["score"] == 85
    print(f"  Dataset regression check OK (baseline={baseline})")

print("\n=== ALL EVALUATION TESTS PASSED ===")
