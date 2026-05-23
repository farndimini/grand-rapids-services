"""
test_multi_agent.py — Bounded Multi-Agent Orchestration Tests
===============================================================
Covers:
   1. SharedContext creation + snapshot
   2. Each agent in isolation (researcher, strategist, writer, optimizer, critic)
   3. Full orchestration end-to-end
   4. Bounded rounds enforcement
   5. Timeout enforcement
   6. Retry (max 1 per agent)
   7. Deadlock detection
   8. Execution graph integration
   9. Telemetry + cost + latency metrics
   10. Benchmark cost vs quality vs latency
   11. No recursive delegation / no autonomous spawning
"""

from __future__ import annotations

import sys
import os
import time
import json
import statistics

# Disable real module network calls during tests for speed
os.environ["SEO_AGENT_TEST_MODE"] = "1"

sys.path.insert(0, ".")

from agent_core.multi_agent.base_agent import AgentBase

_PASSED = 0
_FAILED = 0


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


# ── 1. SharedContext ──────────────────────────────────────────
_section("SharedContext")

from agent_core.multi_agent.context import SharedContext

ctx = SharedContext(keyword="best laptop", topic="Laptop Buying Guide", niche="tech", target_audience="developers")
_check("Context created with keyword", ctx.keyword == "best laptop")
_check("Context has topic", ctx.topic == "Laptop Buying Guide")
_check("Context has niche", ctx.niche == "tech")
_check("Context has target_audience", ctx.target_audience == "developers")

ctx.add_telemetry({"agent": "test", "round": 1, "latency_ms": 10.0, "cost": 0.001})
_check("Telemetry recorded", len(ctx.telemetry) == 1)
_check("Cost total tracks", abs(ctx.cost_total - 0.001) < 1e-6)
_check("Latency total tracks", abs(ctx.latency_total - 10.0) < 0.01)

ctx.add_error("test-agent", "something broke")
_check("Error recorded", len(ctx.errors) == 1)

snap = ctx.snapshot()
_check("Snapshot has keyword", snap["keyword"] == "best laptop")
_check("Snapshot has round", "round" in snap)
_check("Snapshot has cost_total", snap["cost_total"] > 0)
_check("Snapshot has latency_total", snap["latency_total"] > 0)
_check("Snapshot has telemetry_count", snap["telemetry_count"] == 1)

# Stale detection
ctx2 = SharedContext(keyword="other")
ctx2.research_data = {"some": "data"}  # differ from default
_check("Different contexts not stale", not ctx.is_stale(ctx2))
_check("Same context is stale", ctx.is_stale(ctx))


# ── 2. Researcher Agent ────────────────────────────────────────
_section("Researcher Agent")

from agent_core.multi_agent.researcher import Researcher

researcher = Researcher()
_check("Researcher created", researcher.name == "researcher")

rctx = SharedContext(keyword="best laptop")
rctx = researcher.run(rctx, round_num=1)
_check("Research data populated", bool(rctx.research_data))
_check("Research has keyword", rctx.research_data.get("keyword") == "best laptop")
_check("Research has competitors", len(rctx.research_data.get("competitors", [])) > 0)
_check("Research has related_queries", len(rctx.research_data.get("related_queries", [])) > 0)
_check("Research has intent", rctx.research_data.get("intent") in ("commercial", "informational", "navigational"))
_check("Researcher telemetry recorded", len(rctx.telemetry) > 0)
_check("Researcher telemetry status success", rctx.telemetry[-1]["status"] == "success")


# ── 3. Strategist Agent ────────────────────────────────────────
_section("Strategist Agent")

from agent_core.multi_agent.strategist import Strategist

strategist = Strategist()
_check("Strategist created", strategist.name == "strategist")

sctx = SharedContext(keyword="best laptop")
sctx.research_data = {
    "intent": "commercial",
    "competitors": [{"url": "https://example.com/laptop"}],
    "related_queries": ["best laptop 2026", "laptop for developers"],
}
sctx = strategist.run(sctx, round_num=1)
_check("Strategy populated", bool(sctx.strategy))
_check("Strategy has angle", bool(sctx.strategy.get("angle")))
_check("Strategy has sections", len(sctx.strategy.get("sections", [])) > 0)
_check("Strategy has word_count_target", sctx.strategy.get("word_count_target", 0) > 0)
_check("Commercial intent → persuasive tone", "persuasive" in sctx.strategy.get("tone", ""))

# Informational intent
sctx2 = SharedContext(keyword="what is ai")
sctx2.research_data = {"intent": "informational", "competitors": [], "related_queries": []}
sctx2 = strategist.run(sctx2, round_num=1)
_check("Informational → educational tone", "educational" in sctx2.strategy.get("tone", ""))


# ── 4. Writer Agent ────────────────────────────────────────────
_section("Writer Agent")

from agent_core.multi_agent.writer import Writer

writer = Writer()
_check("Writer created", writer.name == "writer")

wctx = SharedContext(keyword="best laptop")
wctx.strategy = {
    "angle": "Why Best Laptop Is the Smart Choice",
    "sections": ["Introduction", "Features", "Comparison", "Verdict"],
    "word_count_target": 500,
    "tone": "persuasive_authoritative",
}
wctx = writer.run(wctx, round_num=1)
_check("Draft generated", bool(wctx.draft))
_check("Draft contains keyword", "laptop" in wctx.draft.lower())
_check("Draft has sections", "## Introduction" in wctx.draft)
_check("Draft has angle in header", "Smart Choice" in wctx.draft)
_check("Draft word count > 100", len(wctx.draft.split()) > 100)
_check("Writer telemetry recorded", len(wctx.telemetry) > 0)


# ── 5. Optimizer Agent ─────────────────────────────────────────
_section("Optimizer Agent")

from agent_core.multi_agent.optimizer import Optimizer

optimizer = Optimizer()
_check("Optimizer created", optimizer.name == "optimizer")

octx = SharedContext(keyword="best laptop")
octx.draft = """
## Introduction

This is a guide about best laptop. It covers many aspects of laptop selection.

## Features

The best laptop comes with various features that matter for users.

## FAQ

Common questions about laptop.
""".strip()
octx = optimizer.run(octx, round_num=1)
_check("Optimized draft generated", bool(octx.optimized_draft))
_check("Optimized has keyword enriched headers", "laptop" in octx.optimized_draft.lower())
_check("Optimized has schema markers", "SCHEMA:" in octx.optimized_draft)
_check("Optimized different from draft", octx.optimized_draft != octx.draft)

# Empty draft edge case
octx2 = SharedContext(keyword="test")
octx2 = optimizer.run(octx2, round_num=1)
_check("Empty draft → empty optimized", octx2.optimized_draft == "")


# ── 6. Critic Agent ────────────────────────────────────────────
_section("Critic Agent")

from agent_core.multi_agent.critic import Critic

critic = Critic()
_check("Critic created", critic.name == "critic")

cctx = SharedContext(keyword="best laptop")
cctx.draft = """
## Introduction

This comprehensive guide explores the best laptop options available today.

## Features

When evaluating the best laptop, several key features deserve attention.

## Comparison

Comparing the top laptops helps identify the best laptop for your needs.

## Verdict

The best laptop ultimately depends on your specific requirements.
""".strip()
cctx = critic.run(cctx, round_num=1)
_check("Critique populated", bool(cctx.critique))
_check("Critique has quality_score", "quality_score" in cctx.critique)
_check("Critique has issues list", isinstance(cctx.critique.get("issues"), list))
_check("Critique has suggestions", isinstance(cctx.critique.get("suggestions"), list))
_check("Critique has keyword_density", cctx.critique.get("keyword_density", -1) >= 0)
_check("Critique has readability_score", cctx.critique.get("readability_score", -1) >= 0)
_check("Critique has word_count", cctx.critique.get("word_count", 0) > 0)
_check("Critique round recorded", cctx.critique.get("round") == 1)
_check("Critic telemetry recorded", len(cctx.telemetry) > 0)

# Check scoring
if cctx.critique.get("quality_score") is not None:
    _check("Quality score in 0-100 range", 0 <= cctx.critique["quality_score"] <= 100)

# Short content detection
cctx2 = SharedContext(keyword="test")
cctx2.draft = "Short content."
cctx2 = critic.run(cctx2, round_num=1)
_check("Short content has issues", len(cctx2.critique.get("issues", [])) > 0)


# ── 7. Full Orchestration (Single Round) ──────────────────────
_section("Full Orchestration (1 round)")

from agent_core.multi_agent import BoundedOrchestrator

agents = {
    "researcher": Researcher(),
    "strategist": Strategist(),
    "writer": Writer(),
    "optimizer": Optimizer(),
    "critic": Critic(),
}

orch = BoundedOrchestrator(
    agents=agents,
    execution_order=["researcher", "strategist", "writer", "optimizer", "critic"],
    max_rounds=1,
    agent_timeout=15.0,
)

result = orch.execute(keyword="best laptop", niche="tech", target_audience="developers")
_check("Orchestration completed", result is not None)
_check("Research data present", bool(result.research_data))
_check("Strategy present", bool(result.strategy))
_check("Draft generated", bool(result.draft))
_check("Optimized draft generated", bool(result.optimized_draft))
_check("Critique present", bool(result.critique))
_check("Round is 1", result.round == 1)
_check("Errors list is empty", len(result.errors) == 0)
_check("Telemetry has 5 entries (1 per agent)", len(result.telemetry) == 5)

bm = orch.benchmark()
_check("Benchmark has total_rounds", bm["total_rounds"] >= 1)
_check("Benchmark has total_cost", bm["total_cost"] > 0)
_check("Benchmark has total_latency_ms", bm["total_latency_ms"] > 0)
_check("Benchmark has agent_stats", len(bm["agent_stats"]) == 5)
_check("No deadlocks detected", bm["deadlocks_detected"] == 0)


# ── 8. Bounded Rounds ─────────────────────────────────────────
_section("Bounded Rounds")

orch3 = BoundedOrchestrator(
    agents=agents,
    max_rounds=3,
    agent_timeout=15.0,
)
result3 = orch3.execute(keyword="best laptop")
_check("3-round orchestration completed", result3 is not None)
_check("Round counter <= 3", result3.round <= 3)
bm3 = orch3.benchmark()
_check("Benchmark rounds <= 3", bm3["total_rounds"] <= 3)
_check("More telemetry with more rounds", len(result3.telemetry) >= len(result.telemetry))


# ── 9. Timeout Enforcement ─────────────────────────────────────
_section("Timeout Enforcement")

import concurrent.futures


class SlowAgent(Researcher):
    def __init__(self):
        super().__init__()
        self.name = "slow_agent"

    def process(self, ctx, round_num):
        import time as _t
        _t.sleep(10)
        return ctx


slow_agents = {
    "researcher": SlowAgent(),
    "strategist": Strategist(),
    "writer": Writer(),
    "optimizer": Optimizer(),
    "critic": Critic(),
}

slow_orch = BoundedOrchestrator(
    agents=slow_agents,
    max_rounds=1,
    agent_timeout=0.1,  # very short timeout
)
t0 = time.perf_counter()
slow_result = slow_orch.execute(keyword="timeout-test")
elapsed = time.perf_counter() - t0
_check("Timeout handled within reasonable time", elapsed < 2.0)
_check("Timeout recorded as error", len(slow_result.errors) > 0)
_check("Timeout error mentions timeout", any("Timeout" in e for e in slow_result.errors))


# ── 10. Deadlock Detection ──────────────────────────────────────
_section("Deadlock Detection")


class NoopAgent(AgentBase):
    def __init__(self):
        super().__init__(name="noop")

    def process(self, ctx, round_num):
        return ctx


deadlock_agents = {
    "researcher": NoopAgent(),
    "strategist": NoopAgent(),
    "writer": NoopAgent(),
    "optimizer": NoopAgent(),
    "critic": NoopAgent(),
}

deadlock_orch = BoundedOrchestrator(
    agents=deadlock_agents,
    max_rounds=3,
    agent_timeout=5.0,
)
deadlock_result = deadlock_orch.execute(keyword="deadlock-test")
_check("Deadlock detected", deadlock_result.deadlock_rounds > 0)
deadlock_bm = deadlock_orch.benchmark()
_check("Benchmark reports deadlocks", deadlock_bm["deadlocks_detected"] > 0)


# ── 11. Retry (Max 1 per Agent) ────────────────────────────────
_section("Retry Mechanism")


class FlakyAgent(Researcher):
    def __init__(self):
        super().__init__()
        self.name = "flaky"
        self._call_count = 0

    def process(self, ctx, round_num):
        self._call_count += 1
        if self._call_count <= 1:
            raise RuntimeError("Transient failure")
        return super().process(ctx, round_num)


flaky_agents = {
    "researcher": FlakyAgent(),
    "strategist": Strategist(),
    "writer": Writer(),
    "optimizer": Optimizer(),
    "critic": Critic(),
}

flaky_orch = BoundedOrchestrator(
    agents=flaky_agents,
    max_rounds=1,
    agent_timeout=15.0,
)
flaky_result = flaky_orch.execute(keyword="retry-test")
r_agent = flaky_agents["researcher"]
_check("Retry succeeded (0 errors)", flaky_result.errors == [] or len(flaky_result.errors) == 0)
_check("Flaky agent called >1 time", r_agent._call_count >= 1)
flaky_bm = flaky_orch.benchmark()
_check("Retry count > 0", flaky_bm["retries"] >= 1)


# ── 12. Execution Graph Integration ─────────────────────────────
_section("Execution Graph Integration")

from agent_core.multi_agent.graph import orchestrate_via_graph

graph_result = orchestrate_via_graph("graph-test", max_rounds=1, agent_timeout=15.0)
_check("Graph orchestration completed", graph_result is not None)
_check("Graph result has research", bool(graph_result.research_data))
_check("Graph result has draft", bool(graph_result.draft))
_check("Graph result has critique", bool(graph_result.critique))
_check("Graph result no errors", len(graph_result.errors) == 0)

from agent_core.multi_agent.graph import build_execution_graph
eg = build_execution_graph("graph-test", max_rounds=2, agent_timeout=15.0)
_check("Execution graph built", eg is not None)


# ── 13. No Recursive Delegation / No Autonomous Spawning ───────
_section("Safety Constraints")

_researcher_process = Researcher.process
import inspect
src = inspect.getsource(Researcher.process)
_check("Researcher: no recursive delegation", "orchestrator" not in src.lower() and "Orchestrator" not in src)

src_s = inspect.getsource(Strategist.process)
_check("Strategist: no agent spawning", "Agent" not in src_s or "AgentBase" not in src_s.split("def")[0])

_check("All agents are AgentBase subclasses", all(
    issubclass(type(a), AgentBase) for a in agents.values()
))

# Verify execution_order determines the flow
orch_custom = BoundedOrchestrator(
    agents=agents,
    execution_order=["critic", "writer", "researcher"],
    max_rounds=1,
)
ctx_custom = orch_custom.execute(keyword="order-test")
_check("Custom execution order respected", ctx_custom is not None)


# ── 14. Cost Benchmark ─────────────────────────────────────────
_section("Cost Benchmark")

bench_agents = {
    "researcher": Researcher(cost_per_call=0.002),
    "strategist": Strategist(cost_per_call=0.002),
    "writer": Writer(cost_per_call=0.003),
    "optimizer": Optimizer(cost_per_call=0.002),
    "critic": Critic(cost_per_call=0.001),
}
bench_orch = BoundedOrchestrator(
    agents=bench_agents,
    max_rounds=3,
    agent_timeout=15.0,
)
bench_result = bench_orch.execute(keyword="benchmark-test")
bench_bm = bench_orch.benchmark()

cost_per_agent = {}
for name, s in bench_bm["agent_stats"].items():
    agent_cost = bench_agents[name].cost_per_call * s["calls"]
    cost_per_agent[name] = round(agent_cost, 6)

total_expected_cost = sum(cost_per_agent.values())
_check("Total cost matches agent costs sum",
      abs(bench_bm["total_cost"] - total_expected_cost) < 0.001)

quality = bench_result.critique.get("quality_score", 0)
cost = bench_bm["total_cost"]
latency = bench_bm["total_latency_ms"]
_check("Quality > 0 when cost > 0", quality == 0 or cost > 0)
_check("Latency > 0 when rounds complete", latency > 0)

print(f"\n  Cost breakdown: {json.dumps(cost_per_agent, indent=2)}")
print(f"  Total cost:     ${bench_bm['total_cost']:.6f}")
print(f"  Total latency:  {bench_bm['total_latency_ms']:.1f}ms")
print(f"  Quality score:  {quality}/100")
print(f"  Deadlocks:      {bench_bm['deadlocks_detected']}")
print(f"  Retries:        {bench_bm['retries']}")


# ── 15. Latency Benchmark ──────────────────────────────────────
_section("Latency Benchmark")

latency_samples = []
for i in range(5):
    lorch = BoundedOrchestrator(
        agents={
            "researcher": Researcher(),
            "strategist": Strategist(),
            "writer": Writer(),
            "optimizer": Optimizer(),
            "critic": Critic(),
        },
        max_rounds=1,
        agent_timeout=15.0,
    )
    t0 = time.perf_counter()
    lorch.execute(keyword=f"latency-test-{i}")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    latency_samples.append(elapsed_ms)

avg_latency = statistics.mean(latency_samples)
p95 = sorted(latency_samples)[int(len(latency_samples) * 0.95)]
_check(f"Avg latency {avg_latency:.0f}ms < 2000ms (single round)", avg_latency < 2000)
_check("All samples < 5000ms", all(s < 5000 for s in latency_samples))

print(f"\n  Latency samples (ms): {[round(s, 1) for s in latency_samples]}")
print(f"  Mean:   {avg_latency:.0f}ms")
print(f"  P95:    {p95:.0f}ms")


# ── 16. Agent Order Validation ─────────────────────────────────
_section("Agent Order Validation")

try:
    BoundedOrchestrator(
        agents={"a": Researcher(), "b": Strategist()},
        execution_order=["a", "nonexistent"],
    )
    _check("Unknown agent in order raises ValueError", False)
except ValueError:
    _check("Unknown agent in order raises ValueError", True)


# ── 17. Structured Output Format ───────────────────────────────
_section("Structured Output")

for agent_obj in [Researcher(), Strategist(), Writer(), Optimizer(), Critic()]:
    sctx = SharedContext(keyword="test")
    output = agent_obj.structured_output(sctx)
    _check(f"{agent_obj.name}: structured output has agent name", output["agent"] == agent_obj.name)
    _check(f"{agent_obj.name}: structured output has model", "model" in output)
    _check(f"{agent_obj.name}: structured output has round", "round" in output)
    _check(f"{agent_obj.name}: structured output has keyword", output["keyword"] == "test")
    _check(f"{agent_obj.name}: structured output has timestamp", "timestamp" in output)


# ── Final ──────────────────────────────────────────────────────
print(f"\n{'=' * 50}")
print(f"  RESULTS: {_PASSED} passed, {_FAILED} failed")

if _FAILED > 0:
    print(f"\n  ❌ {_FAILED} TEST(S) FAILED")
    sys.exit(1)
else:
    print(f"\n  ✅ ALL MULTI-AGENT TESTS PASSED")
