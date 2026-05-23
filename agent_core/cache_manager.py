"""
cache_manager.py — Disk-based SERP and LLM response cache (v2)
===============================================================
Enhancements:
  • LRU eviction when cache exceeds max size
  • Gzip compression for large entries
  • Per-type stats integration with MetricsCollector
  • Cache warming hints for frequently accessed keywords
  • Atomic writes with temp-file + rename

Usage:
    from agent_core.cache_manager import CacheManager
    cache = CacheManager(max_size_mb=100, default_ttl_hours=24)
    cache.save_serp("best laptop", serp_data)
    data = cache.load_serp("best laptop", max_age_hours=24)
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from agent_core.metrics_collector import get_collector

log = logging.getLogger("agent_core.cache_manager")

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "cache_store"


class CacheManager:
    """Persistent on-disk cache with TTL, compression, LRU eviction, and metrics."""

    def __init__(
        self,
        cache_dir: Path | str = DEFAULT_CACHE_DIR,
        default_ttl_hours: int = 24,
        max_size_mb: int = 100,
        compress_threshold_bytes: int = 4096,
    ):
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._default_ttl = default_ttl_hours * 3600
        self._max_size = max_size_mb * 1024 * 1024
        self._compress_threshold = compress_threshold_bytes
        self._lock = threading.Lock()

    # ── Internal helpers ─────────────────────────────────────

    def _keyword_slug(self, keyword: str) -> str:
        return hashlib.sha256(keyword.lower().encode("utf-8")).hexdigest()[:24]

    def _serp_path(self, keyword: str) -> Path:
        today = time.strftime("%Y%m%d")
        slug = self._keyword_slug(keyword)
        return self._dir / f"serp_{today}_{slug}.json"

    def _llm_path(self, system: str, user: str, model: str) -> Path:
        key = f"{model}:{system}:{user}"
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        return self._dir / f"llm_{h}.json"

    def _write_atomic(self, path: Path, payload_bytes: bytes) -> None:
        """Write to temp file then atomic rename."""
        fd, tmp = tempfile.mkstemp(dir=str(self._dir), suffix=".tmp")
        try:
            os.write(fd, payload_bytes)
            os.fsync(fd)
            os.close(fd)
            os.replace(tmp, str(path))
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _read_maybe_compressed(self, path: Path) -> bytes:
        raw = path.read_bytes()
        if raw[:2] == b'\x1f\x8b':
            return gzip.decompress(raw)
        return raw

    def _maybe_evict_lru(self) -> None:
        with self._lock:
            files = list(self._dir.glob("*.json"))
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
            log.info(f"[CACHE-MGR] LRU eviction triggered — size reduced to {total / 1024 / 1024:.1f} MB")

    # ── Public API ───────────────────────────────────────────

    def save_serp(self, keyword: str, data: dict) -> Path:
        path = self._serp_path(keyword)
        payload = {"cached_at": time.time(), "keyword": keyword, "data": data}
        blob = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        if len(blob) > self._compress_threshold:
            blob = gzip.compress(blob, compresslevel=6)
        with self._lock:
            self._write_atomic(path, blob)
        log.debug(f"[CACHE-MGR] SERP saved → {path.name}")
        self._maybe_evict_lru()
        return path

    def load_serp(self, keyword: str, max_age_hours: int | None = None) -> dict | None:
        path = self._serp_path(keyword)
        ttl = (max_age_hours * 3600) if max_age_hours is not None else self._default_ttl
        with self._lock:
            if not path.exists():
                get_collector().record_cache(hit=False, cache_type="serp")
                return None
            try:
                raw = self._read_maybe_compressed(path)
                payload = json.loads(raw.decode("utf-8"))
                age = time.time() - payload.get("cached_at", 0)
                if age > ttl:
                    log.debug(f"[CACHE-MGR] SERP expired for '{keyword}' ({age/3600:.1f}h)")
                    get_collector().record_cache(hit=False, cache_type="serp")
                    return None
                log.debug(f"[CACHE-MGR] SERP HIT for '{keyword}' ({age/3600:.1f}h)")
                get_collector().record_cache(hit=True, cache_type="serp")
                return payload.get("data")
            except (json.JSONDecodeError, OSError, Exception) as e:
                log.warning(f"[CACHE-MGR] SERP read failed: {e}")
                get_collector().record_cache(hit=False, cache_type="serp")
                return None

    def save_llm(self, system: str, user: str, model: str, response: str) -> Path:
        path = self._llm_path(system, user, model)
        payload = {"cached_at": time.time(), "model": model, "response": response}
        blob = json.dumps(payload, ensure_ascii=False, indent=None).encode("utf-8")
        if len(blob) > self._compress_threshold:
            blob = gzip.compress(blob, compresslevel=6)
        with self._lock:
            self._write_atomic(path, blob)
        self._maybe_evict_lru()
        return path

    def load_llm(self, system: str, user: str, model: str, max_age_hours: int | None = None) -> str | None:
        path = self._llm_path(system, user, model)
        ttl = (max_age_hours * 3600) if max_age_hours is not None else self._default_ttl
        with self._lock:
            if not path.exists():
                get_collector().record_cache(hit=False, cache_type="llm")
                return None
            try:
                raw = self._read_maybe_compressed(path)
                payload = json.loads(raw.decode("utf-8"))
                age = time.time() - payload.get("cached_at", 0)
                if age > ttl:
                    get_collector().record_cache(hit=False, cache_type="llm")
                    return None
                get_collector().record_cache(hit=True, cache_type="llm")
                return payload.get("response")
            except (json.JSONDecodeError, OSError, Exception):
                get_collector().record_cache(hit=False, cache_type="llm")
                return None

    def clear_all(self) -> int:
        with self._lock:
            files = list(self._dir.glob("*.json"))
            for f in files:
                f.unlink(missing_ok=True)
            return len(files)

    def clear_expired(self, max_age_hours: int | None = None) -> int:
        ttl = (max_age_hours * 3600) if max_age_hours is not None else self._default_ttl
        now = time.time()
        removed = 0
        with self._lock:
            for f in self._dir.glob("*.json"):
                try:
                    raw = self._read_maybe_compressed(f)
                    payload = json.loads(raw.decode("utf-8"))
                    if now - payload.get("cached_at", 0) > ttl:
                        f.unlink(missing_ok=True)
                        removed += 1
                except (json.JSONDecodeError, OSError, Exception):
                    f.unlink(missing_ok=True)
                    removed += 1
        return removed

    def stats(self) -> dict[str, Any]:
        total_size = 0
        count = 0
        serp_count = 0
        llm_count = 0
        with self._lock:
            for f in self._dir.glob("*.json"):
                count += 1
                total_size += f.stat().st_size
                if f.name.startswith("serp_"):
                    serp_count += 1
                elif f.name.startswith("llm_"):
                    llm_count += 1
        return {
            "files": count,
            "serp_files": serp_count,
            "llm_files": llm_count,
            "total_size_kb": round(total_size / 1024, 2),
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "cache_dir": str(self._dir),
            "max_size_mb": self._max_size / 1024 / 1024,
        }

    def warm_serp(self, keywords: list[str]) -> int:
        """Pre-warm cache by loading existing entries (no-op if missing). Returns hits."""
        hits = 0
        for kw in keywords:
            if self.load_serp(kw) is not None:
                hits += 1
        log.info(f"[CACHE-MGR] Warmed {hits}/{len(keywords)} SERP entries")
        return hits
