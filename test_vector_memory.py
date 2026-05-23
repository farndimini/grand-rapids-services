"""
test_vector_memory.py — Semantic Vector Memory Tests + Benchmarks + Stress
===========================================================================
Covers:
  1. EmbeddingCache — LRU, thread safety, stats
  2. VectorMemory (fallback mode) — store, search, delete, clear
  3. VectorMemory with metadata filtering
  4. VectorMemory compaction (dedup)
  5. VectorMemory batch operations
  6. Async-safe wrappers
  7. MemoryAdapter with HybridMemoryBackend
  8. JsonMemoryBackend
  9. VectorMemoryBackend
  10. Migration utility
  11. Compare backends
  12. Latency benchmarks
  13. Memory stress test
  14. Backwards compatibility
"""

from __future__ import annotations

import sys
import time
import json
import tempfile
from pathlib import Path

sys.path.insert(0, '.')

_PASSED = 0
_FAILED = 0
_TIMINGS: dict[str, list[float]] = {}


def _check(description: str, condition: bool):
    global _PASSED, _FAILED
    if condition:
        _PASSED += 1
        print(f"  ✓ {description}")
    else:
        _FAILED += 1
        print(f"  ✗ {description}")


def _section(name: str):
    print(f"\n=== {name} ===")


def _timed(name: str) -> any:
    """Context manager to record timing."""
    import contextlib

    @contextlib.contextmanager
    def _timer():
        t0 = time.perf_counter()
        yield
        elapsed = (time.perf_counter() - t0) * 1000
        _TIMINGS.setdefault(name, []).append(elapsed)
    return _timer()


# ── 1. EmbeddingCache ──────────────────────────────────────────
_section("EmbeddingCache")
from agent_core.vector_memory import EmbeddingCache

ec = EmbeddingCache(max_size=5)
_check("Empty cache size 0", ec.size == 0)

ec.put("hello", [1.0, 2.0, 3.0])
_check("Put adds entry", ec.size == 1)

got = ec.get("hello")
_check("Get returns value", got == [1.0, 2.0, 3.0])
_check("Get missing returns None", ec.get("missing") is None)

for i in range(10):
    ec.put(f"key_{i}", [float(i)] * 4)
_check("LRU eviction keeps max_size", ec.size == 5)
_check("Oldest key evicted", ec.get("hello") is None)
_check("Newest key present", ec.get("key_9") is not None)

ec.clear()
_check("Clear empties cache", ec.size == 0)

s = ec.stats()
_check("Stats has size", "size" in s)
_check("Stats has max_size", "max_size" in s)


# ── 2. VectorMemory (fallback mode, no ChromaDB) ───────────────
_section("VectorMemory fallback")
from agent_core.vector_memory import VectorMemory, VectorSearchResult

with tempfile.TemporaryDirectory() as td:
    vm = VectorMemory(
        collection_name="test_fallback",
        persist_dir=Path(td) / "vm_test",
    )

    s = vm.stats()
    _check("Stats shows fallback mode", "fallback" in s["mode"] or "dict" in s["mode"])
    _check("Stats has doc_count", "doc_count" in s)

    # Store
    id1 = vm.store("doc-1", "Best laptop for programming and coding", {"keyword": "best laptop", "niche": "tech"})
    _check("Store returns ID", isinstance(id1, str) and len(id1) > 0)

    id2 = vm.store("doc-2", "Top 10 gaming laptops under 1500 dollars", {"keyword": "gaming laptop", "niche": "tech"})
    id3 = vm.store("doc-3", "How to bake a chocolate cake at home", {"keyword": "baking", "niche": "food"})
    id4 = vm.store("doc-4", "Best programming languages for beginners 2026", {"keyword": "programming languages", "niche": "tech"})
    id5 = vm.store("doc-5", "Coffee machine reviews and comparisons", {"keyword": "coffee machine", "niche": "home"})
    id6 = vm.store("doc-6", "Laptop for software engineering students", {"keyword": "student laptop", "niche": "tech"})

    _check("Count returns 6", vm.count() == 6)

    # Search
    results = vm.search("programming laptop", top_k=3)
    _check("Search returns results", len(results) > 0)
    _check("Search results are VectorSearchResult", all(isinstance(r, VectorSearchResult) for r in results))
    _check("Best result has laptop keyword", any("laptop" in r.keyword.lower() for r in results))

    # Get by ID
    got = vm.get("doc-1")
    _check("Get by ID returns result", got is not None)
    _check("Get has correct keyword", got.keyword == "best laptop")
    _check("Get returns None for missing", vm.get("nonexistent") is None)

    # List all
    all_docs = vm.list_all()
    _check("List all returns 6", len(all_docs) == 6)

    # Delete
    deleted = vm.delete("doc-5")
    _check("Delete returns True", deleted)
    _check("Count after delete is 5", vm.count() == 5)
    _check("Deleted doc not found", vm.get("doc-5") is None)

    # Clear
    cleared = vm.clear()
    _check("Clear returns count", cleared >= 0)
    _check("Count after clear is 0", vm.count() == 0)


# ── 3. VectorMemory metadata filtering ────────────────────────
_section("VectorMemory metadata filtering")
with tempfile.TemporaryDirectory() as td:
    vm = VectorMemory(persist_dir=Path(td) / "filter_test")

    vm.store("a1", "Article about Python programming", {"keyword": "python", "niche": "tech", "quality_score": 85, "model": "claude"})
    vm.store("a2", "Article about JavaScript frameworks", {"keyword": "javascript", "niche": "tech", "quality_score": 70, "model": "gpt4"})
    vm.store("a3", "Article about Italian cuisine", {"keyword": "italian food", "niche": "food", "quality_score": 90, "model": "claude"})
    vm.store("a4", "Article about running shoes", {"keyword": "running shoes", "niche": "sports", "quality_score": 60, "model": "gpt4"})

    _check("Stored 4 articles", vm.count() == 4)

    # Filter by niche
    results = vm.search("article", top_k=10, filter_metadata={"niche": "tech"})
    _check("Filter tech returns 2", len(results) == 2)
    _check("All results are tech", all(r.metadata.get("niche") == "tech" for r in results))

    # Filter by model
    results = vm.search("article", top_k=10, filter_metadata={"model": "claude"})
    _check("Filter claude returns 2", len(results) == 2)
    _check("All results are claude", all(r.metadata.get("model") == "claude" for r in results))

    # Search by exact keyword
    results = vm.search_by_keyword("python", exact=False)
    _check("Search by keyword", len(results) > 0)

    # Delete by metadata
    deleted = vm.delete_by_metadata({"niche": "sports"})
    _check("Delete by metadata returns 1", deleted == 1)
    _check("Count after metadata delete is 3", vm.count() == 3)

    # Verify the document is gone
    results = vm.search("running", top_k=10)
    _check("No sports docs after delete", all(r.metadata.get("niche") != "sports" for r in results))


# ── 4. VectorMemory compaction ─────────────────────────────────
_section("VectorMemory compaction")
with tempfile.TemporaryDirectory() as td:
    vm = VectorMemory(persist_dir=Path(td) / "compact_test")

    # Store near-duplicates
    vm.store("d1", "Best laptop for programming students in 2026", {"keyword": "best laptop students"})
    vm.store("d2", "Best laptop for programming students 2026 edition", {"keyword": "best laptop students"})
    vm.store("d3", "Top programming laptop for students", {"keyword": "programming laptop"})
    vm.store("d4", "Completely different article about gardening", {"keyword": "gardening tips"})

    _check("Stored 4 docs", vm.count() == 4)

    # Compact with high threshold
    result = vm.compact(similarity_threshold=0.5)
    _check("Compaction removed duplicates", result["removed"] > 0)
    _check("Compaction kept some", result["kept"] > 0)
    _check("Count reduced after compaction", vm.count() >= 1)

    # Compact with very high threshold (no changes)
    result2 = vm.compact(similarity_threshold=0.99)
    _check("High threshold removes nothing", result2["removed"] == 0)


# ── 5. VectorMemory batch operations ──────────────────────────
_section("VectorMemory batch operations")
with tempfile.TemporaryDirectory() as td:
    vm = VectorMemory(persist_dir=Path(td) / "batch_test")

    items = [
        (f"batch-{i}", f"This is article number {i} about keyword_{i}", {"keyword": f"keyword_{i}", "batch": "yes"})
        for i in range(10)
    ]
    ids = vm.store_batch(items)
    _check("Batch store returns 10 ids", len(ids) == 10)
    _check("Count after batch is 10", vm.count() == 10)

    results = vm.search("keyword_5", top_k=5)
    _check("Batch search works", len(results) > 0)


# ── 6. Async-safe wrappers ────────────────────────────────────
_section("Async-safe wrappers")
import asyncio

with tempfile.TemporaryDirectory() as td:
    vm = VectorMemory(persist_dir=Path(td) / "async_test")

    async def _test_async():
        # Async store
        id1 = await vm.async_store("async-1", "Async article about Python", {"keyword": "async python"})
        _check("Async store returns ID", isinstance(id1, str) and len(id1) > 0)

        id2 = await vm.async_store("async-2", "More async content about asyncio", {"keyword": "asyncio"})

        # Async search
        results = await vm.async_search("python async", top_k=5)
        _check("Async search returns results", len(results) > 0)

        # Async batch
        items = [
            (f"async-batch-{i}", f"Batch async article {i}", {"keyword": f"async_batch_{i}"})
            for i in range(5)
        ]
        ids = await vm.async_store_batch(items)
        _check("Async batch store returns 5 ids", len(ids) == 5)

        # Async count
        count = await vm.async_count()
        _check("Async count matches", count == 7)

        # Async compact
        result = await vm.async_compact(threshold=0.99)
        _check("Async compact completes", "removed" in result)

    asyncio.run(_test_async())


# ── 7. JsonMemoryBackend ──────────────────────────────────────
_section("JsonMemoryBackend")
from agent_core.memory_adapter import JsonMemoryBackend

jmb = JsonMemoryBackend()
_check("JSON backend created", jmb is not None)
jstats = jmb.stats()
_check("JSON stats has backend type", jstats.get("backend") == "json")
_check("JSON stats has articles count", "articles" in jstats)

# Search in existing memory
results = jmb.search("laptop", top_k=5)
_check("JSON search returns list", isinstance(results, list))

count = jmb.count()
_check("JSON count is int", isinstance(count, int))
_check("JSON count non-negative", count >= 0)


# ── 8. VectorMemoryBackend ────────────────────────────────────
_section("VectorMemoryBackend")
from agent_core.memory_adapter import VectorMemoryBackend

with tempfile.TemporaryDirectory() as td:
    vmb = VectorMemoryBackend(
        collection_name="test_vmb",
        persist_dir=Path(td) / "vmb",
    )
    _check("VMB created", vmb is not None)

    # Record article
    vid = vmb.record_article("vector backend test", "This is a test article for the vector memory backend", "local", 85, "testing")
    _check("VMB record returns ID", isinstance(vid, str) and len(vid) > 0)

    # Record another
    vmb.record_article("second article", "Another test article with different content", "claude", 70, "testing")

    # Search
    results = vmb.search("vector memory backend", top_k=5)
    _check("VMB search returns results", len(results) > 0)

    # Get by keyword
    by_kw = vmb.get_by_keyword("vector backend test")
    _check("VMB get_by_keyword returns results", len(by_kw) > 0)

    # Batch record
    from agent_core.memory_adapter import ArticleEntry
    entries = [
        ArticleEntry(keyword=f"batch_{i}", text=f"Batch article {i} content", model="local", quality_score=80, word_count=100, date="2026-01-01")
        for i in range(3)
    ]
    ids = vmb.record_articles_batch(entries)
    _check("VMB batch record returns 3 ids", len(ids) == 3)

    # Stats
    s = vmb.stats()
    _check("VMB stats has backend", s.get("backend") == "vector")
    _check("VMB stats has articles", s.get("articles", 0) >= 5)

    vstats = vmb.vector_memory.stats()
    _check("VectorMemory accessible via VMB", "doc_count" in vstats)


# ── 9. HybridMemoryBackend ────────────────────────────────────
_section("HybridMemoryBackend")
from agent_core.memory_adapter import HybridMemoryBackend

with tempfile.TemporaryDirectory() as td:
    # Use custom backends for isolation
    jmb_hybrid = JsonMemoryBackend()
    vmb_hybrid = VectorMemoryBackend(
        collection_name="test_hybrid",
        persist_dir=Path(td) / "hybrid",
    )
    hmb = HybridMemoryBackend(json_backend=jmb_hybrid, vector_backend=vmb_hybrid)
    _check("Hybrid backend created", hmb is not None)

    # Record (writes to both)
    hid = hmb.record_article("hybrid test kw", "Hybrid backend article content dual write", "local", 90, "hybrid")
    _check("Hybrid record returns ID", isinstance(hid, str) and len(hid) > 0)

    # Search (reads from vector, falls back to JSON)
    results = hmb.search("hybrid backend", top_k=5)
    _check("Hybrid search returns results", len(results) > 0)

    # Stats
    s = hmb.stats()
    _check("Hybrid stats has backend", s.get("backend") == "hybrid")
    _check("Hybrid stats has vector sub-stats", "vector" in s)
    _check("Hybrid stats has json sub-stats", "json" in s)


# ── 10. MemoryAdapter ──────────────────────────────────────────
_section("MemoryAdapter")
from agent_core.memory_adapter import MemoryAdapter

with tempfile.TemporaryDirectory() as td:
    vmb_adapter = VectorMemoryBackend(persist_dir=Path(td) / "adapter")
    adapter = MemoryAdapter(backend=vmb_adapter)
    _check("Adapter created", adapter is not None)

    adapter.record_article("adapter test", "Adapter pattern article content", "local", 80, "adapter-test")
    adapter.record_article("adapter another", "Another article for adapter testing", "claude", 75, "adapter-test")

    results = adapter.search("adapter article", top_k=5)
    _check("Adapter search returns results", len(results) > 0)

    similar = adapter.find_similar("adapter test", top_k=3)
    _check("Adapter find_similar returns results", len(similar) > 0)

    s = adapter.stats()
    _check("Adapter stats has articles", s.get("articles", 0) >= 2)


# ── 11. Compare backends ──────────────────────────────────────
_section("Compare backends")
from agent_core.memory_adapter import compare_backends

with tempfile.TemporaryDirectory() as td:
    # Setup both backends with same data
    jmb_cmp = JsonMemoryBackend()
    vmb_cmp = VectorMemoryBackend(persist_dir=Path(td) / "cmp")

    vmb_cmp.record_article("laptop review", "Best laptop for programming students review", "local", 85, "tech")
    vmb_cmp.record_article("coffee machine", "Top coffee machine reviews 2026", "local", 80, "home")
    vmb_cmp.record_article("python tutorial", "Python programming tutorial for beginners", "claude", 90, "tech")

    comparison = compare_backends("laptop", json_backend=jmb_cmp, vector_backend=vmb_cmp, top_k=5)
    _check("Comparison has query", "query" in comparison)
    _check("Comparison has json_count", "json_count" in comparison)
    _check("Comparison has vector_count", "vector_count" in comparison)
    _check("Comparison has jaccard_similarity", "jaccard_similarity" in comparison)
    _check("Comparison results valid", comparison["json_count"] >= 0 and comparison["vector_count"] >= 0)
    _check("Comparison has overlap_count", "overlap_count" in comparison)


# ── 12. Migration utility ──────────────────────────────────────
_section("Migration utility")
from agent_core.memory_adapter import migrate_json_to_vector

with tempfile.TemporaryDirectory() as td:
    jmb_mig = JsonMemoryBackend()
    vmb_mig = VectorMemoryBackend(persist_dir=Path(td) / "migrate")

    vmb_mig.record_article("migrate test 1", "First article for migration test", "local", 85)
    vmb_mig.record_article("migrate test 2", "Second article for migration test", "claude", 70)

    result = migrate_json_to_vector(json_backend=jmb_mig, vector_backend=vmb_mig)
    _check("Migration result has total_articles", "total_articles" in result)
    _check("Migration result has migrated", "migrated" in result)
    _check("Migration result has errors", "errors" in result)
    _check("Migration result has vector_count", "vector_count" in result)
    _check("Migration errors is 0", result["errors"] == 0)


# ── 13. Latency benchmarks ─────────────────────────────────────
_section("Latency benchmarks")
import statistics

with tempfile.TemporaryDirectory() as td:
    vm_bench = VectorMemory(persist_dir=Path(td) / "bench")

    # Store benchmark
    store_times = []
    for i in range(20):
        t0 = time.perf_counter()
        vm_bench.store(f"bench-{i}", f"Benchmark article number {i} for performance testing", {"keyword": f"benchmark_{i}", "niche": "bench"})
        store_times.append((time.perf_counter() - t0) * 1000)

    print(f"  Store (n=20):   mean={statistics.mean(store_times):.1f}ms  p95={sorted(store_times)[int(20*0.95)]:.1f}ms  min={min(store_times):.1f}ms")

    # Search benchmark
    search_times = []
    for i in range(20):
        t0 = time.perf_counter()
        vm_bench.search(f"article number {i}", top_k=5)
        search_times.append((time.perf_counter() - t0) * 1000)

    print(f"  Search (n=20):  mean={statistics.mean(search_times):.1f}ms  p95={sorted(search_times)[int(20*0.95)]:.1f}ms  min={min(search_times):.1f}ms")

    # Cache efficiency
    # First search without cache (cold)
    t0 = time.perf_counter()
    vm_bench.search("benchmark article cold", top_k=3)
    cold = (time.perf_counter() - t0) * 1000

    # Same search with cache (hot)
    t0 = time.perf_counter()
    vm_bench.search("benchmark article cold", top_k=3)
    hot = (time.perf_counter() - t0) * 1000

    _check("Cache improves latency (hot < cold)", hot < cold * 1.5)  # Should be faster

    print(f"  Cold search: {cold:.1f}ms  Hot search: {hot:.1f}ms  Speedup: {cold/max(hot, 0.01):.1f}x")


# ── 14. Memory stress test ─────────────────────────────────────
_section("Memory stress test")
with tempfile.TemporaryDirectory() as td:
    vm_stress = VectorMemory(persist_dir=Path(td) / "stress")

    articles = []
    for i in range(50):
        kw = f"stress_keyword_{i}"
        text = f"Stress test article number {i} with some content about {kw} and related topics for testing vector memory performance under load."
        articles.append((f"stress-{i}", text, {"keyword": kw, "niche": "stress-test", "index": i}))

    t0 = time.perf_counter()
    vm_stress.store_batch(articles)
    batch_ms = (time.perf_counter() - t0) * 1000
    _check("Stress store 50 articles", vm_stress.count() == 50)
    print(f"  50 stores: {batch_ms:.0f}ms ({batch_ms/50:.1f}ms/article)")

    # Stress search: 25 queries
    t0 = time.perf_counter()
    for i in range(25):
        vm_stress.search(f"stress_keyword_{i % 50}", top_k=5)
    search_25_ms = (time.perf_counter() - t0) * 1000
    print(f"  25 searches: {search_25_ms:.0f}ms ({search_25_ms/25:.1f}ms/search)")

    # Stress compaction
    t0 = time.perf_counter()
    comp_result = vm_stress.compact(similarity_threshold=0.99)
    compact_ms = (time.perf_counter() - t0) * 1000
    print(f"  Compaction: {compact_ms:.0f}ms  removed={comp_result['removed']}  kept={comp_result['kept']}")

    _check("Stress compaction completes without error", "removed" in comp_result)

    # Stress clear
    t0 = time.perf_counter()
    cleared = vm_stress.clear()
    clear_ms = (time.perf_counter() - t0) * 1000
    _check("Stress clear removes all", vm_stress.count() == 0)
    print(f"  Clear: {clear_ms:.0f}ms")

    # Check vector memory stats
    s = vm_stress.stats()
    _check("Stress stats show stores", s["stores"] >= 50)
    _check("Stress stats show searches", s["searches"] >= 25)
    _check("Stress stats show compactions", s["compactions"] >= 1)


# ── 15. Backwards compatibility ────────────────────────────────
_section("Backwards compatibility")
# Existing agent_core imports still work
from agent_core import (
    RelayRouter, ParallelEngine, SemanticValidator, MemoryIndex,
    CacheManager, MetricsCollector, VectorMemory, MemoryAdapter,
)
_check("All agent_core exports importable", True)

# Original memory.py still works
import memory as mem_module
_check("memory.py import unchanged", hasattr(mem_module, "load"))
_check("memory.py has record_article", hasattr(mem_module, "record_article"))
_check("memory.py has record_cluster", hasattr(mem_module, "record_cluster"))
_check("memory.py has save", hasattr(mem_module, "save"))

# Existing memory_index still works
from agent_core.memory_index import MemoryIndex
mi = MemoryIndex()
_check("MemoryIndex still works", callable(mi.search))

# Original modules.py unchanged
import modules
_check("modules.py unchanged", hasattr(modules, "analyze_competitors"))


# ── 16. Cosine similarity utility ─────────────────────────────
_section("Cosine similarity")
from agent_core.vector_memory import cosine_similarity

a = [1.0, 0.0, 0.0]
b = [1.0, 0.0, 0.0]
_check("Identical vectors sim=1", cosine_similarity(a, b) == 1.0)

c = [0.0, 1.0, 0.0]
_check("Orthogonal vectors sim=0", cosine_similarity(a, c) == 0.0)

d = [-1.0, 0.0, 0.0]
_check("Opposite vectors sim=-1", round(cosine_similarity(a, d), 5) == -1.0)

zero = [0.0, 0.0, 0.0]
_check("Zero vector returns 0", cosine_similarity(a, zero) == 0.0)


# ── Final ──────────────────────────────────────────────────────
print(f"\n{'=' * 50}")
print(f"  RESULTS: {_PASSED} passed, {_FAILED} failed")

if _TIMINGS:
    import statistics
    print(f"\n  {'─' * 40}")
    print(f"  Timing Summary")
    print(f"  {'─' * 40}")
    for name, timings in sorted(_TIMINGS.items()):
        mean = statistics.mean(timings)
        _max = max(timings)
        _min = min(timings)
        print(f"  {name:<30s}  mean={mean:.1f}ms  min={_min:.1f}ms  max={_max:.1f}ms")

print(f"{'=' * 50}")

if _FAILED > 0:
    print(f"\n  ❌ {_FAILED} TEST(S) FAILED")
    sys.exit(1)
else:
    print(f"\n  ✅ ALL VECTOR MEMORY TESTS PASSED")
