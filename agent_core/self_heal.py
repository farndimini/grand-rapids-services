"""
self_heal.py — Auto-recovery, Health Monitoring, and Self-Healing Layer
========================================================================
Provides:
  • HealthMonitor — tracks system health metrics and provider status
  • CircuitBreaker — per-provider failure isolation (imported from relay.py)
  • SelfHeal — automated recovery decisions and retry strategy tweaks

NOTE: CircuitBreaker is imported from relay.py to maintain a single canonical
implementation. agent_core/__init__.py re-exports it from self_heal for
backward compatibility.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

# Single canonical CircuitBreaker implementation — imported from relay
from agent_core.relay import CircuitBreaker

log = logging.getLogger("agent_core.self_heal")


# ──────────────────────────────────────────────────────────────
#  Health Monitor
# ──────────────────────────────────────────────────────────────

@dataclass
class HealthSnapshot:
    timestamp: float
    provider: str
    latency_ms: float
    success: bool
    error: str | None = None


class HealthMonitor:
    """Track rolling health stats for every LLM provider and pipeline stage."""

    def __init__(self, max_history: int = 100):
        self._history: dict[str, list[HealthSnapshot]] = {}
        self._max_history = max_history
        self._lock = threading.Lock()

    def record(self, provider: str, latency_ms: float, success: bool, error: str | None = None) -> None:
        snap = HealthSnapshot(time.time(), provider, latency_ms, success, error)
        with self._lock:
            self._history.setdefault(provider, []).append(snap)
            if len(self._history[provider]) > self._max_history:
                self._history[provider].pop(0)

    def uptime_pct(self, provider: str, window_secs: float = 300.0) -> float:
        """Return success ratio for provider in last N seconds."""
        now = time.time()
        with self._lock:
            snaps = [s for s in self._history.get(provider, []) if now - s.timestamp <= window_secs]
        if not snaps:
            return 1.0
        return sum(1 for s in snaps if s.success) / len(snaps)

    def avg_latency(self, provider: str, window_secs: float = 300.0) -> float | None:
        now = time.time()
        with self._lock:
            snaps = [s for s in self._history.get(provider, []) if now - s.timestamp <= window_secs and s.success]
        if not snaps:
            return None
        return sum(s.latency_ms for s in snaps) / len(snaps)

    def summary(self) -> dict[str, dict]:
        result = {}
        with self._lock:
            providers = list(self._history.keys())
        for p in providers:
            result[p] = {
                "uptime_5m": round(self.uptime_pct(p, 300), 2),
                "uptime_1h": round(self.uptime_pct(p, 3600), 2),
                "avg_latency_ms": round(self.avg_latency(p, 300), 0) if self.avg_latency(p, 300) else None,
            }
        return result


# ──────────────────────────────────────────────────────────────
#  Self-Heal Engine
# ──────────────────────────────────────────────────────────────

class SelfHeal:
    """High-level self-healing coordinator.

    Watches health stats and recommends strategy adjustments:
      • provider fallbacks        → when uptime drops
      • rate-limit increases      → when 429s spike
      • cache TTL extensions      → when providers unstable
      • max_workers reduction     → when errors correlate with load
    """

    def __init__(self, monitor: HealthMonitor | None = None):
        self.monitor = monitor or HealthMonitor()

    def recommend(self) -> dict[str, Any]:
        """Return actionable recommendations based on current health."""
        recs: dict[str, Any] = {}
        summary = self.monitor.summary()

        for provider, stats in summary.items():
            uptime = stats.get("uptime_5m", 1.0)
            if uptime < 0.3:
                recs[provider] = {
                    "action": "deprioritize",
                    "reason": f"Uptime {uptime:.0%} in last 5 min",
                    "fallback_order_delta": +2,
                }
            elif uptime < 0.6:
                recs[provider] = {
                    "action": "throttle",
                    "reason": f"Uptime {uptime:.0%} in last 5 min",
                    "extra_delay_ms": 2000,
                }
            else:
                recs[provider] = {"action": "healthy", "reason": f"Uptime {uptime:.0%}"}

        return recs

    def apply_recommendations(self, relay_router: Any) -> None:
        """Push recommendations into a RelayRouter instance (if provided)."""
        recs = self.recommend()
        for provider, action in recs.items():
            if action["action"] == "deprioritize" and hasattr(relay_router, "_deprioritize_provider"):
                relay_router._deprioritize_provider(provider)
                log.info(f"[SELF_HEAL] Deprioritized {provider}: {action['reason']}")
            elif action["action"] == "throttle" and hasattr(relay_router, "_add_delay"):
                relay_router._add_delay(provider, action.get("extra_delay_ms", 1000))
                log.info(f"[SELF_HEAL] Throttled {provider}: {action['reason']}")
