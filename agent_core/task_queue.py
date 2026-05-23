"""
task_queue.py — Durable Task Queue with Celery + Redis
=======================================================
Provides:
  • Celery app with Redis broker and result backend
  • Configurable retry policies (max_retries, exponential backoff, jitter)
  • Task persistence with result expiry
  • Structured telemetry integration
  • Graceful shutdown support

Usage:
    from agent_core.task_queue import get_task_queue
    queue = get_task_queue()
    queue.dispatch("analyze_competitors", keyword="best laptop", model="local")
    result = queue.await_result(task_id, timeout=120)

Decorator for Celery tasks:
    from agent_core.task_queue import seo_task
    @seo_task
    def my_task(keyword, model):
        ...
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from config import CELERY_CONFIG

log = logging.getLogger("agent_core.task_queue")


class TaskState(str, Enum):
    PENDING = "PENDING"
    RECEIVED = "RECEIVED"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    REVOKED = "REVOKED"
    RETRY = "RETRY"


@dataclass
class TaskRecord:
    task_id: str
    task_name: str
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    state: TaskState = TaskState.PENDING
    result: Any = None
    error: str | None = None
    retries: int = 0
    max_retries: int = 3
    created_at: float = 0.0
    started_at: float | None = None
    completed_at: float | None = None
    worker: str | None = None
    queue: str = "default"

    @property
    def duration_ms(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at) * 1000
        return None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "state": self.state.value,
            "result": _safe_serialize(self.result),
            "error": self.error,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "duration_ms": self.duration_ms,
            "worker": self.worker,
            "queue": self.queue,
        }


def _safe_serialize(obj: Any) -> Any:
    if obj is None:
        return None
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)[:500]


class RetryPolicy:
    """Exponential backoff with jitter for Celery tasks."""

    def __init__(
        self,
        max_retries: int = 3,
        min_backoff: float = 2.0,
        max_backoff: float = 60.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.min_backoff = min_backoff
        self.max_backoff = max_backoff
        self.jitter = jitter

    def get_backoff(self, attempt: int) -> float:
        import random
        delay = min(self.max_backoff, self.min_backoff * (2 ** attempt))
        if self.jitter:
            delay += random.uniform(0, delay * 0.5)
        return delay

    def to_celery_dict(self) -> dict:
        return {
            "max_retries": self.max_retries,
            "interval_start": self.min_backoff,
            "interval_step": 2.0,
            "interval_max": self.max_backoff,
        }


# Default policies
DEFAULT_RETRY_POLICY = RetryPolicy(max_retries=3, min_backoff=2.0)
FAST_RETRY_POLICY = RetryPolicy(max_retries=2, min_backoff=1.0, max_backoff=10.0)
HEAVY_RETRY_POLICY = RetryPolicy(max_retries=5, min_backoff=5.0, max_backoff=120.0)


class InProcessBackend:
    """Fallback backend when Redis is unavailable — stores results in memory.

    This ensures the system works even without Redis running, at the cost
    of not being durable across process restarts.
    """

    def __init__(self):
        self._results: dict[str, TaskRecord] = {}
        self._lock = threading.Lock()

    def store(self, record: TaskRecord) -> None:
        with self._lock:
            self._results[record.task_id] = record

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self._results.get(task_id)

    def list_by_state(self, state: TaskState, limit: int = 50) -> list[TaskRecord]:
        with self._lock:
            matching = [r for r in self._results.values() if r.state == state]
            return sorted(matching, key=lambda r: r.created_at, reverse=True)[:limit]

    def list_recent(self, limit: int = 50) -> list[TaskRecord]:
        with self._lock:
            return sorted(self._results.values(), key=lambda r: r.created_at, reverse=True)[:limit]

    def count_by_state(self) -> dict[str, int]:
        with self._lock:
            counts: dict[str, int] = {}
            for r in self._results.values():
                counts[r.state.value] = counts.get(r.state.value, 0) + 1
            return counts

    def clear(self) -> int:
        with self._lock:
            n = len(self._results)
            self._results.clear()
            return n


class TaskQueue:
    """Durable task queue — dispatches work to Celery workers or runs in-process.

    Features:
      • Automatic fallback to in-process execution when Redis is unavailable
      • Configurable retry policies per task type
      • Structured telemetry via MetricsCollector
      • Task persistence with result expiry
      • Graceful shutdown (drain in-flight tasks)
    """

    def __init__(
        self,
        broker_url: str = "",
        result_backend_url: str = "",
        default_queue: str = "seo_agent",
        default_retry_policy: RetryPolicy | None = None,
        use_celery: bool | None = None,
        metrics_collector: Any = None,
    ):
        self._broker_url = broker_url or CELERY_CONFIG.get("broker_url", "")
        self._result_backend_url = result_backend_url or CELERY_CONFIG.get("result_backend_url", "")
        self._default_queue = default_queue
        self._retry_policy = default_retry_policy or DEFAULT_RETRY_POLICY
        self._celery_app = None
        self._started = time.time()

        # Metrics
        self._metrics = metrics_collector
        if self._metrics is None:
            try:
                from agent_core.metrics_collector import get_collector
                self._metrics = get_collector()
            except Exception:
                self._metrics = None

        # Fallback backend
        self._local_backend = InProcessBackend()

        # Shutdown coordination
        self._shutdown_event = threading.Event()
        self._in_flight: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

        # Decide execution mode
        if use_celery is None:
            use_celery = bool(self._broker_url)
        self._use_celery = use_celery

        if self._use_celery:
            self._init_celery()

    def _init_celery(self) -> None:
        """Lazy-init the Celery app."""
        if self._celery_app is not None:
            return
        try:
            from celery import Celery
            self._celery_app = Celery(
                "seo_agent",
                broker=self._broker_url,
                backend=self._result_backend_url,
                include=["agent_core.worker_tasks"],
            )
            self._celery_app.conf.update(
                task_serializer="json",
                result_serializer="json",
                accept_content=["json"],
                result_expires=3600,
                task_track_started=True,
                task_acks_late=True,
                worker_prefetch_multiplier=1,
                worker_concurrency=CELERY_CONFIG.get("worker_concurrency", 4),
                task_default_queue=self._default_queue,
                task_queues={
                    self._default_queue: {"exchange": self._default_queue, "routing_key": self._default_queue},
                    "intelligence": {"exchange": "intelligence", "routing_key": "intelligence"},
                    "batch": {"exchange": "batch", "routing_key": "batch"},
                },
            )
            log.info(f"[TASK-QUEUE] Celery initialized (broker={self._broker_url})")
        except ImportError:
            log.warning("[TASK-QUEUE] Celery not installed — falling back to in-process execution")
            self._use_celery = False
        except Exception as e:
            log.warning(f"[TASK-QUEUE] Celery init failed: {e} — falling back to in-process execution")
            self._use_celery = False

    @property
    def is_available(self) -> bool:
        return self._use_celery and self._celery_app is not None

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._started

    # ── Dispatch ─────────────────────────────────────────────

    def dispatch(
        self,
        task_name: str,
        *args,
        queue: str | None = None,
        retry_policy: RetryPolicy | None = None,
        task_id: str | None = None,
        **kwargs,
    ) -> str:
        """Dispatch a task to the queue.

        Returns the task_id for result retrieval.
        If Celery is unavailable, executes synchronously and stores result locally.
        """
        import uuid
        tid = task_id or str(uuid.uuid4())
        q = queue or self._default_queue
        policy = retry_policy or self._retry_policy

        record = TaskRecord(
            task_id=tid,
            task_name=task_name,
            args=args,
            kwargs=kwargs,
            state=TaskState.RECEIVED,
            max_retries=policy.max_retries,
            created_at=time.time(),
            queue=q,
        )
        self._local_backend.store(record)

        if self.is_available and self._celery_app:
            self._dispatch_celery(tid, task_name, args, kwargs, q, policy)
        else:
            self._dispatch_local(tid, task_name, args, kwargs, policy)

        return tid

    def _dispatch_celery(
        self,
        tid: str,
        task_name: str,
        args: tuple,
        kwargs: dict,
        queue: str,
        policy: RetryPolicy,
    ) -> None:
        """Dispatch via Celery async task."""
        try:
            task_ref = self._celery_app.tasks.get(task_name)
            if task_ref is None:
                raise ValueError(f"Task '{task_name}' not registered in Celery")

            async_result = task_ref.apply_async(
                args=args,
                kwargs=kwargs,
                task_id=tid,
                queue=queue,
                retry_policy=policy.to_celery_dict(),
            )
            with self._lock:
                self._in_flight[tid] = threading.Event()

            if self._metrics:
                self._metrics.increment("tasks_dispatched")
                self._metrics.increment(f"tasks_dispatched_{queue}")

            log.info(f"[TASK-QUEUE] Dispatched {task_name} [{tid[:8]}] → {queue}")
        except Exception as e:
            log.warning(f"[TASK-QUEUE] Celery dispatch failed: {e} — running locally")
            self._dispatch_local(tid, task_name, args, kwargs, policy)

    def _dispatch_local(self, tid: str, task_name: str, args: tuple, kwargs: dict, policy: RetryPolicy) -> None:
        """Execute task in-process (fallback or when Celery is not configured)."""
        record = self._local_backend.get(tid)
        if record:
            record.state = TaskState.STARTED
            record.started_at = time.time()
            self._local_backend.store(record)

        with self._lock:
            self._in_flight[tid] = threading.Event()

        last_error: Exception | None = None
        for attempt in range(1 + policy.max_retries):
            try:
                result = self._run_task_local(task_name, *args, **kwargs)
                if record:
                    record.state = TaskState.SUCCESS
                    record.result = result
                    record.completed_at = time.time()
                    record.retries = attempt
                    self._local_backend.store(record)
                with self._lock:
                    if tid in self._in_flight:
                        self._in_flight[tid].set()
                if self._metrics:
                    self._metrics.increment("tasks_completed_local")
                return
            except Exception as e:
                last_error = e
                if attempt < policy.max_retries:
                    backoff = policy.get_backoff(attempt)
                    log.warning(f"[TASK-QUEUE] Local retry {attempt+1}/{policy.max_retries} for {task_name} after {backoff:.1f}s: {e}")
                    time.sleep(backoff)
                else:
                    log.error(f"[TASK-QUEUE] Local task {task_name} failed after {policy.max_retries} retries: {e}")

        if record:
            record.state = TaskState.FAILURE
            record.error = str(last_error)
            record.completed_at = time.time()
            record.retries = policy.max_retries
            self._local_backend.store(record)
        with self._lock:
            if tid in self._in_flight:
                self._in_flight[tid].set()
        if self._metrics:
            self._metrics.increment("tasks_failed_local")

    _TASK_MAP: dict[str, tuple[str, str]] = {
        "analyze_competitors": ("modules", "analyze_competitors"),
        "decide_strategy": ("modules", "decide_strategy"),
        "write_article": ("modules", "write_article"),
        "optimize_ctr": ("modules", "optimize_ctr"),
        "build_cluster": ("modules", "build_cluster"),
        "build_calendar": ("modules", "build_calendar"),
        "validate_article_quality": ("modules", "validate_article_quality"),
        "score_authority": ("modules", "score_authority"),
        "full_pipeline": ("pipeline_enhancer", "run_full_enhanced"),
        "batch_articles": ("pipeline_enhancer", "run_batch_articles"),
    }

    def _run_task_local(self, task_name: str, *args, **kwargs) -> Any:
        """Resolve and call the local task function (lazy import)."""
        entry = self._TASK_MAP.get(task_name)
        if entry is None:
            raise ValueError(f"Unknown local task: {task_name}")
        fn = self._import_task(*entry)
        return fn(*args, **kwargs)

    @staticmethod
    def _import_task(module_name: str, func_name: str) -> Callable:
        import importlib
        mod = importlib.import_module(module_name)
        return getattr(mod, func_name)

    # ── Result retrieval ─────────────────────────────────────

    def get_result(self, task_id: str, timeout: float | None = None) -> TaskRecord | None:
        """Get task result. Blocks up to `timeout` seconds if task is in-flight."""
        record = self._local_backend.get(task_id)
        if record is None:
            return None

        if record.state in (TaskState.PENDING, TaskState.RECEIVED, TaskState.STARTED, TaskState.RETRY):
            event = self._get_event(task_id)
            if event is not None:
                event.wait(timeout=timeout)

        return self._local_backend.get(task_id)

    def _get_event(self, task_id: str) -> threading.Event | None:
        with self._lock:
            return self._in_flight.get(task_id)

    def await_result(self, task_id: str, timeout: float = 120.0, poll_interval: float = 0.5) -> Any:
        """Block until task completes and return its result."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            record = self._local_backend.get(task_id)
            if record and record.state in (TaskState.SUCCESS, TaskState.FAILURE):
                if record.state == TaskState.FAILURE:
                    raise RuntimeError(f"Task {task_id} failed: {record.error}")
                return record.result
            time.sleep(poll_interval)
        raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")

    def get_status(self, task_id: str) -> dict:
        record = self._local_backend.get(task_id)
        if record is None:
            return {"task_id": task_id, "state": "UNKNOWN"}
        return record.to_dict()

    # ── Batch operations ─────────────────────────────────────

    def dispatch_batch(
        self,
        task_name: str,
        items: list[dict],
        queue: str = "batch",
        max_concurrent: int = 4,
    ) -> list[str]:
        """Dispatch a batch of tasks. Returns list of task_ids."""
        task_ids = []
        for item in items:
            args = item.get("args", ())
            kwargs = item.get("kwargs", {})
            tid = self.dispatch(task_name, *args, queue=queue, **kwargs)
            task_ids.append(tid)
        log.info(f"[TASK-QUEUE] Batch dispatched: {len(task_ids)} × {task_name}")
        return task_ids

    def await_batch(
        self,
        task_ids: list[str],
        timeout: float = 300.0,
        poll_interval: float = 1.0,
    ) -> dict[str, Any]:
        """Wait for all tasks in a batch to complete. Returns {task_id: result}."""
        deadline = time.time() + timeout
        results: dict[str, Any] = {}
        pending = set(task_ids)

        while pending and time.time() < deadline:
            for tid in list(pending):
                record = self._local_backend.get(tid)
                if record and record.state in (TaskState.SUCCESS, TaskState.FAILURE):
                    if record.state == TaskState.SUCCESS:
                        results[tid] = record.result
                    pending.remove(tid)
            if pending:
                time.sleep(poll_interval)

        for tid in pending:
            results[tid] = None

        return results

    # ── Telemetry ─────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        local_backend_stats = self._local_backend.count_by_state()
        uptime = time.time() - self._started
        return {
            "mode": "celery" if self.is_available else "in_process",
            "uptime_seconds": round(uptime, 1),
            "uptime_hours": round(uptime / 3600, 2),
            "broker_url": self._broker_url if self._use_celery else "none (in-process)",
            "in_flight": len(self._in_flight),
            "tasks_by_state": local_backend_stats,
            "total_tracked": sum(local_backend_stats.values()),
        }

    def print_stats(self) -> None:
        s = self.stats()
        from llm_router import c
        print(f"\n{c('bold', 'Task Queue Stats')}")
        print(f"  Mode:            {s['mode']}")
        print(f"  Uptime:          {s['uptime_hours']}h")
        print(f"  In-flight:       {s['in_flight']}")
        print(f"  Total tracked:   {s['total_tracked']}")
        for state, count in sorted(s['tasks_by_state'].items()):
            print(f"    {state:<12s} {count}")

    # ── Shutdown ──────────────────────────────────────────────

    def shutdown(self, timeout: float = 30.0) -> dict:
        """Graceful shutdown: drain in-flight tasks and clean up resources.

        Returns summary of tasks at shutdown time.
        """
        log.info(f"[TASK-QUEUE] Shutting down (timeout={timeout}s)...")
        self._shutdown_event.set()

        # Wait for in-flight tasks
        deadline = time.time() + timeout
        with self._lock:
            in_flight = dict(self._in_flight)

        for tid, event in in_flight.items():
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            event.wait(timeout=remaining)

        summary = self.stats()
        log.info(f"[TASK-QUEUE] Shutdown complete. {summary}")
        return summary


# ── Singleton ─────────────────────────────────────────────────

_queue_instance: TaskQueue | None = None
_queue_lock = threading.Lock()


def get_task_queue() -> TaskQueue:
    global _queue_instance
    with _queue_lock:
        if _queue_instance is None:
            _queue_instance = TaskQueue()
        return _queue_instance


def reset_task_queue() -> None:
    global _queue_instance
    with _queue_lock:
        if _queue_instance is not None:
            _queue_instance.shutdown(timeout=5)
        _queue_instance = None


__all__ = [
    "TaskQueue",
    "TaskRecord",
    "TaskState",
    "RetryPolicy",
    "get_task_queue",
    "reset_task_queue",
    "DEFAULT_RETRY_POLICY",
    "FAST_RETRY_POLICY",
    "HEAVY_RETRY_POLICY",
]
