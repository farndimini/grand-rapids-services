"""
test_metrics_store.py — Tests for persistent metrics store.
Run: python test_metrics_store.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '.')

print("=== Testing MetricsStore ===")
from agent_core.metrics_store import MetricsStore

td = tempfile.mkdtemp()
try:
    db = Path(td) / "test_metrics.db"
    store = MetricsStore(db_path=db)

    # Record sample data
    store.record_latency("write_article", 1500.0, True, model="gpt-4o")
    store.record_latency("write_article", 2000.0, False, error="timeout")
    store.record_provider_call("openrouter", 3200.0, True, tokens=1200, cost_usd=0.004)
    store.record_provider_call("groq", 500.0, True, tokens=800, cost_usd=0.0005)
    store.record_provider_call("openrouter", 8000.0, False, error="rate_limit")
    store.record_cache("llm", hit=True)
    store.record_cache("llm", hit=False)
    store.record_cache("serp", hit=True)
    store.record_quality("best laptop", score=78, reward=0.3, eeat_score=65)
    store.record_quality("best laptop", score=85, reward=0.6, eeat_score=72)
    store.record_ranking("best laptop", position=12, ctr=2.5, impressions=1500, clicks=38)
    store.record_rewrite("best laptop", attempt=1, score_before=60, score_after=78)
    store.record_tokens("openrouter", 1200, 0.004)

    # Queries
    trend = store.get_latency_trend("write_article", days=1)
    assert trend["count"] == 2
    assert "p50" in trend

    health = store.get_provider_health(days=1)
    assert "openrouter" in health
    assert health["openrouter"]["calls"] == 2
    assert health["groq"]["success_rate"] == 1.0

    cache = store.get_cache_ratio(days=1)
    assert cache["llm"]["total"] == 2
    assert cache["llm"]["hit_rate"] == 0.5

    qual = store.get_quality_trend(days=1)
    assert qual["count"] == 2
    assert qual["avg_score"] == 81.5

    rewrite = store.get_rewrite_effectiveness(days=1)
    assert rewrite["count"] == 1
    assert rewrite["avg_improvement"] == 18

    summary = store.full_summary(days=1)
    assert "provider_health" in summary
    assert "fallback_failures" in summary

    # Cleanup
    cleaned = store.cleanup_old(days=0)
    assert sum(cleaned.values()) > 0

    print("  MetricsStore OK")
finally:
    import shutil
    try:
        shutil.rmtree(td)
    except PermissionError:
        pass

print("\n=== ALL METRICS STORE TESTS PASSED ===")
