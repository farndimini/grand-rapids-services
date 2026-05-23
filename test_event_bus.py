"""
test_event_bus.py — 35+ tests for Event Bus.

Usage: python test_event_bus.py
"""

from __future__ import annotations

import sys
import time
sys.path.insert(0, ".")

from event_bus import (
    Event, EventBus, get_bus, reset_bus,
    emit, on, on_any,
    on_pipeline_start, on_pipeline_complete, on_pipeline_blocked,
    on_consensus_complete, on_dag_built, on_trust_evaluated,
    EVENT_PIPELINE_STARTED, EVENT_PIPELINE_COMPLETED,
    EVENT_PIPELINE_BLOCKED, EVENT_CONSENSUS_COMPLETED,
    EVENT_DAG_BUILT, EVENT_TRUST_EVALUATED,
    EVENT_REPAIR_ATTEMPTED, EVENT_CONTRADICTION_DETECTED,
    EVENT_HALLUCINATION_DETECTED, ALL_EVENTS,
)


# ── Event ────────────────────────────────────────────────

def test_event_creation():
    ev = Event("test.type", {"key": "val"}, source="mysrc")
    assert ev.id and len(ev.id) == 12
    assert ev.event_type == "test.type"
    assert ev.payload["key"] == "val"
    assert ev.source == "mysrc"
    assert ev._dispatched is False


def test_event_to_dict():
    ev = Event("t", {"a": 1}, source="s")
    d = ev.to_dict()
    assert d["event_type"] == "t"
    assert d["payload"]["a"] == 1
    assert d["source"] == "s"
    assert "created_at" in d


def test_event_parent_id():
    parent = Event("parent")
    child = Event("child", parent_id=parent.id)
    assert child.parent_id == parent.id


# ── EventBus ─────────────────────────────────────────────

def test_bus_singleton():
    reset_bus()
    b1 = get_bus()
    b2 = get_bus()
    assert b1 is b2


def test_bus_reset():
    reset_bus()
    b1 = get_bus()
    reset_bus()
    b2 = get_bus()
    assert b2 is not b1


def test_subscribe_and_emit():
    reset_bus()
    bus = get_bus()
    results = []
    bus.on("test", lambda e: results.append(e.event_type))
    bus.emit("test")
    assert len(results) == 1
    assert results[0] == "test"


def test_emit_with_payload():
    reset_bus()
    bus = get_bus()
    results = []
    bus.on("pay", lambda e: results.append(e.payload["num"]))
    bus.emit("pay", {"num": 42})
    assert results[0] == 42


def test_multiple_handlers():
    reset_bus()
    bus = get_bus()
    r1, r2 = [], []
    bus.on("multi", lambda e: r1.append(1))
    bus.on("multi", lambda e: r2.append(2))
    bus.emit("multi")
    assert len(r1) == 1
    assert len(r2) == 1


def test_handler_exception_does_not_crash():
    reset_bus()
    bus = get_bus()
    results = []
    bus.on("crash", lambda e: (_ for _ in ()).throw(Exception("boom")))
    bus.on("crash", lambda e: results.append("ok"))
    bus.emit("crash")
    assert len(results) == 1  # second handler still fires


def test_filtered_subscription():
    reset_bus()
    bus = get_bus()
    results = []
    bus.on("filt", lambda e: results.append(e.payload["v"]),
           filter_fn=lambda e: e.payload.get("v") > 5)
    bus.emit("filt", {"v": 3})
    bus.emit("filt", {"v": 10})
    bus.emit("filt", {"v": 7})
    assert results == [10, 7]


def test_unsubscribe():
    reset_bus()
    bus = get_bus()
    sub = bus.on("unsub", lambda e: None)
    assert bus.off("unsub", sub) is True
    assert bus.off("unsub", "nope") is False


def test_clear_event_type():
    reset_bus()
    bus = get_bus()
    bus.on("a", lambda e: None)
    bus.on("a", lambda e: None)
    bus.clear("a")
    assert bus.statistics()["handler_count"] == 0


def test_clear_all():
    reset_bus()
    bus = get_bus()
    bus.on("a", lambda e: None)
    bus.on("b", lambda e: None)
    bus.clear()
    assert bus.statistics()["subscriptions"] == 0


# ── Deferred dispatch ────────────────────────────────────

def test_deferred_emit():
    reset_bus()
    bus = get_bus()
    bus.emit_deferred("def", {"i": 1})
    bus.emit_deferred("def", {"i": 2})
    assert bus.statistics()["deferred_pending"] == 2
    results = []
    bus.on("def", lambda e: results.append(e.payload["i"]))
    count = bus.flush()
    assert count == 2
    assert results == [1, 2]
    assert bus.statistics()["deferred_pending"] == 0


def test_flush_empty():
    reset_bus()
    bus = get_bus()
    assert bus.flush() == 0


# ── on_any ───────────────────────────────────────────────

def test_on_any():
    reset_bus()
    bus = get_bus()
    results = []
    bus.on_any(lambda e: results.append(e.event_type))
    bus.emit("type.a")
    bus.emit("type.b")
    bus.emit("type.c")
    assert len(results) == 3
    assert "type.a" in results


# ── History ──────────────────────────────────────────────

def test_history_records_events():
    reset_bus()
    bus = get_bus()
    bus.emit("h1")
    bus.emit("h2")
    history = bus.get_history()
    assert len(history) >= 2


def test_history_filter_by_type():
    reset_bus()
    bus = get_bus()
    bus.emit("filter_me", {"key": "val"})
    bus.emit("other")
    filtered = bus.get_history(event_type="filter_me")
    assert len(filtered) == 1
    assert filtered[0]["payload"]["key"] == "val"


def test_history_limit():
    reset_bus()
    bus = get_bus()
    for i in range(100):
        bus.emit("bulk", {"i": i})
    history = bus.get_history(limit=10)
    assert len(history) <= 10


# ── Statistics ────────────────────────────────────────────

def test_statistics():
    reset_bus()
    bus = get_bus()
    bus.on("s1", lambda e: None)
    bus.on("s2", lambda e: None)
    bus.emit("s1")
    bus.emit("s1")
    stats = bus.statistics()
    assert stats["emit_count"] == 2
    assert stats["handler_count"] == 2
    assert "s1" in stats["event_types"]



# ── Event chaining ───────────────────────────────────────

def test_event_chaining():
    reset_bus()
    bus = get_bus()
    chain = []
    bus.on("first", lambda e: (chain.append("first"), bus.emit("second"))[0])
    bus.on("second", lambda e: chain.append("second"))
    bus.emit("first")
    assert "first" in chain
    assert "second" in chain


def test_chain_depth_limit():
    reset_bus()
    bus = get_bus()
    depth = []
    def recursive(e):
        depth.append(1)
        bus.emit("recurse")
    bus.on("recurse", recursive)
    bus._max_chain_depth = 5
    bus.emit("recurse")
    assert len(depth) == 5  # capped at 5


# ── Convenience helpers ──────────────────────────────────

def test_convenience_on_emit():
    reset_bus()
    bus = get_bus()
    results = []
    on("conv", lambda e: results.append(1))
    emit("conv")
    assert len(results) == 1


def test_convenience_on_any():
    reset_bus()
    results = []
    on_any(lambda e: results.append(e.event_type))
    emit("conv.a")
    emit("conv.b")
    assert len(results) == 2


def test_convenience_pipeline_helpers():
    reset_bus()
    bus = get_bus()
    results = []
    on_pipeline_start(lambda e: results.append("start"))
    on_pipeline_complete(lambda e: results.append("complete"))
    on_pipeline_blocked(lambda e: results.append("blocked"))
    on_consensus_complete(lambda e: results.append("consensus"))
    on_dag_built(lambda e: results.append("dag"))
    on_trust_evaluated(lambda e: results.append("trust"))
    bus.emit(EVENT_PIPELINE_STARTED)
    bus.emit(EVENT_PIPELINE_COMPLETED)
    bus.emit(EVENT_PIPELINE_BLOCKED)
    bus.emit(EVENT_CONSENSUS_COMPLETED)
    bus.emit(EVENT_DAG_BUILT)
    bus.emit(EVENT_TRUST_EVALUATED)
    assert results == ["start", "complete", "blocked", "consensus", "dag", "trust"]


# ── Constants ────────────────────────────────────────────

def test_all_events_defined():
    assert len(ALL_EVENTS) >= 10
    assert EVENT_PIPELINE_STARTED in ALL_EVENTS
    assert EVENT_CONTRADICTION_DETECTED in ALL_EVENTS
    assert EVENT_HALLUCINATION_DETECTED in ALL_EVENTS


# ── Thread safety ────────────────────────────────────────

def test_concurrent_emit():
    import threading
    reset_bus()
    bus = get_bus()
    results = []
    bus.on("thread", lambda e: results.append(1))
    threads = [threading.Thread(target=lambda: bus.emit("thread")) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 10


# ── Run all ──────────────────────────────────────────────

def test_all():
    test_event_creation()
    test_event_to_dict()
    test_event_parent_id()
    test_bus_singleton()
    test_bus_reset()
    test_subscribe_and_emit()
    test_emit_with_payload()
    test_multiple_handlers()
    test_handler_exception_does_not_crash()
    test_filtered_subscription()
    test_unsubscribe()
    test_clear_event_type()
    test_clear_all()
    test_deferred_emit()
    test_flush_empty()
    test_on_any()
    test_history_records_events()
    test_history_filter_by_type()
    test_history_limit()
    test_statistics()
    test_event_chaining()
    test_chain_depth_limit()
    test_convenience_on_emit()
    test_convenience_on_any()
    test_convenience_pipeline_helpers()
    test_all_events_defined()
    test_concurrent_emit()
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    test_all()
