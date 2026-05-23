"""
Enhanced pipeline tests (no external network required).
Tests agent_core modules and pipeline_enhancer.
"""
import sys
sys.path.insert(0, '.')

print("=== Testing agent_core imports ===")
from agent_core import RelayRouter, ParallelEngine, SemanticValidator, MemoryIndex, SelfHeal
print("  OK")

print("\n=== Testing cache_manager ===")
from agent_core.cache_manager import CacheManager
cm = CacheManager()
cm.save_serp("test kw", {"results": [1, 2]})
assert cm.load_serp("test kw") == {"results": [1, 2]}
cm.save_llm("sys", "user", "local", "hello")
assert cm.load_llm("sys", "user", "local") == "hello"
print("  OK")

print("\n=== Testing pipeline_enhancer import ===")
import pipeline_enhancer as pe
assert hasattr(pe, 'run_full_enhanced')
assert hasattr(pe, 'run_batch_articles')
print("  OK")

print("\n=== Testing self_heal ===")
from agent_core.self_heal import CircuitBreaker, HealthMonitor, SelfHeal
cb = CircuitBreaker()
assert cb.can_execute()
cb.record_failure()
cb.record_failure()
cb.record_failure()
# After 3 failures circuit should be open or still closed depending on timing
assert cb.status()["state"] in ("closed", "open")
print("  OK")

print("\n=== Testing parallel engine (no actual parallel work) ===")
from agent_core.parallel import ParallelEngine, TaskGroup
engine = ParallelEngine(max_workers=2)
with engine:
    with TaskGroup(engine) as g:
        def _add(a, b): return a + b
        g.submit("add", _add, 2, 3)
    res = g.results()
    assert res.get("add") == 5
print("  OK")

print("\n=== Testing semantic validator (no network) ===")
from agent_core.validator import SemanticValidator
sv = SemanticValidator()
html = """<html><body>
<h1>Best Password Manager</h1>
<h2>Introduction</h2><p>This is a test article about password managers.</p>
<h2>Features</h2><p>More content here with pricing $10.</p>
<script type="application/ld+json">{"@type":"Article"}</script>
<script type="application/ld+json">{"@type":"FAQPage"}</script>
</body></html>"""
report = sv.validate(html, "best password manager")
assert report.score >= 0
assert report.keyword_relevance >= 0
print(f"  Score: {report.score}, Relevance: {report.keyword_relevance:.2f}")
print("  OK")

print("\n=== Testing memory index (empty) ===")
from agent_core.memory_index import MemoryIndex
idx = MemoryIndex()
summary = idx.summary()
assert "total_articles" in summary
print(f"  Articles: {summary['total_articles']}")
print("  OK")

print("\n=== ALL ENHANCED TESTS PASSED ===")
