"""
metrics_collector.py — Centralized Pipeline Metrics & Observability
====================================================================
Tracks every critical dimension of SEO Agent Pro performance:
  • Stage latency (per pipeline step)
  • Provider success rates and fallback counts
  • Estimated API cost per run and per provider
  • Cache hit/miss ratios
  • Content quality score distributions
  • Throughput (articles/hour, words/minute)

Usage:
    from agent_core.metrics_collector import MetricsCollector, get_collector
    metrics = get_collector()
    metrics.record_stage("write_article", latency_ms=4500, success=True)
    metrics.record_provider("openrouter", latency_ms=3200, success=True, tokens=1200)
    print(metrics.summary())
"""

from __future__ import annotations

import json
import logging
import statistics
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("agent_core.metrics")

# ── Estimated cost per 1K tokens (USD) — rough industry averages ──
_COST_PER_1K_TOKENS: dict[str, float] = {
    "anthropic": 0.003,    # Claude Sonnet ~$3/M tokens input
    "openrouter": 0.002,   # OpenRouter premium ~$2/M tokens
    "groq": 0.0005,        # Groq ultra-fast ~$0.5/M tokens
    "google": 0.00035,     # Gemini Flash ~$0.35/M tokens
    "local": 0.0,          # Local inference — zero API cost
}

DEFAULT_METRICS_DIR = Path(__file__).resolve().parent.parent / "metrics"


@dataclass
class StageRecord:
    stage: str
    latency_ms: float
    success: bool
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderRecord:
    provider: str
    latency_ms: float
    success: bool
    timestamp: float
    tokens_used: int = 0
    error: str | None = None


class MetricsCollector:
    """Thread-safe collector for all pipeline metrics.

    Persists rolling windows to disk for survival across restarts.
    """

    def __init__(
        self,
        metrics_dir: Path | str = DEFAULT_METRICS_DIR,
        max_stage_history: int = 500,
        max_provider_history: int = 500,
        auto_persist_interval: int = 300,
    ):
        self._dir = Path(metrics_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._max_stage = max_stage_history
        self._max_provider = max_provider_history

        self._stages: list[StageRecord] = []
        self._providers: list[ProviderRecord] = []
        self._counters: dict[str, int] = {}
        self._quality_scores: list[int] = []
        self._lock = threading.Lock()
        self._start_time = time.time()

        self._load()
        if auto_persist_interval > 0:
            self._schedule_persist(auto_persist_interval)

    # ── Persistence ────────────────────────────────────────

    def _persist_path(self) -> Path:
        return self._dir / "metrics_state.json"

    def _load(self) -> None:
        path = self._persist_path()
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                blob = json.load(f)
            self._counters = blob.get("counters", {})
            self._quality_scores = blob.get("quality_scores", [])[-100:]
            log.debug("[METRICS] Loaded persisted state")
        except Exception as e:
            log.warning(f"[METRICS] Load failed: {e}")

    def persist(self) -> None:
        path = self._persist_path()
        try:
            with self._lock:
                blob = {
                    "counters": self._counters,
                    "quality_scores": self._quality_scores[-200:],
                    "saved_at": time.time(),
                }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(blob, f, ensure_ascii=False, indent=None)
        except Exception as e:
            log.warning(f"[METRICS] Persist failed: {e}")

    def _schedule_persist(self, interval: int) -> None:
        def _loop():
            while True:
                time.sleep(interval)
                self.persist()
        t = threading.Thread(target=_loop, daemon=True, name="metrics_persist")
        t.start()

    # ── Recording ──────────────────────────────────────────

    def record_stage(self, stage: str, latency_ms: float, success: bool, **meta) -> None:
        with self._lock:
            self._stages.append(StageRecord(stage, latency_ms, success, time.time(), meta))
            if len(self._stages) > self._max_stage:
                self._stages.pop(0)
            key = f"stage_{stage}_{'ok' if success else 'fail'}"
            self._counters[key] = self._counters.get(key, 0) + 1

    def record_provider(
        self,
        provider: str,
        latency_ms: float,
        success: bool,
        tokens_used: int = 0,
        error: str | None = None,
    ) -> None:
        with self._lock:
            self._providers.append(
                ProviderRecord(provider, latency_ms, success, time.time(), tokens_used, error)
            )
            if len(self._providers) > self._max_provider:
                self._providers.pop(0)
            key = f"provider_{provider}_{'ok' if success else 'fail'}"
            self._counters[key] = self._counters.get(key, 0) + 1
            if tokens_used > 0:
                self._counters[f"provider_{provider}_tokens"] = (
                    self._counters.get(f"provider_{provider}_tokens", 0) + tokens_used
                )

    def record_quality(self, score: int) -> None:
        with self._lock:
            self._quality_scores.append(score)
            if len(self._quality_scores) > 200:
                self._quality_scores.pop(0)

    def record_fallback(self, from_provider: str, to_provider: str) -> None:
        with self._lock:
            key = f"fallback_{from_provider}_to_{to_provider}"
            self._counters[key] = self._counters.get(key, 0) + 1
            self._counters["total_fallbacks"] = self._counters.get("total_fallbacks", 0) + 1

    def record_cache(self, hit: bool, cache_type: str = "llm") -> None:
        with self._lock:
            self._counters[f"cache_{cache_type}_{'hit' if hit else 'miss'}"] = (
                self._counters.get(f"cache_{cache_type}_{'hit' if hit else 'miss'}", 0) + 1
            )

    def increment(self, counter_name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[counter_name] = self._counters.get(counter_name, 0) + value

    # ── Queries ────────────────────────────────────────────

    def stage_latency(self, stage: str, window_secs: float = 3600.0) -> dict[str, float | None]:
        """Return {p50, p95, max, avg} latency for a stage (ms)."""
        now = time.time()
        with self._lock:
            latencies = [
                r.latency_ms
                for r in self._stages
                if r.stage == stage and now - r.timestamp <= window_secs
            ]
        if not latencies:
            return {"p50": None, "p95": None, "max": None, "avg": None, "count": 0}
        latencies.sort()
        n = len(latencies)
        return {
            "p50": latencies[n // 2],
            "p95": latencies[int(n * 0.95)],
            "max": latencies[-1],
            "avg": round(statistics.mean(latencies), 1),
            "count": n,
        }

    def provider_summary(self, window_secs: float = 3600.0) -> dict[str, dict]:
        """Return health stats per provider in the window."""
        now = time.time()
        with self._lock:
            records = [r for r in self._providers if now - r.timestamp <= window_secs]
        result: dict[str, dict] = {}
        for r in records:
            result.setdefault(r.provider, {"ok": 0, "fail": 0, "latencies": []})
            result[r.provider]["ok" if r.success else "fail"] += 1
            result[r.provider]["latencies"].append(r.latency_ms)
        for prov, stats in result.items():
            total = stats["ok"] + stats["fail"]
            stats["success_rate"] = round(stats["ok"] / total, 2) if total else 1.0
            stats["avg_latency_ms"] = round(statistics.mean(stats["latencies"]), 0) if stats["latencies"] else None
            stats["p95_latency_ms"] = round(sorted(stats["latencies"])[int(len(stats["latencies"]) * 0.95)], 0) if stats["latencies"] else None
            del stats["latencies"]
            # Cost estimate
            tokens = self._counters.get(f"provider_{prov}_tokens", 0)
            stats["estimated_cost_usd"] = round(
                (tokens / 1000) * _COST_PER_1K_TOKENS.get(prov, 0.0), 4
            )
        return result

    def cache_ratio(self, cache_type: str = "llm") -> dict[str, float]:
        with self._lock:
            hits = self._counters.get(f"cache_{cache_type}_hit", 0)
            misses = self._counters.get(f"cache_{cache_type}_miss", 0)
        total = hits + misses
        return {
            "hit_rate": round(hits / total, 3) if total else 0.0,
            "miss_rate": round(misses / total, 3) if total else 0.0,
            "total": total,
        }

    def quality_distribution(self) -> dict[str, Any]:
        with self._lock:
            scores = list(self._quality_scores)
        if not scores:
            return {"count": 0}
        return {
            "count": len(scores),
            "avg": round(statistics.mean(scores), 1),
            "min": min(scores),
            "max": max(scores),
            "p50": round(statistics.median(scores), 1),
        }

    def throughput(self) -> dict[str, float]:
        """Articles per hour and words per minute (since collector start)."""
        elapsed_h = (time.time() - self._start_time) / 3600
        with self._lock:
            articles = self._counters.get("articles_completed", 0)
            words = self._counters.get("total_words_generated", 0)
        return {
            "articles_per_hour": round(articles / elapsed_h, 2) if elapsed_h else 0.0,
            "words_per_minute": round(words / ((time.time() - self._start_time) / 60), 1) if elapsed_h else 0.0,
        }

    # ── Summary ────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        return {
            "uptime_hours": round((time.time() - self._start_time) / 3600, 2),
            "stage_latency_1h": {
                stage: self.stage_latency(stage, 3600)
                for stage in sorted({r.stage for r in self._stages[-100:]})
            },
            "provider_health_1h": self.provider_summary(3600),
            "cache": {
                "llm": self.cache_ratio("llm"),
                "serp": self.cache_ratio("serp"),
            },
            "quality": self.quality_distribution(),
            "throughput": self.throughput(),
            "counters": dict(self._counters),
            "total_fallbacks": self._counters.get("total_fallbacks", 0),
        }

    def print_summary(self) -> None:
        s = self.summary()
        print(f"\n{'═' * 56}")
        print("  PIPELINE METRICS")
        print(f"{'═' * 56}")
        print(f"  Uptime:        {s['uptime_hours']:.1f}h")
        print(f"  Throughput:    {s['throughput']['articles_per_hour']:.1f} articles/hr")
        print(f"  Quality (avg): {s['quality'].get('avg', '?')}/100")
        print(f"  Total fallbacks: {s['total_fallbacks']}")
        for prov, stats in s["provider_health_1h"].items():
            print(f"  {prov:12s}  OK {stats['ok']:>3d}  FAIL {stats['fail']:>3d}  "
                  f"rate {stats['success_rate']:.0%}  lat {stats['avg_latency_ms']:.0f}ms")
        for ctype, cratio in s["cache"].items():
            print(f"  Cache [{ctype:4s}]  hit rate {cratio['hit_rate']:.1%}")
        print(f"{'═' * 56}\n")


# ── Singleton accessor ────────────────────────────────────────

_collector_instance: MetricsCollector | None = None
_collector_lock = threading.Lock()


def get_collector() -> MetricsCollector:
    global _collector_instance
    with _collector_lock:
        if _collector_instance is None:
            _collector_instance = MetricsCollector()
        return _collector_instance


def reset_collector() -> None:
    global _collector_instance
    with _collector_lock:
        _collector_instance = None
