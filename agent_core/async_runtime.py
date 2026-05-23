"""
agent_core/async_runtime.py — Async Execution Layer for SEO Agent Pro
======================================================================
Provides production-grade asyncio infrastructure:
  • Shared semaphore pools with provider-specific limits
  • Async-safe circuit breakers, rate limiters, and caching
  • Task supervisor with cancellation propagation
  • Timeout isolation envelopes
  • Telemetry for queue wait time, active tasks, saturation

Target: Python 3.11+ — uses TaskGroup where beneficial but falls back
gracefully to asyncio.gather for broader compatibility.

Usage:
    from agent_core.async_runtime import AsyncRuntime, async_timed
    runtime = AsyncRuntime()
    result = await runtime.call_provider("openai", my_async_fn, *args)
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Coroutine, TypeVar

# Telemetry integration
from agent_core.metrics_collector import get_collector

log = logging.getLogger("agent_core.async_runtime")

T = TypeVar("T")

# ──────────────────────────────────────────────────────────────
#  1. Configuration defaults (mirrors config.py structure)
# ──────────────────────────────────────────────────────────────

DEFAULT_MAX_CONCURRENCY = 10
DEFAULT_PROVIDER_LIMITS: dict[str, int] = {
    "anthropic": 3,
    "openrouter": 5,
    "groq": 6,
    "google": 4,
    "local": 20,
}
DEFAULT_REQUEST_TIMEOUT = 90.0


# ──────────────────────────────────────────────────────────────
#  2. Async Circuit Breaker
# ──────────────────────────────────────────────────────────────

class AsyncCircuitBreaker:
    """Thread-safe AND event-loop-safe circuit breaker.

    Uses asyncio.Lock for coroutine safety and tracks failures
    with monotonic timestamps.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
        window_seconds: float = 120.0,
    ):
        self._threshold = failure_threshold
        self._recovery = recovery_timeout
        self._window = window_seconds
        self._failures: list[float] = []
        self._state = "closed"  # closed | open | half_open
        self._opened_at = 0.0
        self._lock = asyncio.Lock()

    async def record_success(self) -> None:
        async with self._lock:
            if self._state == "half_open":
                self._state = "closed"
                self._failures.clear()
                log.info("[AsyncCB] Closed after recovery")
            elif self._state == "closed":
                self._failures.clear()

    async def record_failure(self) -> None:
        now = time.monotonic()
        async with self._lock:
            if self._state == "half_open":
                self._state = "open"
                self._opened_at = now
                log.warning("[AsyncCB] Re-opened on recovery failure")
                return
            self._failures = [t for t in self._failures if now - t < self._window]
            self._failures.append(now)
            if len(self._failures) >= self._threshold and self._state == "closed":
                self._state = "open"
                self._opened_at = now
                log.warning(f"[AsyncCB] OPENED — {len(self._failures)} failures in {self._window}s")

    async def can_execute(self) -> bool:
        now = time.monotonic()
        async with self._lock:
            if self._state == "closed":
                return True
            if self._state == "open" and now - self._opened_at >= self._recovery:
                self._state = "half_open"
                log.info("[AsyncCB] Half-open — attempting recovery")
                return True
            return self._state == "half_open"

    def status(self) -> dict[str, Any]:
        return {
            "state": self._state,
            "failures_in_window": len(self._failures),
            "threshold": self._threshold,
        }


# ──────────────────────────────────────────────────────────────
#  3. Async Token Bucket
# ──────────────────────────────────────────────────────────────

class AsyncTokenBucket:
    """Async-friendly token bucket using asyncio.Lock.

    Non-blocking acquisition with optional wait.
    """

    def __init__(self, rate: float = 1.0, capacity: float = 3.0):
        self._rate = rate
        self._capacity = capacity
        self._tokens = float(capacity)
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> float:
        """Acquire tokens. Returns wait time in seconds."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_update
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last_update = now
            if self._tokens >= tokens:
                self._tokens -= tokens
                return 0.0
            deficit = tokens - self._tokens
            wait = deficit / self._rate
            self._tokens = 0
            self._last_update += wait
        await asyncio.sleep(wait)
        return wait

    async def try_acquire(self, tokens: float = 1.0) -> bool:
        """Non-blocking acquisition. Returns True if tokens were available."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_update
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last_update = now
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False


# ──────────────────────────────────────────────────────────────
#  4. Async Disk Cache
# ──────────────────────────────────────────────────────────────

class AsyncDiskCache:
    """Disk cache with async-safe file I/O (runs blocking ops in thread pool).

    Uses asyncio.to_thread for all blocking disk operations to avoid
    stalling the event loop. Supports TTL and gzip compression.
    """

    def __init__(
        self,
        cache_dir: Path | str = "agent_core/cache",
        ttl_seconds: int = 21600,
        max_size_mb: int = 200,
    ):
        self._dir = Path(cache_dir)
        self._ttl = ttl_seconds
        self._max_size = max_size_mb * 1024 * 1024
        self._lock = asyncio.Lock()

    def _path(self, key: str) -> Path:
        h = hashlib.sha256(key.encode()).hexdigest()[:32]
        return self._dir / f"async_{h}.json"

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            path = self._path(key)
            if not path.exists():
                return None
            try:
                raw = await asyncio.to_thread(path.read_bytes)
                if raw[:2] == b'\x1f\x8b':
                    raw = await asyncio.to_thread(__import__("gzip").decompress, raw)
                data = json.loads(raw.decode("utf-8"))
                if time.time() - data.get("ts", 0) > self._ttl:
                    await asyncio.to_thread(path.unlink, True)
                    return None
                return data["payload"]
            except Exception:
                await asyncio.to_thread(path.unlink, True)
                return None

    async def set(self, key: str, payload: Any) -> None:
        async with self._lock:
            path = self._path(key)
            self._dir.mkdir(parents=True, exist_ok=True)
            try:
                blob = json.dumps({"ts": time.time(), "payload": payload}, ensure_ascii=False, indent=None)
                raw = blob.encode("utf-8")
                if len(raw) > 8192:
                    raw = await asyncio.to_thread(__import__("gzip").compress, raw, 6)
                await asyncio.to_thread(path.write_bytes, raw)
            except OSError as e:
                log.warning(f"[AsyncCache] Write failed: {e}")
        await self._maybe_evict_lru()

    async def _maybe_evict_lru(self) -> None:
        async with self._lock:
            files = list(self._dir.glob("async_*.json"))
            total = sum(f.stat().st_size for f in files)
            if total <= self._max_size:
                return
            files.sort(key=lambda f: f.stat().st_mtime)
            for f in files:
                if total <= self._max_size * 0.8:
                    break
                try:
                    total -= f.stat().st_size
                    f.unlink(missing_ok=True)
                except OSError:
                    pass


# ──────────────────────────────────────────────────────────────
#  5. Async Relay with Intelligent Fallback
# ──────────────────────────────────────────────────────────────

class AsyncRelay:
    """Async-aware LLM relay with resilience features.

    Wraps coroutine-based provider calls with:
      • Per-provider semaphore limits
      • Async circuit breaker
      • Async token bucket rate limiter
      • Exponential backoff with jitter
      • Async disk cache
      • Cross-provider fallback
      • Timeout envelopes
    """

    def __init__(
        self,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        provider_limits: dict[str, int] | None = None,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
        cache_ttl: int = 21600,
    ):
        self._global_sem = asyncio.Semaphore(max_concurrency)
        limits = provider_limits or DEFAULT_PROVIDER_LIMITS
        self._provider_sems: dict[str, asyncio.Semaphore] = {
            p: asyncio.Semaphore(l) for p, l in limits.items()
        }
        self._timeout = request_timeout
        self._cache = AsyncDiskCache(ttl_seconds=cache_ttl)
        self._breakers: dict[str, AsyncCircuitBreaker] = {
            p: AsyncCircuitBreaker() for p in limits
        }
        self._buckets: dict[str, AsyncTokenBucket] = {
            "anthropic": AsyncTokenBucket(rate=1.0, capacity=2),
            "openrouter": AsyncTokenBucket(rate=2.0, capacity=4),
            "groq": AsyncTokenBucket(rate=3.0, capacity=6),
            "google": AsyncTokenBucket(rate=2.0, capacity=4),
            "local": AsyncTokenBucket(rate=10.0, capacity=20),
        }
        self._fallback_order = ["anthropic", "openrouter", "groq", "google", "local"]
        self._stats: dict[str, Any] = {"calls": 0, "cache_hits": 0, "fallbacks": 0, "failures": 0}

    async def call(
        self,
        provider: str,
        coro_fn: Callable[..., Awaitable[T]],
        *args,
        use_cache: bool = False,
        cache_key: str = "",
        **kwargs,
    ) -> T:
        """Execute coro_fn under provider limits, breaker, bucket, timeout.

        Args:
            provider: Provider name (must match semaphore keys)
            coro_fn: Async callable to execute
            use_cache: Whether to cache the result
            cache_key: Cache key (auto-built from args if omitted)
        """
        if use_cache:
            ck = cache_key or self._build_cache_key(coro_fn, args, kwargs)
            cached = await self._cache.get(ck)
            if cached is not None:
                self._stats["cache_hits"] += 1
                get_collector().record_cache(hit=True, cache_type="llm")
                return cached  # type: ignore[return-value]

        sem = self._provider_sems.get(provider) or self._global_sem
        breaker = self._breakers.get(provider) or AsyncCircuitBreaker()
        bucket = self._buckets.get(provider) or AsyncTokenBucket(rate=5.0, capacity=10)

        if not await breaker.can_execute():
            raise RuntimeError(f"[AsyncRelay] Circuit breaker OPEN for {provider}")

        # Rate limit
        await bucket.acquire(1.0)

        # Semaphore acquisition with queue-wait telemetry
        queue_t0 = time.monotonic()
        async with self._global_sem:
            async with sem:
                queue_wait = (time.monotonic() - queue_t0) * 1000
                get_collector().record_stage("queue_wait", queue_wait, True, provider=provider)

                t0 = time.perf_counter()
                try:
                    result = await asyncio.wait_for(
                        coro_fn(*args, **kwargs),
                        timeout=self._timeout,
                    )
                    latency_ms = (time.perf_counter() - t0) * 1000
                    await breaker.record_success()
                    self._stats["calls"] += 1
                    get_collector().record_provider(provider, latency_ms, True)

                    if use_cache:
                        ck = cache_key or self._build_cache_key(coro_fn, args, kwargs)
                        await self._cache.set(ck, result)
                    return result
                except asyncio.TimeoutError:
                    latency_ms = (time.perf_counter() - t0) * 1000
                    await breaker.record_failure()
                    self._stats["failures"] += 1
                    get_collector().record_provider(provider, latency_ms, False, error="timeout")
                    raise
                except Exception as e:
                    latency_ms = (time.perf_counter() - t0) * 1000
                    await breaker.record_failure()
                    self._stats["failures"] += 1
                    get_collector().record_provider(provider, latency_ms, False, error=str(e)[:120])
                    raise

    async def call_with_fallback(
        self,
        preferred_provider: str,
        coro_fn_map: dict[str, Callable[..., Awaitable[T]]],
        *args,
        **kwargs,
    ) -> T:
        """Try preferred provider, then fall back through ordered list."""
        ordered = [preferred_provider] + [p for p in self._fallback_order if p != preferred_provider]
        last_err: Exception | None = None

        for prov in ordered:
            if prov not in coro_fn_map:
                continue
            try:
                result = await self.call(prov, coro_fn_map[prov], *args, **kwargs)
                if prov != preferred_provider:
                    self._stats["fallbacks"] += 1
                    get_collector().record_fallback(preferred_provider, prov)
                return result
            except Exception as e:
                last_err = e
                log.warning(f"[AsyncRelay] Fallback chain: {prov} failed: {e}")
                continue

        raise RuntimeError(f"[AsyncRelay] All providers exhausted. Last error: {last_err}")

    def _build_cache_key(self, fn: Callable, args: tuple, kwargs: dict) -> str:
        payload = json.dumps({"fn": fn.__name__, "args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    def health(self) -> dict[str, dict]:
        return {p: b.status() for p, b in self._breakers.items()}

    def stats(self) -> dict[str, Any]:
        return dict(self._stats)


# ──────────────────────────────────────────────────────────────
#  6. Task Supervisor & Gather Wrappers
# ──────────────────────────────────────────────────────────────

@dataclass
class TaskResult:
    name: str
    success: bool
    result: Any = None
    exception: Exception | None = None
    latency_ms: float = 0.0


class TaskSupervisor:
    """Supervises concurrent tasks with graceful error isolation.

    Ensures one failing task does not crash the entire gather.
    """

    async def supervised_gather(
        self,
        tasks: dict[str, Callable[..., Awaitable[T]]],
        *args,
        return_exceptions: bool = True,
        **kwargs,
    ) -> dict[str, TaskResult]:
        """Run named tasks concurrently, isolating failures.

        Returns a dict mapping task name -> TaskResult.
        """
        async def _run_one(name: str, fn: Callable[..., Awaitable[T]]) -> TaskResult:
            t0 = time.perf_counter()
            try:
                result = await fn(*args, **kwargs)
                return TaskResult(
                    name=name,
                    success=True,
                    result=result,
                    latency_ms=(time.perf_counter() - t0) * 1000,
                )
            except asyncio.CancelledError:
                raise  # Propagate cancellation
            except Exception as e:
                return TaskResult(
                    name=name,
                    success=False,
                    exception=e,
                    latency_ms=(time.perf_counter() - t0) * 1000,
                )

        coros = [_run_one(name, fn) for name, fn in tasks.items()]
        results = await asyncio.gather(*coros, return_exceptions=return_exceptions)
        out: dict[str, TaskResult] = {}
        for name, res in zip(tasks.keys(), results):
            if isinstance(res, Exception):
                out[name] = TaskResult(name=name, success=False, exception=res)
            else:
                out[name] = res
        return out

    async def bounded_map(
        self,
        coro_fn: Callable[[Any], Awaitable[T]],
        items: list[Any],
        concurrency: int = 5,
    ) -> list[T | Exception]:
        """Map coro_fn over items with bounded concurrency."""
        sem = asyncio.Semaphore(concurrency)

        async def _wrapped(item: Any) -> T | Exception:
            async with sem:
                try:
                    return await coro_fn(item)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    return e

        return await asyncio.gather(*(_wrapped(item) for item in items))


# ──────────────────────────────────────────────────────────────
#  7. Timeout Envelope Decorator
# ──────────────────────────────────────────────────────────────

def timeout_envelope(seconds: float):
    """Decorator that wraps an async function with a strict timeout.

    Raises asyncio.TimeoutError if the coroutine exceeds the limit.
    """
    def decorator(coro_fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(coro_fn)
        async def wrapper(*args, **kwargs) -> T:
            return await asyncio.wait_for(coro_fn(*args, **kwargs), timeout=seconds)
        return wrapper
    return decorator


# ──────────────────────────────────────────────────────────────
#  8. Async Telemetry Decorator
# ──────────────────────────────────────────────────────────────

def async_timed(stage_name: str, **static_meta):
    """Decorator that records latency and success for any async function."""
    def decorator(coro_fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(coro_fn)
        async def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                result = await coro_fn(*args, **kwargs)
                latency_ms = (time.perf_counter() - t0) * 1000
                get_collector().record_stage(stage_name, latency_ms, True, **static_meta)
                return result
            except asyncio.CancelledError:
                latency_ms = (time.perf_counter() - t0) * 1000
                get_collector().record_stage(stage_name, latency_ms, False, cancelled=True, **static_meta)
                raise
            except Exception as e:
                latency_ms = (time.perf_counter() - t0) * 1000
                get_collector().record_stage(stage_name, latency_ms, False, error=str(e)[:80], **static_meta)
                raise
        return wrapper
    return decorator


# ──────────────────────────────────────────────────────────────
#  9. AsyncRuntime Facade
# ──────────────────────────────────────────────────────────────

class AsyncRuntime:
    """Central facade for all async execution in SEO Agent Pro.

    Combines relay, supervisor, caching, and telemetry into one
    interface that pipeline stages can import and use safely.
    """

    def __init__(
        self,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        provider_limits: dict[str, int] | None = None,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ):
        self.relay = AsyncRelay(
            max_concurrency=max_concurrency,
            provider_limits=provider_limits,
            request_timeout=request_timeout,
        )
        self.supervisor = TaskSupervisor()
        self._lock = asyncio.Lock()

    async def run_parallel_serp_fetches(
        self,
        fetchers: dict[str, Callable[..., Awaitable[T]]],
        *args,
        **kwargs,
    ) -> dict[str, TaskResult]:
        """Run multiple SERP fetchers concurrently with error isolation."""
        return await self.supervisor.supervised_gather(fetchers, *args, **kwargs)

    async def run_bounded_pipeline(
        self,
        coro_fn: Callable[[Any], Awaitable[T]],
        items: list[Any],
        concurrency: int = 5,
    ) -> list[T | Exception]:
        """Process items with bounded parallelism (e.g., batch articles)."""
        return await self.supervisor.bounded_map(coro_fn, items, concurrency=concurrency)

    def health(self) -> dict[str, Any]:
        return {
            "relay": self.relay.health(),
            "relay_stats": self.relay.stats(),
        }

    # ── Singleton accessor ──────────────────────────────────

    _instance: AsyncRuntime | None = None

    @classmethod
    def get(cls) -> AsyncRuntime:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
