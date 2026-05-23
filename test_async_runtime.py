"""
test_async_runtime.py — Unit tests for the async execution layer.
Run: python test_async_runtime.py
Target: Python 3.11+
"""

import asyncio
import sys
import time

sys.path.insert(0, '.')

print("=== Testing Async Circuit Breaker ===")
from agent_core.async_runtime import AsyncCircuitBreaker

async def test_async_circuit_breaker():
    cb = AsyncCircuitBreaker(failure_threshold=2, recovery_timeout=0.3)
    assert await cb.can_execute()
    await cb.record_failure()
    assert await cb.can_execute()
    await cb.record_failure()
    assert not await cb.can_execute()  # OPEN
    await asyncio.sleep(0.35)
    assert await cb.can_execute()  # half_open
    await cb.record_success()
    assert await cb.can_execute()  # closed
    print("  AsyncCircuitBreaker OK")

asyncio.run(test_async_circuit_breaker())

print("\n=== Testing Async Token Bucket ===")
from agent_core.async_runtime import AsyncTokenBucket

async def test_async_token_bucket():
    tb = AsyncTokenBucket(rate=10.0, capacity=3.0)
    assert await tb.try_acquire(1.0)  # instant
    assert await tb.try_acquire(2.0)  # instant, 0 left
    assert not await tb.try_acquire(1.0)  # empty
    waited = await tb.acquire(1.0)
    assert waited > 0.0
    print(f"  AsyncTokenBucket OK (waited {waited*1000:.1f}ms)")

asyncio.run(test_async_token_bucket())

print("\n=== Testing Async Disk Cache ===")
from agent_core.async_runtime import AsyncDiskCache
import tempfile
from pathlib import Path

async def test_async_disk_cache():
    with tempfile.TemporaryDirectory() as td:
        cache = AsyncDiskCache(cache_dir=td, ttl_seconds=2)
        await cache.set("test_key", {"hello": "world"})
        got = await cache.get("test_key")
        assert got == {"hello": "world"}, f"Expected hit, got {got}"
        # Expiration
        await asyncio.sleep(2.1)
        expired = await cache.get("test_key")
        assert expired is None, "Expected expired"
        print("  AsyncDiskCache OK")

asyncio.run(test_async_disk_cache())

print("\n=== Testing Async Relay ===")
from agent_core.async_runtime import AsyncRelay

async def test_async_relay():
    relay = AsyncRelay(max_concurrency=5, request_timeout=1.0)

    async def dummy_ok():
        await asyncio.sleep(0.01)
        return "ok"

    async def dummy_slow():
        await asyncio.sleep(2.0)
        return "too late"

    result = await relay.call("local", dummy_ok)
    assert result == "ok"

    try:
        await relay.call("local", dummy_slow)
        assert False, "Expected timeout"
    except asyncio.TimeoutError:
        pass

    health = relay.health()
    assert "local" in health
    print("  AsyncRelay OK")

asyncio.run(test_async_relay())

print("\n=== Testing Task Supervisor ===")
from agent_core.async_runtime import TaskSupervisor

async def test_supervisor():
    sup = TaskSupervisor()

    async def good():
        await asyncio.sleep(0.01)
        return 42

    async def bad():
        await asyncio.sleep(0.01)
        raise ValueError("intentional")

    results = await sup.supervised_gather({"good": good, "bad": bad})
    assert results["good"].success and results["good"].result == 42
    assert not results["bad"].success
    assert isinstance(results["bad"].exception, ValueError)

    # bounded_map
    async def double(x):
        await asyncio.sleep(0.01)
        return x * 2

    mapped = await sup.bounded_map(double, [1, 2, 3, 4, 5], concurrency=2)
    assert mapped == [2, 4, 6, 8, 10]
    print("  TaskSupervisor OK")

asyncio.run(test_supervisor())

print("\n=== Testing Timeout Envelope ===")
from agent_core.async_runtime import timeout_envelope

async def test_timeout_envelope():
    @timeout_envelope(0.1)
    async def fast():
        await asyncio.sleep(0.01)
        return "done"

    @timeout_envelope(0.1)
    async def slow():
        await asyncio.sleep(0.5)
        return "never"

    assert await fast() == "done"
    try:
        await slow()
        assert False
    except asyncio.TimeoutError:
        pass
    print("  timeout_envelope OK")

asyncio.run(test_timeout_envelope())

print("\n=== Testing Async Timed Decorator ===")
from agent_core.async_runtime import async_timed
from agent_core.metrics_collector import get_collector, reset_collector

reset_collector()

async def test_async_timed():
    @async_timed("test_coro", provider="test")
    async def my_coro():
        await asyncio.sleep(0.01)
        return "result"

    @async_timed("test_fail", provider="test")
    async def my_fail():
        await asyncio.sleep(0.01)
        raise RuntimeError("boom")

    assert await my_coro() == "result"
    try:
        await my_fail()
    except RuntimeError:
        pass

    m = get_collector()
    stages = [r.stage for r in m._stages]
    assert "test_coro" in stages
    assert "test_fail" in stages
    print("  async_timed OK")

asyncio.run(test_async_timed())

print("\n=== Testing AsyncRuntime Facade ===")
from agent_core.async_runtime import AsyncRuntime

async def test_async_runtime_facade():
    rt = AsyncRuntime.get()
    health = rt.health()
    assert "relay" in health
    assert "relay_stats" in health
    print("  AsyncRuntime OK")

asyncio.run(test_async_runtime_facade())

print("\n=== ALL ASYNC RUNTIME TESTS PASSED ===")
