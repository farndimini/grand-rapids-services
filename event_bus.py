"""
event_bus.py — Event-Driven Orchestration Bus
===============================================
Lightweight pub/sub event bus that decouples subsystems:

  Before: module → module → module (tight coupling)
  After:  module → emit → bus → dispatch → handler(s)

Prevents orchestration explosion, circular calls, governance spaghetti.
Zero dependencies, thread-safe, event chaining, deferred dispatch.
"""

from __future__ import annotations

import time
import uuid
import logging
import threading
from typing import Any, Callable, Optional

log = logging.getLogger("event_bus")


# ── Standard Event Types ─────────────────────────────────

EVENT_PIPELINE_STARTED = "pipeline.started"
EVENT_PIPELINE_COMPLETED = "pipeline.completed"
EVENT_PIPELINE_BLOCKED = "pipeline.blocked"
EVENT_PIPELINE_GOVERNANCE = "pipeline.governance"
EVENT_CONSENSUS_COMPLETED = "consensus.completed"
EVENT_DAG_BUILT = "dag.built"
EVENT_TRUTH_REGISTERED = "truth.registered"
EVENT_TRUST_EVALUATED = "trust.evaluated"
EVENT_REPAIR_ATTEMPTED = "repair.attempted"
EVENT_REPAIR_FAILED = "repair.failed"
EVENT_CONTRADICTION_DETECTED = "contradiction.detected"
EVENT_HALLUCINATION_DETECTED = "hallucination.detected"
EVENT_ARTICLE_GENERATED = "article.generated"
EVENT_ARTICLE_REPAIRED = "article.repaired"
EVENT_ARTICLE_QUARANTINED = "article.quarantined"
EVENT_SWARM_COMPLETED = "swarm.completed"
EVENT_GOVERNOR_AUDITED = "governor.audited"
EVENT_SITE_INGESTED = "site.ingested"
EVENT_TEMPORAL_EXPIRY_DETECTED = "temporal.expiry_detected"
EVENT_REPAIR_ORCHESTRATED = "repair.orchestrated"
EVENT_TRUST_COLLAPSE = "trust.collapse"
EVENT_PUBLISH_BLOCKED = "publish.blocked"

ALL_EVENTS = [
    EVENT_PIPELINE_STARTED, EVENT_PIPELINE_COMPLETED,
    EVENT_PIPELINE_BLOCKED, EVENT_PIPELINE_GOVERNANCE,
    EVENT_CONSENSUS_COMPLETED, EVENT_DAG_BUILT,
    EVENT_TRUTH_REGISTERED, EVENT_TRUST_EVALUATED,
    EVENT_REPAIR_ATTEMPTED, EVENT_REPAIR_FAILED,
    EVENT_CONTRADICTION_DETECTED, EVENT_HALLUCINATION_DETECTED,
    EVENT_ARTICLE_GENERATED, EVENT_ARTICLE_REPAIRED,
    EVENT_ARTICLE_QUARANTINED, EVENT_SWARM_COMPLETED,
    EVENT_GOVERNOR_AUDITED, EVENT_SITE_INGESTED,
    EVENT_TEMPORAL_EXPIRY_DETECTED, EVENT_REPAIR_ORCHESTRATED,
    EVENT_TRUST_COLLAPSE, EVENT_PUBLISH_BLOCKED,
]


# ── Event ─────────────────────────────────────────────────

class Event:
    """A single event in the bus. Immutable after creation."""

    def __init__(
        self,
        event_type: str,
        payload: Optional[dict] = None,
        source: Optional[str] = None,
        parent_id: Optional[str] = None,
    ):
        self.id = uuid.uuid4().hex[:12]
        self.event_type = event_type
        self.payload = payload or {}
        self.source = source or "unknown"
        self.parent_id = parent_id
        self.created_at = time.time()
        self._dispatched = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "payload": dict(self.payload),
            "source": self.source,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
            "dispatched": self._dispatched,
        }

    def __repr__(self) -> str:
        return f"Event({self.event_type}, src={self.source}, id={self.id[:6]}...)"


# ── EventBus ──────────────────────────────────────────────

HandlerFn = Callable[[Event], Any]


class EventBus:
    """Lightweight event bus with pub/sub and deferred dispatch.

    Thread-safe. Supports event chaining (handlers can emit new events).
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._subscriptions: dict[str, list[dict]] = {}  # type → [{handler, filter_fn, name}]
        self._deferred: list[Event] = []
        self._history: list[Event] = []
        self._max_history = 1000
        self._emit_count = 0
        self._handler_count = 0
        self._chain_depth = 0
        self._max_chain_depth = 20  # prevent infinite chains

    # ── Subscription management ──

    def on(
        self,
        event_type: str,
        handler: HandlerFn,
        filter_fn: Optional[Callable[[Event], bool]] = None,
        name: Optional[str] = None,
    ) -> str:
        """Subscribe to an event type. Returns subscription ID for off()."""
        sub_id = uuid.uuid4().hex[:12]
        with self._lock:
            if event_type not in self._subscriptions:
                self._subscriptions[event_type] = []
            self._subscriptions[event_type].append({
                "id": sub_id,
                "handler": handler,
                "filter_fn": filter_fn,
                "name": name or getattr(handler, "__name__", "anonymous"),
            })
            self._handler_count += 1
        log.debug("[BUS] subscribed %s to '%s'", name or handler.__name__, event_type)
        return sub_id

    def on_any(self, handler: HandlerFn) -> str:
        """Subscribe to ALL events. Useful for logging/monitoring."""
        return self.on("*", handler)

    def off(self, event_type: str, sub_id: str) -> bool:
        """Unsubscribe by subscription ID."""
        with self._lock:
            subs = self._subscriptions.get(event_type, [])
            before = len(subs)
            self._subscriptions[event_type] = [s for s in subs if s["id"] != sub_id]
            removed = before - len(self._subscriptions.get(event_type, []))
            if removed:
                self._handler_count -= 1
            return removed > 0

    def clear(self, event_type: Optional[str] = None) -> None:
        """Remove all subscriptions for an event type (or all)."""
        with self._lock:
            if event_type:
                removed = len(self._subscriptions.pop(event_type, []))
                self._handler_count -= removed
            else:
                self._subscriptions.clear()
                self._handler_count = 0

    # ── Emission ──

    def emit(
        self,
        event_type: str,
        payload: Optional[dict] = None,
        source: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> Event:
        """Emit an event synchronously. All matching handlers fire immediately."""
        event = Event(event_type, payload, source, parent_id)
        self._emit_count += 1
        self._trace_event(event)

        with self._lock:
            handlers = list(self._subscriptions.get(event_type, []))
            wild_handlers = list(self._subscriptions.get("*", []))

        all_handlers = handlers + wild_handlers

        # Chain depth tracking
        self._chain_depth += 1
        if self._chain_depth > self._max_chain_depth:
            self._chain_depth -= 1
            log.error("[BUS] Chain depth exceeded (%d) for '%s' — aborting",
                       self._max_chain_depth, event_type)
            return event

        for sub in all_handlers:
            try:
                fn_filter = sub.get("filter_fn")
                if fn_filter and not fn_filter(event):
                    continue
                sub["handler"](event)
            except Exception as e:
                log.error("[BUS] Handler '%s' failed on '%s': %s",
                           sub.get("name", "?"), event_type, e)

        self._chain_depth -= 1
        event._dispatched = True
        return event

    def emit_deferred(
        self,
        event_type: str,
        payload: Optional[dict] = None,
        source: Optional[str] = None,
    ) -> Event:
        """Queue an event for deferred dispatch. Call flush() to dispatch."""
        event = Event(event_type, payload, source)
        with self._lock:
            self._deferred.append(event)
        return event

    def flush(self) -> int:
        """Dispatch all deferred events. Returns count dispatched."""
        with self._lock:
            batch = list(self._deferred)
            self._deferred.clear()
        count = 0
        for event in batch:
            self.emit(event.event_type, event.payload, event.source)
            count += 1
        return count

    # ── Introspection ──

    def statistics(self) -> dict:
        with self._lock:
            total_subs = sum(len(v) for v in self._subscriptions.values())
            return {
                "subscriptions": total_subs,
                "handler_count": self._handler_count,
                "emit_count": self._emit_count,
                "deferred_pending": len(self._deferred),
                "history_size": len(self._history),
                "event_types": list(self._subscriptions.keys()),
            }

    def get_history(
        self,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        events = self._history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return [e.to_dict() for e in events[-limit:]]

    # ── Internal ──

    def _trace_event(self, event: Event) -> None:
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

    def __repr__(self) -> str:
        s = self.statistics()
        return (
            f"EventBus(subs={s['subscriptions']}, emitted={s['emit_count']}, "
            f"handlers={s['handler_count']})"
        )


# ── Global Singleton ──────────────────────────────────────

_BUS: Optional[EventBus] = None


def get_bus() -> EventBus:
    global _BUS
    if _BUS is None:
        _BUS = EventBus()
    return _BUS


def reset_bus() -> None:
    global _BUS
    _BUS = None


# ── Convenience helpers ──────────────────────────────────

def on(event_type: str, handler: HandlerFn, filter_fn=None, name=None) -> str:
    """Quick-access subscribe."""
    return get_bus().on(event_type, handler, filter_fn, name)


def on_any(handler: HandlerFn) -> str:
    """Quick-access subscribe to all events."""
    return get_bus().on("*", handler)


def emit(
    event_type: str,
    payload: Optional[dict] = None,
    source: Optional[str] = None,
) -> Event:
    """Quick-access emit."""
    return get_bus().emit(event_type, payload, source)


def on_pipeline_start(handler: HandlerFn) -> str:
    return get_bus().on(EVENT_PIPELINE_STARTED, handler)


def on_pipeline_complete(handler: HandlerFn) -> str:
    return get_bus().on(EVENT_PIPELINE_COMPLETED, handler)


def on_pipeline_blocked(handler: HandlerFn) -> str:
    return get_bus().on(EVENT_PIPELINE_BLOCKED, handler)


def on_consensus_complete(handler: HandlerFn) -> str:
    return get_bus().on(EVENT_CONSENSUS_COMPLETED, handler)


def on_dag_built(handler: HandlerFn) -> str:
    return get_bus().on(EVENT_DAG_BUILT, handler)


def on_trust_evaluated(handler: HandlerFn) -> str:
    return get_bus().on(EVENT_TRUST_EVALUATED, handler)


def on_swarm_completed(handler: HandlerFn) -> str:
    return get_bus().on(EVENT_SWARM_COMPLETED, handler)


def on_publish_blocked(handler: HandlerFn) -> str:
    return get_bus().on(EVENT_PUBLISH_BLOCKED, handler)


def on_article_quarantined(handler: HandlerFn) -> str:
    return get_bus().on(EVENT_ARTICLE_QUARANTINED, handler)
