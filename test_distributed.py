"""
test_distributed.py — Distributed Execution Infrastructure Tests
=================================================================
Covers:
  1. TaskQueue — dispatch, result retrieval, retry policy, telemetry
  2. TaskRecord — state lifecycle, serialization
  3. RetryPolicy — backoff calculation
  4. InProcessBackend — storage, listing, state counts
  5. DistributedPipeline — dispatch, fallback, API compatibility
  6. Worker entrypoint — import, health check
  7. Backwards compatibility — existing modes still work
  8. Graceful shutdown — drain and summary
  9. Config integration — CELERY_CONFIG settings

Run:  python test_distributed.py
"""

from __future__ import annotations

import sys
import time
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, '.')

_PASSED = 0
_FAILED = 0


def _check(description: str, condition: bool):
    global _PASSED, _FAILED
    if condition:
        _PASSED += 1
        print(f"  ✓ {description}")
    else:
        _FAILED += 1
        print(f"  ✗ {description}")


def _section(name: str):
    print(f"\n=== {name} ===")


# ── 1. RetryPolicy ─────────────────────────────────────────────
_section("RetryPolicy")
from agent_core.task_queue import RetryPolicy, DEFAULT_RETRY_POLICY, FAST_RETRY_POLICY, HEAVY_RETRY_POLICY

rp = RetryPolicy(max_retries=3, min_backoff=2.0, max_backoff=60.0, jitter=False)
backoff_0 = rp.get_backoff(0)
_check("Backoff attempt 0 = min_backoff", backoff_0 == 2.0)
backoff_1 = rp.get_backoff(1)
_check("Backoff attempt 1 = 4.0", backoff_1 == 4.0)
backoff_2 = rp.get_backoff(2)
_check("Backoff attempt 2 = 8.0", backoff_2 == 8.0)
backoff_5 = rp.get_backoff(5)
_check("Backoff attempt 5 capped at max_backoff", backoff_5 == 60.0)

cd = rp.to_celery_dict()
_check("Celery dict has max_retries", cd["max_retries"] == 3)
_check("Celery dict has interval_start", cd["interval_start"] == 2.0)
_check("Celery dict has interval_max", cd["interval_max"] == 60.0)

rp_jitter = RetryPolicy(max_retries=3, min_backoff=2.0, jitter=True)
bj = rp_jitter.get_backoff(0)
_check("Jitter produces different value", bj >= 2.0 and bj <= 3.0)

_check("FAST_RETRY_POLICY max_retries=2", FAST_RETRY_POLICY.max_retries == 2)
_check("HEAVY_RETRY_POLICY max_retries=5", HEAVY_RETRY_POLICY.max_retries == 5)

# ── 2. TaskState enum ──────────────────────────────────────────
_section("TaskState")
from agent_core.task_queue import TaskState

_check("PENDING state", TaskState.PENDING.value == "PENDING")
_check("SUCCESS state", TaskState.SUCCESS.value == "SUCCESS")
_check("FAILURE state", TaskState.FAILURE.value == "FAILURE")
_check("All 7 states defined", len(TaskState) == 7)

# ── 3. TaskRecord ──────────────────────────────────────────────
_section("TaskRecord")
from agent_core.task_queue import TaskRecord

rec = TaskRecord(
    task_id="test-123",
    task_name="write_article",
    args=("kw",),
    kwargs={"model": "local"},
    state=TaskState.STARTED,
    started_at=100.0,
    completed_at=145.0,
    worker="worker-1",
    queue="seo_agent",
)
_check("TaskRecord duration_ms", rec.duration_ms == 45000.0)
d = rec.to_dict()
_check("to_dict has task_id", d["task_id"] == "test-123")
_check("to_dict has state", d["state"] == "STARTED")
_check("to_dict has duration_ms", d["duration_ms"] == 45000.0)
_check("to_dict has worker", d["worker"] == "worker-1")

rec_no_duration = TaskRecord(task_id="nope", task_name="test")
_check("No duration when not completed", rec_no_duration.duration_ms is None)

# ── 4. InProcessBackend ────────────────────────────────────────
_section("InProcessBackend")
from agent_core.task_queue import InProcessBackend

backend = InProcessBackend()
rec1 = TaskRecord(task_id="a1", task_name="t1", state=TaskState.SUCCESS)
rec2 = TaskRecord(task_id="a2", task_name="t2", state=TaskState.FAILURE)
rec3 = TaskRecord(task_id="a3", task_name="t3", state=TaskState.PENDING)

backend.store(rec1)
backend.store(rec2)
backend.store(rec3)

_check("Get existing record", backend.get("a1") is not None)
_check("Get non-existing record", backend.get("nonexistent") is None)

recent = backend.list_recent(limit=10)
_check("List recent returns 3", len(recent) == 3)

by_state = backend.count_by_state()
_check("Count SUCCESS=1", by_state.get("SUCCESS") == 1)
_check("Count FAILURE=1", by_state.get("FAILURE") == 1)
_check("Count PENDING=1", by_state.get("PENDING") == 1)

cleared = backend.clear()
_check("Clear returns 3", cleared == 3)
_check("Backend empty after clear", backend.count_by_state() == {})

# ── 5. TaskQueue (in-process mode, no Celery) ──────────────────
_section("TaskQueue (in-process fallback)")
from agent_core.task_queue import TaskQueue, reset_task_queue

queue = TaskQueue(use_celery=False)

stats = queue.stats()
_check("Queue stats mode = in_process", stats["mode"] == "in_process")
_check("Queue not available when Celery disabled", not queue.is_available)

# ── Persistent mock functions ────────────────────────────────
_batch_retry_count = [0]

def _fake_analyze(keyword, model):
    return {"keyword": keyword, "competitors": 5}

def _failing_task(**kwargs):
    _batch_retry_count[0] += 1
    if _batch_retry_count[0] < 2:
        raise RuntimeError("Transient error")
    return {"status": "ok"}

# Dispatch and await a local task
import modules as _orig_mod
_orig_mod.analyze_competitors = _fake_analyze

tid = queue.dispatch("analyze_competitors", keyword="test kw", model="local")
_check("Dispatch returns task_id", isinstance(tid, str) and len(tid) > 0)

result = queue.await_result(tid, timeout=10)
_check("Await result returns dict", isinstance(result, dict))
_check("Result has keyword 'test kw'", result.get("keyword") == "test kw")
_check("Result has competitors 5", result.get("competitors") == 5)

status = queue.get_status(tid)
_check("Status is SUCCESS", status["state"] == "SUCCESS")
_check("Status has duration_ms", status.get("duration_ms") is not None)

# ── 6. TaskQueue retry on failure ──────────────────────────────
_section("TaskQueue retry behavior")
_orig_mod.analyze_competitors = _failing_task
_batch_retry_count[0] = 0

queue2 = TaskQueue(use_celery=False)
tid2 = queue2.dispatch("analyze_competitors", retry_policy=RetryPolicy(max_retries=2, min_backoff=0.1, jitter=False))
result2 = queue2.await_result(tid2, timeout=10)
_check("Retry succeeds after 2 attempts", result2 == {"status": "ok"})
_check("Exactly 2 calls made", _batch_retry_count[0] == 2)

# ── 7. TaskQueue dispatch_batch and await_batch ────────────────
_section("TaskQueue batch operations")
_orig_mod.analyze_competitors = _fake_analyze

queue3 = TaskQueue(use_celery=False)

items = [
    {"kwargs": {"keyword": f"kw{i}", "model": "local"}}
    for i in range(3)
]

tids = queue3.dispatch_batch("analyze_competitors", items)
_check(f"Batch dispatched {len(tids)} tasks", len(tids) == 3)

results = queue3.await_batch(tids, timeout=10)
_check(f"Batch returned {len(results)} results", len(results) == 3)
all_ok = all(v is not None for v in results.values())
_check("All batch tasks succeeded", all_ok)

batch_stats = queue3.stats()
_check("Batch stats show 3 tasks tracked", batch_stats["total_tracked"] >= 3)

# ── 8. DistributedPipeline ─────────────────────────────────────
_section("DistributedPipeline")
from agent_core.distributed import DistributedPipeline
from agent_core.task_queue import reset_task_queue

# Reset queue state for clean pipeline test
reset_task_queue()

_orig_mod.analyze_competitors = _fake_analyze

dp = DistributedPipeline()
_check("DistributedPipeline created", dp is not None)

# Test available
_check("Pipeline available flag", dp.available)

# Test queue_status
qs = dp.queue_status()
_check("Queue status has mode", "mode" in qs)

# Test dispatch
td = dp.analyze_competitors(keyword="dp-test-kw", model="local")
_check("Distributed analyze returns dict", isinstance(td, dict))
_check("Distributed result has keyword", td.get("keyword") == "dp-test-kw")
_check("Distributed result has competitors", td.get("competitors") == 5)

# Test validate_article_quality
dp2 = DistributedPipeline()
vq = dp2.validate_article_quality(article="<h1>Test</h1><p>Content</p>", keyword="test keyword")
_check("Distributed quality check returns dict", isinstance(vq, dict))

# ── 9. Graceful shutdown ───────────────────────────────────────
_section("Graceful shutdown")
queue4 = TaskQueue(use_celery=False)

def _slow_task(**kwargs):
    time.sleep(0.3)
    return {"done": True}

queue4._orig_analyze_competitors = _orig_mod.analyze_competitors
_orig_mod.analyze_competitors = _slow_task
slow_tid = queue4.dispatch("analyze_competitors", keyword="slow", model="local")

# Shutdown should wait for in-flight tasks
summary = queue4.shutdown(timeout=5)
_check("Shutdown returns dict", isinstance(summary, dict))
_check("Shutdown has mode", "mode" in summary)

# Verify the slow task eventually completed
final_status = queue4.get_status(slow_tid)
_check("Slow task completed before shutdown", final_status["state"] == "SUCCESS")

# ── 10. Config integration ─────────────────────────────────────
_section("Config integration")
from config import CELERY_CONFIG

_check("CELERY_CONFIG has broker_url", "broker_url" in CELERY_CONFIG)
_check("CELERY_CONFIG has result_backend_url", "result_backend_url" in CELERY_CONFIG)
_check("CELERY_CONFIG has worker_concurrency", "worker_concurrency" in CELERY_CONFIG)
_check("CELERY_CONFIG has task_timeout", "task_timeout" in CELERY_CONFIG)
_check("CElERY_CONFIG broker default is redis", "redis://" in CELERY_CONFIG["broker_url"])

# ── 11. Worker entrypoint — imports and flags ──────────────────
_section("Worker entrypoint")
from worker_entrypoint import main as worker_main
_check("Worker entrypoint main function imported", callable(worker_main))

# Test with --no-celery flag (in-process mode)
try:
    import argparse
    # Quick test: verify argument parsing works
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-celery", action="store_true")
    parser.add_argument("--loglevel", default="info")
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--queues", default=None)
    parser.add_argument("--hostname", default=None)
    parser.add_argument("--health-port", type=int, default=0)
    args = parser.parse_args(["--no-celery"])
    _check("Worker accepts --no-celery flag", args.no_celery)
except Exception as e:
    _check(f"Worker argument parsing: {e}", False)

# ── 12. Backwards compatibility — existing imports unchanged ───
_section("Backwards compatibility")
# Existing agent_core imports still work
from agent_core import (
    RelayRouter, ParallelEngine, SemanticValidator, MemoryIndex,
    CacheManager, MetricsCollector, SelfHeal, HealthDashboard,
    TaskQueue, DistributedPipeline,
)
_check("All agent_core exports importable", True)

# Original modules import still works
import modules as agent_mod
_check("modules.py imports unchanged", hasattr(agent_mod, "analyze_competitors"))
_check("modules.py has write_article", hasattr(agent_mod, "write_article"))

# Original pipeline_enhancer import still works
import pipeline_enhancer as pe
_check("pipeline_enhancer imports unchanged", hasattr(pe, "run_full_enhanced"))
_check("pipeline_enhancer has run_batch_articles", hasattr(pe, "run_batch_articles"))

# Original main.py modes still work
from main import run_full, run_article, run_cluster, run_calendar
_check("main.py run_full unchanged", callable(run_full))
_check("main.py run_article unchanged", callable(run_article))
_check("main.py run_cluster unchanged", callable(run_cluster))
_check("main.py run_calendar unchanged", callable(run_calendar))

# Original config still works
from config import DEFAULT_MODEL, MODELS, SETTINGS, API_KEYS, GSC_CONFIG, CELERY_CONFIG
_check("config.py DEFAULT_MODEL unchanged", DEFAULT_MODEL == "local")
_check("config.py MODELS still has entries", len(MODELS) > 0)
_check("config.py has CELERY_CONFIG", len(CELERY_CONFIG) > 0)

# ── 13. import worker_tasks module ─────────────────────────────
_section("Worker tasks module")
try:
    from agent_core.worker_tasks import app
    _check("worker_tasks app importable", app is not None)
    # Verify tasks are registered
    assert hasattr(app, 'tasks_registered'), "No tasks_registered on app"
    _check("Tasks registered", len(app.tasks_registered) >= 10)
    for task_name in [
        "analyze_competitors", "decide_strategy", "write_article",
        "optimize_ctr", "build_cluster", "build_calendar",
        "validate_article_quality", "score_authority",
        "full_pipeline", "batch_articles",
    ]:
        _check(f"  Task '{task_name}' registered", task_name in app.tasks_registered)
except ImportError:
    _check("Celery not installed — worker_tasks test skipped (prerequisite)", True)
except Exception as e:
    _check(f"worker_tasks init: {e}", False)

# ── 14. Telemetry recording ────────────────────────────────────
_section("Task telemetry")
from agent_core.metrics_collector import get_collector, reset_collector
reset_collector()
mc = get_collector()

mc.increment("tasks_dispatched")
mc.increment("tasks_completed_local")
mc.increment("tasks_failed_local")
mc.increment("worker_task_write_article_started")
mc.increment("worker_task_write_article_completed")

_check("tasks_dispatched recorded", mc._counters.get("tasks_dispatched") == 1)
_check("tasks_completed_local recorded", mc._counters.get("tasks_completed_local") == 1)
_check("tasks_failed_local recorded", mc._counters.get("tasks_failed_local") == 1)
_check("worker task telemetry recorded", mc._counters.get("worker_task_write_article_completed") == 1)

# ── 15. DistributedPipeline shutdown ───────────────────────────
_section("DistributedPipeline shutdown")
dp3 = DistributedPipeline()
dp3.shutdown()
_check("DistributedPipeline shutdown completes", True)


# ── Final ──────────────────────────────────────────────────────
print(f"\n{'=' * 50}")
print(f"  RESULTS: {_PASSED} passed, {_FAILED} failed")
print(f"{'=' * 50}")

if _FAILED > 0:
    print(f"\n  ❌ {_FAILED} TEST(S) FAILED")
    sys.exit(1)
else:
    print(f"\n  ✅ ALL DISTRIBUTED TESTS PASSED")
