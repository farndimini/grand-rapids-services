"""
telemetry.py — Automatic Pipeline Stage Instrumentation
=========================================================
Provides decorators and context managers that inject metrics
into ANY callable without modifying its body.

Usage:
    from agent_core.telemetry import track_stage, TelemetryContext

    @track_stage("competitor_analysis")
    def analyze_competitors(keyword, model):
        ...

    with TelemetryContext("full_pipeline"):
        run_full(keyword, niche, model, months)
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable, TypeVar

from agent_core.metrics_collector import get_collector

log = logging.getLogger("agent_core.telemetry")

F = TypeVar("F", bound=Callable[..., Any])


class TelemetryContext:
    """Context manager that times a block and records success/failure."""

    def __init__(self, stage_name: str, **meta):
        self.stage = stage_name
        self.meta = meta
        self._t0 = 0.0

    def __enter__(self) -> TelemetryContext:
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        latency_ms = (time.perf_counter() - self._t0) * 1000
        success = exc_type is None
        get_collector().record_stage(self.stage, latency_ms, success, **self.meta)
        status = "PASS" if success else "FAIL"
        log.debug(f"[TELEMETRY] {self.stage}: {latency_ms:.0f}ms — {status}")


def track_stage(stage_name: str, **default_meta) -> Callable[[F], F]:
    """Decorator that records latency and success for the wrapped function."""

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            with TelemetryContext(stage_name, **default_meta):
                return fn(*args, **kwargs)
        return wrapper  # type: ignore[return-value]
    return decorator


def track_llm_call(fn_name: str = "llm_call") -> Callable[[F], F]:
    """Special decorator for LLM calls that also records provider metrics."""

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(system: str, user: str, model: str, *args, **kwargs):
            t0 = time.perf_counter()
            try:
                result = fn(system, user, model, *args, **kwargs)
                latency_ms = (time.perf_counter() - t0) * 1000
                # Extract provider from model via config
                _provider = _guess_provider(model)
                get_collector().record_provider(_provider, latency_ms, True)
                get_collector().record_stage(fn_name, latency_ms, True, provider=_provider, model=model)
                return result
            except Exception as e:
                latency_ms = (time.perf_counter() - t0) * 1000
                _provider = _guess_provider(model)
                get_collector().record_provider(_provider, latency_ms, False, error=str(e)[:80])
                get_collector().record_stage(fn_name, latency_ms, False, provider=_provider, error=str(e)[:80])
                raise
        return wrapper  # type: ignore[return-value]
    return decorator


def _guess_provider(model: str) -> str:
    """Best-effort provider extraction from model name."""
    from config import MODELS
    if model in MODELS:
        return MODELS[model][0]
    # Heuristic fallback
    model_l = model.lower()
    if "claude" in model_l:
        return "anthropic"
    if "gpt" in model_l or "openai" in model_l:
        return "openrouter"
    if "groq" in model_l or "llama-3" in model_l:
        return "groq"
    if "gemini" in model_l:
        return "google"
    return "local"
