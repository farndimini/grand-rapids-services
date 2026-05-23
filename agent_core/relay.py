"""
relay.py — Resilient LLM Router Wrapper (v2.1)
================================================
Enhancements:
  • IntelligentFallback integration (multi-factor provider selection)
  • Exponential backoff WITH jitter
  • Token-bucket rate limiter per provider
  • Full metrics integration (latency, success, fallback, cost)
  • Response caching with compression & LRU eviction
  • Circuit breaker per provider
  • Request coalescing

Usage:
    from agent_core.relay import RelayRouter
    router = RelayRouter()
    text = router.call(system, user, model="claude-sonnet-4")
    data = router.call_json(system, user, model="gpt-4o")
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import threading
import time
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from llm_router import call as _orig_call, call_json as _orig_call_json, c, validate_config
from config import API_KEYS, MODELS, SETTINGS

# NEW imports
from agent_core.metrics_collector import get_collector
from agent_core.intelligent_fallback import IntelligentFallback

log = logging.getLogger("agent_core.relay")

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)
DEFAULT_MAX_RETRIES = 4
DEFAULT_BASE_DELAY = 1.5
DEFAULT_TIMEOUT = 90
FALLBACK_CHAIN = ["anthropic", "openrouter", "groq", "google", "local"]
MAX_CACHE_SIZE_MB = 200


@dataclass(frozen=True)
class _CacheKey:
    system_hash: str
    user_hash: str
    model: str
    mode: str

    @classmethod
    def build(cls, system: str, user: str, model: str, mode: str) -> _CacheKey:
        return cls(
            system_hash=hashlib.sha256(system.encode("utf-8")).hexdigest()[:24],
            user_hash=hashlib.sha256(user.encode("utf-8")).hexdigest()[:24],
            model=model,
            mode=mode,
        )


class DiskCache:
    """JSON disk cache with TTL, gzip compression, and LRU eviction."""

    def __init__(self, ttl_seconds: int = 21600):
        self._dir = CACHE_DIR
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._max_size_bytes = MAX_CACHE_SIZE_MB * 1024 * 1024

    def _path(self, key: _CacheKey) -> Path:
        name = f"{key.model}_{key.mode}_{key.system_hash}_{key.user_hash}.json"
        return self._dir / name

    def get(self, key: _CacheKey) -> Any | None:
        path = self._path(key)
        with self._lock:
            if not path.exists():
                return None
            try:
                raw = path.read_bytes()
                if raw[:2] == b'\x1f\x8b':
                    raw = __import__("gzip").decompress(raw)
                data = json.loads(raw.decode("utf-8"))
                if time.time() - data.get("ts", 0) > self._ttl:
                    path.unlink(missing_ok=True)
                    return None
                get_collector().record_cache(hit=True, cache_type="llm")
                log.debug(f"[CACHE] HIT  {key.model} {key.mode}")
                return data["payload"]
            except Exception:
                path.unlink(missing_ok=True)
                return None

    def set(self, key: _CacheKey, payload: Any) -> None:
        path = self._path(key)
        with self._lock:
            try:
                blob = json.dumps({"ts": time.time(), "payload": payload}, ensure_ascii=False, indent=None)
                raw = blob.encode("utf-8")
                if len(raw) > 8192:
                    raw = __import__("gzip").compress(raw, compresslevel=6)
                path.write_bytes(raw)
            except OSError as e:
                log.warning(f"[CACHE] Write failed: {e}")
        self._maybe_evict_lru()

    def clear(self) -> int:
        with self._lock:
            files = list(self._dir.glob("*.json"))
            for f in files:
                f.unlink(missing_ok=True)
            return len(files)

    def _maybe_evict_lru(self) -> None:
        with self._lock:
            files = list(self._dir.glob("*.json"))
            total = sum(f.stat().st_size for f in files)
            if total <= self._max_size_bytes:
                return
            files.sort(key=lambda f: f.stat().st_mtime)
            for f in files:
                if total <= self._max_size_bytes * 0.8:
                    break
                try:
                    total -= f.stat().st_size
                    f.unlink(missing_ok=True)
                except OSError:
                    pass


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_timeout: float = 60.0
    window_seconds: float = 120.0

    _failures: list[float] = field(default_factory=list, repr=False)
    _state: str = field(default="closed", repr=False)
    _opened_at: float = field(default=0.0, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_success(self) -> None:
        with self._lock:
            if self._state == "half_open":
                self._state = "closed"
                self._failures.clear()
                log.info("[CB] Closed after recovery")
            elif self._state == "closed":
                self._failures.clear()

    def record_failure(self) -> None:
        now = time.time()
        with self._lock:
            if self._state == "half_open":
                self._state = "open"
                self._opened_at = now
                log.warning("[CB] Re-opened on recovery failure")
                return
            self._failures = [t for t in self._failures if now - t < self.window_seconds]
            self._failures.append(now)
            if len(self._failures) >= self.failure_threshold and self._state == "closed":
                self._state = "open"
                self._opened_at = now
                log.warning(f"[CB] OPENED — {len(self._failures)} failures in {self.window_seconds}s")

    def can_execute(self) -> bool:
        now = time.time()
        with self._lock:
            if self._state == "closed":
                return True
            if self._state == "open" and now - self._opened_at >= self.recovery_timeout:
                self._state = "half_open"
                log.info("[CB] Half-open — attempting recovery")
                return True
            return self._state == "half_open"

    def status(self) -> dict:
        with self._lock:
            return {
                "state": self._state,
                "failures_in_window": len(self._failures),
                "threshold": self.failure_threshold,
            }


class TokenBucket:
    """Simple token bucket for per-provider rate limiting."""

    def __init__(self, rate: float = 1.0, capacity: float = 3.0):
        self._rate = rate
        self._capacity = capacity
        self._tokens = capacity
        self._last_update = time.time()
        self._lock = threading.Lock()

    def acquire(self, tokens: float = 1.0) -> float:
        with self._lock:
            now = time.time()
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
        time.sleep(wait)
        return wait


class RequestCoalescer:
    def __init__(self):
        self._inflight: dict[str, threading.Event] = {}
        self._results: dict[str, Any] = {}
        self._lock = threading.Lock()

    def _key(self, system: str, user: str, model: str, mode: str) -> str:
        return json.dumps({"s": system, "u": user, "m": model, "mode": mode}, sort_keys=True)

    def execute(self, fn: Callable[[], Any], system: str, user: str, model: str, mode: str) -> Any:
        key = self._key(system, user, model, mode)
        with self._lock:
            if key in self._inflight:
                event = self._inflight[key]
            else:
                event = threading.Event()
                self._inflight[key] = event
                event = None

        if event is not None:
            event.wait(timeout=120)
            with self._lock:
                return self._results.get(key)

        try:
            result = fn()
            with self._lock:
                self._results[key] = result
            return result
        finally:
            with self._lock:
                ev = self._inflight.pop(key, None)
                if ev is not None:
                    ev.set()
                self._results.pop(key, None)


class RelayRouter:
    """Enhanced LLM router with resilience features and intelligent fallback."""

    def __init__(
        self,
        cache_ttl: int = 21600,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        timeout: float = DEFAULT_TIMEOUT,
        enable_rate_limit: bool = True,
        use_intelligent_fallback: bool = True,
    ):
        self._cache = DiskCache(ttl_seconds=cache_ttl)
        self._breakers: dict[str, CircuitBreaker] = {p: CircuitBreaker() for p in FALLBACK_CHAIN}
        self._coalescer = RequestCoalescer()
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._timeout = timeout
        self._stats = {"calls": 0, "cache_hits": 0, "fallbacks": 0, "failures": 0}
        self._lock = threading.Lock()
        self._enable_rate_limit = enable_rate_limit
        self._use_intelligent_fallback = use_intelligent_fallback
        self._intelligent_fallback = IntelligentFallback() if use_intelligent_fallback else None
        self._buckets: dict[str, TokenBucket] = {
            "anthropic": TokenBucket(rate=1.0, capacity=2),
            "openrouter": TokenBucket(rate=2.0, capacity=4),
            "groq": TokenBucket(rate=3.0, capacity=6),
            "google": TokenBucket(rate=2.0, capacity=4),
            "local": TokenBucket(rate=10.0, capacity=20),
        }

    def stats(self) -> dict:
        with self._lock:
            return dict(self._stats)

    def health(self) -> dict:
        return {p: b.status() for p, b in self._breakers.items()}

    def clear_cache(self) -> int:
        return self._cache.clear()

    def call(self, system: str, user: str, model: str = "", stream: bool = False) -> str:
        if not model:
            from config import DEFAULT_MODEL
            model = DEFAULT_MODEL
        if stream:
            return self._execute_with_fallback(system, user, model, stream=True)

        cache_key = _CacheKey.build(system, user, model, "text")
        cached = self._cache.get(cache_key)
        if cached is not None:
            with self._lock:
                self._stats["cache_hits"] += 1
            return cached

        def _fn():
            result = self._execute_with_fallback(system, user, model, stream=False)
            self._cache.set(cache_key, result)
            return result

        return self._coalescer.execute(_fn, system, user, model, "text")

    def call_json(self, system: str, user: str, model: str = "") -> dict:
        if not model:
            from config import DEFAULT_MODEL
            model = DEFAULT_MODEL

        cache_key = _CacheKey.build(system, user, model, "json")
        cached = self._cache.get(cache_key)
        if cached is not None:
            with self._lock:
                self._stats["cache_hits"] += 1
            return cached

        def _fn():
            result = self._execute_with_fallback_json(system, user, model)
            self._cache.set(cache_key, result)
            return result

        return self._coalescer.execute(_fn, system, user, model, "json")

    def _execute_with_fallback(self, system: str, user: str, model: str, stream: bool) -> str:
        providers = self._build_fallback_sequence(model)
        last_err = None
        from_provider = self._guess_provider(model)

        for prv in providers:
            if not self._breakers[prv].can_execute():
                continue
            if self._enable_rate_limit:
                self._buckets[prv].acquire(1.0)
            t0 = time.perf_counter()
            try:
                result = self._retry_call(system, user, prv, stream)
                self._breakers[prv].record_success()
                latency_ms = (time.perf_counter() - t0) * 1000
                with self._lock:
                    self._stats["calls"] += 1
                get_collector().record_provider(prv, latency_ms, True)
                if prv != from_provider:
                    get_collector().record_fallback(from_provider, prv)
                return result
            except Exception as e:
                latency_ms = (time.perf_counter() - t0) * 1000
                self._breakers[prv].record_failure()
                last_err = e
                log.warning(f"[RELAY] {prv} failed: {e}")
                with self._lock:
                    self._stats["failures"] += 1
                get_collector().record_provider(prv, latency_ms, False, error=str(e)[:120])
                continue

        raise RuntimeError(f"All providers exhausted. Last error: {last_err}")

    def _execute_with_fallback_json(self, system: str, user: str, model: str) -> dict:
        providers = self._build_fallback_sequence(model)
        last_err = None
        from_provider = self._guess_provider(model)

        for prv in providers:
            if not self._breakers[prv].can_execute():
                continue
            if self._enable_rate_limit:
                self._buckets[prv].acquire(1.0)
            t0 = time.perf_counter()
            try:
                result = self._retry_call_json(system, user, prv)
                self._breakers[prv].record_success()
                latency_ms = (time.perf_counter() - t0) * 1000
                with self._lock:
                    self._stats["calls"] += 1
                get_collector().record_provider(prv, latency_ms, True)
                if prv != from_provider:
                    get_collector().record_fallback(from_provider, prv)
                return result
            except Exception as e:
                latency_ms = (time.perf_counter() - t0) * 1000
                self._breakers[prv].record_failure()
                last_err = e
                log.warning(f"[RELAY] JSON {prv} failed: {e}")
                with self._lock:
                    self._stats["failures"] += 1
                get_collector().record_provider(prv, latency_ms, False, error=str(e)[:120])
                continue

        raise RuntimeError(f"All JSON providers exhausted. Last error: {last_err}")

    def _retry_call(self, system: str, user: str, provider: str, stream: bool) -> str:
        model_name = self._find_model_for_provider(provider)
        for attempt in range(1, self._max_retries + 1):
            try:
                return self._timed_call(system, user, model_name, stream)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
                if attempt == self._max_retries:
                    raise
                delay = self._base_delay * (2 ** (attempt - 1))
                jitter = random.uniform(0, delay * 0.5)
                total_delay = delay + jitter
                log.debug(f"[RELAY] Retry {attempt}/{self._max_retries} after {total_delay:.1f}s — {e}")
                time.sleep(total_delay)
        raise RuntimeError("Unexpected exit from retry loop")

    def _retry_call_json(self, system: str, user: str, provider: str) -> dict:
        model_name = self._find_model_for_provider(provider)
        for attempt in range(1, self._max_retries + 1):
            try:
                return self._timed_call_json(system, user, model_name)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                if attempt == self._max_retries:
                    raise
                delay = self._base_delay * (2 ** (attempt - 1))
                jitter = random.uniform(0, delay * 0.5)
                total_delay = delay + jitter
                log.debug(f"[RELAY] JSON retry {attempt}/{self._max_retries} after {total_delay:.1f}s — {e}")
                time.sleep(total_delay)
        raise RuntimeError("Unexpected exit from JSON retry loop")

    def _timed_call(self, system: str, user: str, model: str, stream: bool) -> str:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_orig_call, system, user, model, stream)
            return future.result(timeout=self._timeout)

    def _timed_call_json(self, system: str, user: str, model: str) -> dict:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_orig_call_json, system, user, model)
            return future.result(timeout=self._timeout)

    def _build_fallback_sequence(self, preferred_model: str) -> list[str]:
        """Use intelligent fallback if enabled, else fallback chain."""
        if self._use_intelligent_fallback and self._intelligent_fallback:
            try:
                return self._intelligent_fallback.build_fallback_sequence(
                    preferred=preferred_model,
                    min_success_rate=0.2
                )
            except Exception as e:
                log.warning(f"[RELAY] Intelligent fallback failed: {e}, using chain fallback")

        try:
            preferred_provider, _ = validate_config(preferred_model)
        except SystemExit:
            preferred_provider = "local"

        sequence = [preferred_provider]
        for p in FALLBACK_CHAIN:
            if p != preferred_provider and p not in sequence:
                sequence.append(p)
        return sequence

    def _find_model_for_provider(self, provider: str) -> str:
        for name, (prv, _mid) in MODELS.items():
            if prv == provider:
                if provider == "local":
                    return name
                if API_KEYS.get(provider):
                    return name
        return "local"

    def _guess_provider(self, model: str) -> str:
        try:
            return validate_config(model)[0]
        except SystemExit:
            return "local"


class CachedLLMCall:
    _router: RelayRouter | None = None
    _lock = threading.Lock()

    @classmethod
    def _get_router(cls) -> RelayRouter:
        with cls._lock:
            if cls._router is None:
                cls._router = RelayRouter()
            return cls._router

    @classmethod
    def call(cls, system: str, user: str, model: str = "", stream: bool = False) -> str:
        return cls._get_router().call(system, user, model, stream)

    @classmethod
    def call_json(cls, system: str, user: str, model: str = "") -> dict:
        return cls._get_router().call_json(system, user, model)

    @classmethod
    def stats(cls) -> dict:
        return cls._get_router().stats()

    @classmethod
    def health(cls) -> dict:
        return cls._get_router().health()
