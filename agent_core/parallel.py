"""
parallel.py — Concurrent Execution Engine for SEO Pipeline
============================================================
Runs independent pipeline stages concurrently to cut wall-clock time.

Safe to use with any pipeline stage that doesn't depend on another's output.

Usage:
    from agent_core.parallel import ParallelEngine, TaskGroup
    engine = ParallelEngine(max_workers=4)

    with TaskGroup(engine) as g:
        g.submit("competitor", analyze_competitors, keyword, model)
        g.submit("cluster",    build_cluster,    keyword, niche, model)
        g.submit("calendar",   build_calendar,   keyword, niche, months, model)

    results = g.results()  # {"competitor": {...}, "cluster": {...}, "calendar": [...]}
"""

from __future__ import annotations

import concurrent.futures
import logging
import time
from typing import Any, Callable

log = logging.getLogger("agent_core.parallel")


class ParallelEngine:
    """Manages a thread pool for concurrent SEO pipeline execution."""

    def __init__(self, max_workers: int = 4):
        self._max_workers = max_workers
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None

    def start(self) -> ParallelEngine:
        if self._executor is None or self._executor._shutdown:
            self._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="seo_agent_",
            )
        return self

    def shutdown(self, wait: bool = True) -> None:
        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None

    def __enter__(self) -> ParallelEngine:
        return self.start()

    def __exit__(self, *args) -> None:
        self.shutdown(wait=True)

    def submit(self, fn: Callable, *args, **kwargs) -> concurrent.futures.Future:
        if self._executor is None:
            raise RuntimeError("Engine not started. Use 'with' context or call .start()")
        return self._executor.submit(fn, *args, **kwargs)


class TaskGroup:
    """Named task collector with error isolation."""

    def __init__(self, engine: ParallelEngine):
        self._engine = engine
        self._futures: dict[str, concurrent.futures.Future] = {}
        self._results: dict[str, Any] = {}
        self._errors: dict[str, Exception] = {}
        self._durations: dict[str, float] = {}

    def submit(self, name: str, fn: Callable, *args, **kwargs) -> None:
        """Submit a named task."""
        future = self._engine.submit(self._wrap, name, fn, *args, **kwargs)
        self._futures[name] = future

    def _wrap(self, name: str, fn: Callable, *args, **kwargs) -> tuple[str, Any, float]:
        t0 = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
            return name, result, time.perf_counter() - t0
        except Exception as e:
            log.warning(f"[PARALLEL] Task '{name}' failed: {e}")
            raise

    def results(self, timeout: float | None = None) -> dict[str, Any]:
        """Wait for all tasks and collect results. Tasks that fail are logged but don't crash others."""
        for name, future in self._futures.items():
            try:
                _name, result, duration = future.result(timeout=timeout)
                self._results[_name] = result
                self._durations[_name] = duration
                log.info(f"[PARALLEL] {name} completed in {duration:.2f}s")
            except Exception as e:
                self._errors[name] = e
                self._durations[name] = None
                log.warning(f"[PARALLEL] {name} FAILED: {e}")
        return self._results

    def errors(self) -> dict[str, Exception]:
        return dict(self._errors)

    def durations(self) -> dict[str, float | None]:
        return dict(self._durations)

    def summary(self) -> dict:
        total = len(self._futures)
        succeeded = len(self._results)
        failed = len(self._errors)
        return {
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
            "durations": self._durations,
        }

    def __enter__(self) -> TaskGroup:
        return self

    def __exit__(self, *args) -> None:
        pass


# ──────────────────────────────────────────────────────────────
#  Higher-level helpers for common SEO Agent Pro patterns
# ──────────────────────────────────────────────────────────────

def run_parallel_analysis(
    keyword: str,
    niche: str,
    model: str,
    months: int = 3,
) -> dict[str, Any]:
    """
    Run competitor analysis, cluster build, and calendar build in parallel.
    Returns dict with 'competitor', 'cluster', 'calendar' keys.
    """
    import modules as agent

    engine = ParallelEngine(max_workers=3)
    with engine:
        with TaskGroup(engine) as g:
            g.submit("competitor", agent.analyze_competitors, keyword, model)
            g.submit("cluster",    agent.build_cluster,    keyword, niche, model)
            g.submit("calendar",   agent.build_calendar,   keyword, niche, months, model)
        results = g.results()

    summary = g.summary()
    log.info(f"[PARALLEL] Analysis complete: {summary['succeeded']}/{summary['total']} succeeded")
    return results


def run_parallel_batch_articles(
    keywords: list[str],
    model: str,
    max_workers: int = 3,
) -> dict[str, str]:
    """
    Write multiple articles concurrently.
    Returns {keyword: article_html} mapping.
    """
    import modules as agent

    def _write_one(kw: str) -> tuple[str, str]:
        comp = agent.analyze_competitors(kw, model)
        strategy = agent.decide_strategy(kw, comp, 0, model)
        article = agent.write_article(kw, strategy, model)
        return kw, article

    engine = ParallelEngine(max_workers=max_workers)
    articles: dict[str, str] = {}
    with engine:
        futures = {engine.submit(_write_one, kw): kw for kw in keywords}
        for future in concurrent.futures.as_completed(futures):
            kw = futures[future]
            try:
                _kw, article = future.result(timeout=300)
                articles[_kw] = article
                log.info(f"[PARALLEL] Article done: {kw[:50]}")
            except Exception as e:
                log.warning(f"[PARALLEL] Article failed: {kw[:50]} — {e}")

    return articles
