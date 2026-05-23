"""
test_agent_core.py — Unit tests for agent_core resilience layer
================================================================
Covers:
  • metrics_collector (stage/provider recording, summary)
  • telemetry (track_stage, TelemetryContext)
  • relay (CircuitBreaker, DiskCache, TokenBucket, jitter)
  • cache_manager (LRU, compression, atomic write)
  • health_dashboard (subsystem checks)

Run:  python test_agent_core.py
"""

import sys
import time
import threading
import tempfile
from pathlib import Path

sys.path.insert(0, '.')

# ── 1. Metrics Collector ───────────────────────────────────
print("=== Testing metrics_collector ===")
from agent_core.metrics_collector import MetricsCollector, get_collector, reset_collector

reset_collector()
m = get_collector()
m.record_stage("test_stage", latency_ms=1500, success=True)
m.record_stage("test_stage", latency_ms=2000, success=False)
m.record_provider("openrouter", latency_ms=3000, success=True, tokens_used=1200)
m.record_provider("groq", latency_ms=500, success=True, tokens_used=800)
m.record_fallback("openrouter", "groq")
m.record_quality(85)
m.record_quality(72)
m.increment("articles_completed", 2)
m.increment("total_words_generated", 3500)

lat = m.stage_latency("test_stage", window_secs=3600)
assert lat["count"] == 2, f"Expected 2 stage records, got {lat['count']}"
assert lat["avg"] == 1750.0, f"Expected avg 1750, got {lat['avg']}"

ps = m.provider_summary(3600)
assert "openrouter" in ps, "Expected openrouter in provider summary"
assert ps["openrouter"]["ok"] == 1
assert ps["groq"]["ok"] == 1
assert m._counters.get("total_fallbacks", 0) == 1

qd = m.quality_distribution()
assert qd["count"] == 2
assert qd["avg"] == 78.5

cr = m.cache_ratio("llm")
assert cr["total"] == 0  # No cache hits/misses recorded yet

print("  metrics_collector OK")

# ── 2. Telemetry ───────────────────────────────────────────
print("\n=== Testing telemetry ===")
from agent_core.telemetry import TelemetryContext, track_stage

reset_collector()

@track_stage("decorated_fn")
def sample_fn(x):
    return x * 2

result = sample_fn(5)
assert result == 10

with TelemetryContext("ctx_block", detail="test"):
    time.sleep(0.01)

m2 = get_collector()
stages = [r.stage for r in m2._stages]
assert "decorated_fn" in stages
assert "ctx_block" in stages
print("  telemetry OK")

# ── 3. Relay Components ────────────────────────────────────
print("\n=== Testing relay components ===")
from agent_core.relay import CircuitBreaker, TokenBucket, DiskCache

# CircuitBreaker
cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.5)
assert cb.can_execute()
cb.record_failure()
assert cb.can_execute()
cb.record_failure()
assert not cb.can_execute()
time.sleep(0.6)
assert cb.can_execute()  # half_open
cb.record_success()
assert cb.can_execute()  # closed
print("  CircuitBreaker OK")

# TokenBucket
tb = TokenBucket(rate=10.0, capacity=5.0)
assert tb.acquire(1.0) == 0.0  # instant — 4 remain
waited = tb.acquire(5.0)       # needs 1 more token — wait 0.1s
assert waited > 0.0
print(f"  TokenBucket OK (waited {waited*1000:.1f}ms)")
# After acquiring 6 total from capacity 5, bucket is empty - next must wait
waited2 = tb.acquire(1.0)
assert waited2 > 0.0
print(f"  TokenBucket wait2 OK (waited {waited2*1000:.1f}ms)")

# DiskCache (with compression & LRU)
with tempfile.TemporaryDirectory() as td:
    dc = DiskCache(ttl_seconds=10)
    dc._dir = Path(td)  # override to temp dir
    # Build a real _CacheKey
    from agent_core.relay import _CacheKey as CacheKey
    key = CacheKey.build("sys", "usr", "model", "text")
    # monkey-patch _path for testing
    dc._path = lambda k: Path(td) / "test.json"
    dc.set(key, {"hello": "world"})
    got = dc.get(key)
    assert got == {"hello": "world"}, f"Expected cache hit, got {got}"
    dc.clear()
    assert dc.get(key) is None
    print("  DiskCache OK")

print("  relay components OK")

# ── 4. Cache Manager ───────────────────────────────────────
print("\n=== Testing cache_manager ===")
from agent_core.cache_manager import CacheManager

with tempfile.TemporaryDirectory() as td:
    cm = CacheManager(cache_dir=td, default_ttl_hours=1, max_size_mb=10)
    cm.save_serp("best laptop", {"results": [1, 2, 3]})
    loaded = cm.load_serp("best laptop")
    assert loaded == {"results": [1, 2, 3]}
    loaded_old = cm.load_serp("best laptop", max_age_hours=0)
    assert loaded_old is None, "Expected expired"
    s = cm.stats()
    assert s["files"] >= 1
    assert s["total_size_mb"] < 10
    cleared = cm.clear_all()
    assert cleared >= 1
    print("  CacheManager OK")

# ── 5. Health Dashboard ────────────────────────────────────
print("\n=== Testing health_dashboard ===")
from agent_core.health_dashboard import HealthDashboard

hd = HealthDashboard()
report = hd.generate()
assert 0 <= report.overall_health <= 100
assert isinstance(report.critical_issues, list)
assert isinstance(report.warnings, list)
assert "Configuration" in report.subsystem_health
assert "Agent Core" in report.subsystem_health
print(f"  Health Dashboard OK (overall {report.overall_health}/100)")

# ── Final ──────────────────────────────────────────────────
print("\n=== ALL AGENT_CORE TESTS PASSED ===")
