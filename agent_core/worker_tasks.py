"""
worker_tasks.py — Celery Task Definitions for SEO Agent Pro
=============================================================
Wraps existing modules.py functions as Celery tasks.
These are loaded by the Celery worker when it starts.

Each task:
  • Delegates to the existing modules.py function (no business logic change)
  • Includes retry policy metadata
  • Records structured telemetry via MetricsCollector
  • Supports task_id tracking for result retrieval

Usage (start worker):
    celery -A agent_core.worker_tasks worker --loglevel=info --concurrency=4

Usage (Python API):
    from agent_core.worker_tasks import analyze_competitors_task
    result = analyze_competitors_task.delay(keyword="best laptop", model="local")
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

log = logging.getLogger("agent_core.worker_tasks")

# ── Celery app (lazy init) ────────────────────────────────────

_celery_app = None


def _get_app():
    global _celery_app
    if _celery_app is not None:
        return _celery_app
    try:
        from celery import Celery
        from config import CELERY_CONFIG

        broker = CELERY_CONFIG.get("broker_url", "redis://localhost:6379/0")
        backend = CELERY_CONFIG.get("result_backend_url", "redis://localhost:6379/0")

        _celery_app = Celery(
            "seo_agent",
            broker=broker,
            backend=backend,
        )
        _celery_app.conf.update(
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
            result_expires=3600,
            task_track_started=True,
            task_acks_late=True,
            worker_prefetch_multiplier=1,
        )
        _celery_app.conf.task_default_queue = "seo_agent"

        # Register tasks on this app instance
        _register_tasks(_celery_app)

        log.info(f"[WORKER] Celery app created (broker={broker})")
    except ImportError:
        log.error("[WORKER] Celery not installed — cannot create worker tasks")
        raise
    return _celery_app


def _register_tasks(app) -> None:
    """Register all SEO Agent Pro tasks with the Celery app."""

    @app.task(
        name="analyze_competitors",
        bind=True,
        max_retries=3,
        default_retry_delay=2,
        acks_late=True,
        track_started=True,
    )
    def analyze_competitors_task(self, keyword: str, model: str) -> dict:
        return _run_task("analyze_competitors", keyword=keyword, model=model)

    @app.task(
        name="decide_strategy",
        bind=True,
        max_retries=3,
        default_retry_delay=2,
        acks_late=True,
        track_started=True,
    )
    def decide_strategy_task(self, keyword: str, competitor_data: dict, articles_written: int, model: str) -> dict:
        return _run_task("decide_strategy", keyword=keyword, competitor_data=competitor_data, articles_written=articles_written, model=model)

    @app.task(
        name="write_article",
        bind=True,
        max_retries=3,
        default_retry_delay=5,
        acks_late=True,
        track_started=True,
    )
    def write_article_task(self, keyword: str, strategy: dict, model: str) -> str:
        return _run_task("write_article", keyword=keyword, strategy=strategy, model=model)

    @app.task(
        name="optimize_ctr",
        bind=True,
        max_retries=2,
        default_retry_delay=2,
        acks_late=True,
        track_started=True,
    )
    def optimize_ctr_task(self, keyword: str, article_snippet: str, model: str) -> dict:
        return _run_task("optimize_ctr", keyword=keyword, article_snippet=article_snippet, model=model)

    @app.task(
        name="build_cluster",
        bind=True,
        max_retries=3,
        default_retry_delay=2,
        acks_late=True,
        track_started=True,
    )
    def build_cluster_task(self, keyword: str, niche: str, model: str) -> dict:
        return _run_task("build_cluster", keyword=keyword, niche=niche, model=model)

    @app.task(
        name="build_calendar",
        bind=True,
        max_retries=2,
        default_retry_delay=2,
        acks_late=True,
        track_started=True,
    )
    def build_calendar_task(self, keyword: str, niche: str, months: int, model: str) -> list:
        return _run_task("build_calendar", keyword=keyword, niche=niche, months=months, model=model)

    @app.task(
        name="validate_article_quality",
        bind=True,
        max_retries=2,
        default_retry_delay=1,
        acks_late=True,
        track_started=True,
    )
    def validate_article_quality_task(self, article: str, keyword: str) -> dict:
        return _run_task("validate_article_quality", article=article, keyword=keyword)

    @app.task(
        name="score_authority",
        bind=True,
        max_retries=2,
        default_retry_delay=2,
        acks_late=True,
        track_started=True,
    )
    def score_authority_task(self, niche: str, articles_written: list, model: str) -> dict:
        return _run_task("score_authority", niche=niche, articles_written=articles_written, model=model)

    @app.task(
        name="full_pipeline",
        bind=True,
        max_retries=2,
        default_retry_delay=10,
        acks_late=True,
        track_started=True,
        soft_time_limit=600,
        time_limit=900,
    )
    def full_pipeline_task(self, keyword: str, niche: str, model: str, months: int = 3) -> dict:
        return _run_task("full_pipeline", keyword=keyword, niche=niche, model=model, months=months)

    @app.task(
        name="batch_articles",
        bind=True,
        max_retries=1,
        default_retry_delay=5,
        acks_late=True,
        track_started=True,
        soft_time_limit=1200,
        time_limit=1800,
    )
    def batch_articles_task(self, keywords: list, model: str) -> dict:
        return _run_task("batch_articles", keywords=keywords, model=model)

    # Store references so they can be imported
    app.tasks_registered = {
        "analyze_competitors": analyze_competitors_task,
        "decide_strategy": decide_strategy_task,
        "write_article": write_article_task,
        "optimize_ctr": optimize_ctr_task,
        "build_cluster": build_cluster_task,
        "build_calendar": build_calendar_task,
        "validate_article_quality": validate_article_quality_task,
        "score_authority": score_authority_task,
        "full_pipeline": full_pipeline_task,
        "batch_articles": batch_articles_task,
    }


def _run_task(task_name: str, **kwargs) -> Any:
    """Execute a task by delegating to the existing modules.py or pipeline_enhancer."""
    _record_telemetry(task_name, "started", kwargs)

    t0 = time.perf_counter()
    try:
        if task_name in ("full_pipeline", "batch_articles"):
            import pipeline_enhancer as _pe
            fn = getattr(_pe, {
                "full_pipeline": "run_full_enhanced",
                "batch_articles": "run_batch_articles",
            }[task_name])
        else:
            import modules as _mod
            fn = getattr(_mod, task_name)

        result = fn(**kwargs)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        _record_telemetry(task_name, "completed", kwargs, latency_ms=elapsed_ms)
        log.info(f"[WORKER] {task_name} completed in {elapsed_ms:.0f}ms")

        return result
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        _record_telemetry(task_name, "failed", kwargs, latency_ms=elapsed_ms, error=str(e))
        log.error(f"[WORKER] {task_name} failed after {elapsed_ms:.0f}ms: {e}")
        raise


def _record_telemetry(task_name: str, state: str, task_kwargs: dict, latency_ms: float | None = None, error: str | None = None) -> None:
    """Record task telemetry to MetricsCollector (best-effort)."""
    try:
        from agent_core.metrics_collector import get_collector
        collector = get_collector()

        if state == "started":
            collector.increment(f"worker_tasks_started")
            collector.increment(f"worker_task_{task_name}_started")
        elif state == "completed":
            collector.increment(f"worker_tasks_completed")
            collector.increment(f"worker_task_{task_name}_completed")
            if latency_ms is not None:
                collector.record_stage(f"worker_{task_name}", latency_ms, True)
        elif state == "failed":
            collector.increment(f"worker_tasks_failed")
            collector.increment(f"worker_task_{task_name}_failed")
            if latency_ms is not None:
                collector.record_stage(f"worker_{task_name}", latency_ms, False)
    except Exception:
        log.warning("[WORKER] Telemetry recording failed")


# ── Module-level app instance ─────────────────────────────────

app = _get_app()

# Export tasks for import
analyze_competitors_task = app.tasks_registered["analyze_competitors"]
decide_strategy_task = app.tasks_registered["decide_strategy"]
write_article_task = app.tasks_registered["write_article"]
optimize_ctr_task = app.tasks_registered["optimize_ctr"]
build_cluster_task = app.tasks_registered["build_cluster"]
build_calendar_task = app.tasks_registered["build_calendar"]
validate_article_quality_task = app.tasks_registered["validate_article_quality"]
score_authority_task = app.tasks_registered["score_authority"]
full_pipeline_task = app.tasks_registered["full_pipeline"]
batch_articles_task = app.tasks_registered["batch_articles"]

__all__ = [
    "app",
    "analyze_competitors_task",
    "decide_strategy_task",
    "write_article_task",
    "optimize_ctr_task",
    "build_cluster_task",
    "build_calendar_task",
    "validate_article_quality_task",
    "score_authority_task",
    "full_pipeline_task",
    "batch_articles_task",
]
