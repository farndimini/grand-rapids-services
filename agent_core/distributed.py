"""
distributed.py — Distributed Execution Integration Layer
=========================================================
Routes SEO Agent Pro tasks through a durable Celery queue
when --distributed is passed, with automatic fallback to
in-process execution when Redis/Celery is unavailable.

Uses pipeline_enhancer.configure() for dependency injection
(instead of the old monkey-patch approach that caused import-order
instability and unsafe multiprocessing behavior).

Usage:
    from agent_core.distributed import DistributedPipeline
    pipeline = DistributedPipeline()
    result = pipeline.run_full(keyword="best laptop", model="local")

Integration in main.py:
    python main.py --keyword "best laptop" --model local --distributed
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from config import CELERY_CONFIG, SETTINGS

log = logging.getLogger("agent_core.distributed")

# ── Lazy imports ──────────────────────────────────────────────

_HAS_DISTRIBUTED = False
_task_queue = None


def _get_task_queue():
    global _task_queue, _HAS_DISTRIBUTED
    if _task_queue is not None:
        return _task_queue
    try:
        from agent_core.task_queue import TaskQueue, get_task_queue
        _task_queue = get_task_queue()
        _HAS_DISTRIBUTED = True
        return _task_queue
    except Exception as e:
        log.warning(f"[DISTRIBUTED] Task queue unavailable: {e}")
        _HAS_DISTRIBUTED = False
        return None


# ── DistributedPipeline ───────────────────────────────────────

class DistributedPipeline:
    """Drop-in replacement for pipeline_enhancer via task queue.

    All methods match the pipeline_enhancer API exactly for
    backwards compatibility. When the task queue is unavailable,
    falls back to direct pipeline_enhancer calls.
    """

    def __init__(self, queue_name: str = "seo_agent", auto_fallback: bool = True):
        self._queue = _get_task_queue()
        self._queue_name = queue_name
        self._auto_fallback = auto_fallback
        self._fallback_pipeline = None

        if self._queue is None and auto_fallback:
            self._init_fallback()

    def _init_fallback(self) -> None:
        """Lazy-init the fallback pipeline_enhancer."""
        if self._fallback_pipeline is not None:
            return
        try:
            import pipeline_enhancer
            self._fallback_pipeline = pipeline_enhancer
            log.info("[DISTRIBUTED] Using in-process fallback (pipeline_enhancer)")
        except ImportError:
            import modules
            self._fallback_pipeline = modules
            log.info("[DISTRIBUTED] Using in-process fallback (modules)")

    @property
    def available(self) -> bool:
        return self._queue is not None and _HAS_DISTRIBUTED

    def _dispatch(self, task_name: str, force_local: bool = False, **kwargs) -> Any:
        """Dispatch a task. If force_local or queue unavailable, run in-process."""
        if not force_local and self.available:
            try:
                tid = self._queue.dispatch(task_name, queue=self._queue_name, **kwargs)
                log.info(f"[DISTRIBUTED] Dispatched {task_name} [{tid[:8]}]")
                result = self._queue.await_result(tid, timeout=CELERY_CONFIG.get("task_timeout", 300))
                return result
            except Exception as e:
                log.warning(f"[DISTRIBUTED] Remote dispatch failed: {e} — falling back to in-process")
                if not self._auto_fallback:
                    raise

        # In-process fallback
        return self._run_local(task_name, **kwargs)

    def _run_local(self, task_name: str, **kwargs) -> Any:
        """Run a task in-process via pipeline_enhancer or modules."""
        if self._fallback_pipeline is None:
            self._init_fallback()
        if self._fallback_pipeline is None:
            raise RuntimeError("No fallback pipeline available")

        fn = getattr(self._fallback_pipeline, task_name, None)
        if fn is None:
            raise ValueError(f"Unknown task: {task_name}")

        log.info(f"[DISTRIBUTED] Running {task_name} in-process")
        t0 = time.perf_counter()
        try:
            result = fn(**kwargs)
            elapsed = (time.perf_counter() - t0) * 1000
            log.info(f"[DISTRIBUTED] {task_name} completed in {elapsed:.0f}ms")
            return result
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            log.error(f"[DISTRIBUTED] {task_name} failed after {elapsed:.0f}ms: {e}")
            raise

    # ── LLM call dispatch (used by configure() relay hooks) ──

    def _dispatch_llm(
        self, system: str, user: str, model: str, stream: bool = True
    ) -> str:
        # Force local execution: no Celery task handler registered for "call".
        # This avoids dispatching an unregistered task to the remote queue.
        return self._dispatch("call", force_local=True,
                              system=system, user=user, model_name=model, stream=stream)

    def _dispatch_llm_json(
        self, system: str, user: str, model: str
    ) -> dict | list:
        # Force local execution: no Celery task handler registered for "call_json".
        return self._dispatch("call_json", force_local=True,
                              system=system, user=user, model_name=model)

    # ── Pipeline methods (mirrors pipeline_enhancer API) ─────

    def analyze_competitors(self, keyword: str, model: str) -> dict:
        return self._dispatch("analyze_competitors", keyword=keyword, model=model)

    def decide_strategy(self, keyword: str, competitor_data: dict, articles_written: int, model: str) -> dict:
        return self._dispatch("decide_strategy", keyword=keyword, competitor_data=competitor_data, articles_written=articles_written, model=model)

    def write_article(self, keyword: str, strategy: dict, model: str) -> str:
        return self._dispatch("write_article", keyword=keyword, strategy=strategy, model=model)

    def optimize_ctr(self, keyword: str, article_snippet: str, model: str) -> dict:
        return self._dispatch("optimize_ctr", keyword=keyword, article_snippet=article_snippet, model=model)

    def build_cluster(self, keyword: str, niche: str, model: str) -> dict:
        return self._dispatch("build_cluster", keyword=keyword, niche=niche, model=model)

    def build_calendar(self, keyword: str, niche: str, months: int, model: str) -> list:
        return self._dispatch("build_calendar", keyword=keyword, niche=niche, months=months, model=model)

    def validate_article_quality(self, article: str, keyword: str) -> dict:
        return self._dispatch("validate_article_quality", article=article, keyword=keyword)

    def score_authority(self, niche: str, articles_written: list, model: str) -> dict:
        return self._dispatch("score_authority", niche=niche, articles_written=articles_written, model=model)

    def run_full_enhanced(self, keyword: str, niche: str, model: str, months: int = 3, **kwargs) -> dict:
        return self._dispatch("full_pipeline", keyword=keyword, niche=niche, model=model, months=months)

    def run_batch_articles(self, keywords: list[str], model: str) -> dict[str, str]:
        return self._dispatch("batch_articles", keywords=keywords, model=model)

    # ── Queue management ─────────────────────────────────────

    def queue_status(self) -> dict:
        if self.available:
            return self._queue.stats()
        return {"mode": "in_process", "available": False}

    def shutdown(self) -> None:
        if self._queue is not None:
            self._queue.shutdown(timeout=15)


# ── Patch entry point (used by main.py --distributed) ─────────

def patch_pipeline(distributed_pipeline: DistributedPipeline) -> None:
    """Configure pipeline_enhancer for distributed execution.

    Uses pipeline_enhancer.configure() for clean dependency injection
    rather than module-level function replacement. Also stores and
    replaces pipeline-level functions for full task offloading.
    """
    import pipeline_enhancer as pe

    # Inject relay_call/relay_call_json via configure() so LLM calls
    # route through the distributed task queue (or fall back to in-process).
    pe.configure(
        relay_call=distributed_pipeline._dispatch_llm,
        relay_call_json=distributed_pipeline._dispatch_llm_json,
    )

    # Store originals for function-level dispatch if not already stored
    if not hasattr(pe, '_orig_analyze_competitors'):
        pe._orig_analyze_competitors = pe.analyze_competitors
        pe._orig_decide_strategy = pe.decide_strategy
        pe._orig_write_article = pe.write_article
        pe._orig_optimize_ctr = pe.optimize_ctr
        pe._orig_build_cluster = pe.build_cluster
        pe._orig_build_calendar = pe.build_calendar
        pe._orig_validate_article_quality = pe.validate_article_quality
        pe._orig_score_authority = pe.score_authority
        pe._orig_run_full_enhanced = pe.run_full_enhanced
        pe._orig_run_batch_articles = pe.run_batch_articles

    # Replace pipeline-level functions for full task offloading
    pe.analyze_competitors = distributed_pipeline.analyze_competitors
    pe.decide_strategy = distributed_pipeline.decide_strategy
    pe.write_article = distributed_pipeline.write_article
    pe.optimize_ctr = distributed_pipeline.optimize_ctr
    pe.build_cluster = distributed_pipeline.build_cluster
    pe.build_calendar = distributed_pipeline.build_calendar
    pe.validate_article_quality = distributed_pipeline.validate_article_quality
    pe.score_authority = distributed_pipeline.score_authority
    pe.run_full_enhanced = distributed_pipeline.run_full_enhanced
    pe.run_batch_articles = distributed_pipeline.run_batch_articles

    log.info("[DISTRIBUTED] pipeline_enhancer configured for distributed execution")


def unpatch_pipeline() -> None:
    """Restore original pipeline_enhancer configuration."""
    import pipeline_enhancer as pe

    # Reset dependency injection config
    pe.configure(relay_call=None, relay_call_json=None)

    # Restore original pipeline-level functions
    attrs = [
        ("analyze_competitors", "_orig_analyze_competitors"),
        ("decide_strategy", "_orig_decide_strategy"),
        ("write_article", "_orig_write_article"),
        ("optimize_ctr", "_orig_optimize_ctr"),
        ("build_cluster", "_orig_build_cluster"),
        ("build_calendar", "_orig_build_calendar"),
        ("validate_article_quality", "_orig_validate_article_quality"),
        ("score_authority", "_orig_score_authority"),
        ("run_full_enhanced", "_orig_run_full_enhanced"),
        ("run_batch_articles", "_orig_run_batch_articles"),
    ]
    for attr, orig_attr in attrs:
        if hasattr(pe, orig_attr):
            setattr(pe, attr, getattr(pe, orig_attr))

    log.info("[DISTRIBUTED] pipeline_enhancer restored to original")


__all__ = [
    "DistributedPipeline",
    "patch_pipeline",
    "unpatch_pipeline",
    "_HAS_DISTRIBUTED",
]
