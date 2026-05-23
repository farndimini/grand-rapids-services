"""
test_planner_rl.py — Tests for Phase 4 (Planner) and Phase 5 (RL).
Run: python test_planner_rl.py
"""

import sys
import tempfile

sys.path.insert(0, '.')

print("=== Testing State Machine ===")
from agent_core.state_machine import PipelineStateMachine, State

sm = PipelineStateMachine("pipe-001", keyword="best CRM")
assert sm.state == State.PENDING
assert sm.transition(State.RUNNING)
assert sm.state == State.RUNNING
assert sm.transition(State.VALIDATING)
assert not sm.transition(State.RETRYING)  # illegal: VALIDATING cannot go to RETRYING
assert sm.transition(State.REWRITING)
assert sm.transition(State.VALIDATING)
assert sm.transition(State.COMPLETE)
assert sm.is_terminal
summary = sm.summary()
assert summary["transitions"] >= 5
print(f"  StateMachine: {summary['transitions']} transitions, terminal={summary['terminal']}")

# Resume from checkpoint
sm2 = PipelineStateMachine.resume("pipe-001")
assert sm2 is not None
assert sm2.state == State.COMPLETE
print("  Checkpoint resume OK")

print("\n=== Testing Execution Graph ===")
import asyncio
from agent_core.execution_graph import ExecutionGraph

async def test_exec_graph():
    g = ExecutionGraph("test-graph")

    async def step_a():
        await asyncio.sleep(0.01)
        return "A"

    async def step_b():
        await asyncio.sleep(0.01)
        return "B"

    async def step_c():
        await asyncio.sleep(0.01)
        return "C(A,B)"

    g.add_node("a", step_a)
    g.add_node("b", step_b)
    g.add_node("c", step_c, depends_on=["a", "b"])
    results = await g.execute()
    assert results["a"] == "A"
    assert results["b"] == "B"
    assert results["c"] == "C(A,B)"
    trace = g.trace()
    assert len(trace) == 3
    print("  ExecutionGraph OK")

asyncio.run(test_exec_graph())

print("\n=== Testing Agent Planner ===")
from agent_core.planner import AgentPlanner, Policy

planner = AgentPlanner(policy=Policy(min_quality_score=70, max_rewrite_attempts=1))
plan = planner.create_plan(keyword="best CRM", niche="tech", model="gpt-4o", serp_difficulty="high")
assert len(plan.steps) >= 8
assert plan.adaptive_params["target_length"] == 2500
assert any(s.name == "validate_article" for s in plan.steps)
assert any(s.name == "rewrite_weak" for s in plan.steps)
print(f"  AgentPlanner: {len(plan.steps)} steps, target_len={plan.adaptive_params['target_length']}")

viz = planner.visualize_text(plan)
assert "FETCH_SERP" in viz
print("  Planner visualization OK")

# Replan (validate_article has fallback_step=rewrite_weak)
replan = planner.replan_on_failure(plan, "validate_article", "score_too_low")
assert len(replan.steps) > len(plan.steps)
print("  Replan OK")

print("\n=== Testing RL Reward Engine ===")
from agent_core.rl_optimizer import RewardEngine, StrategyEvolution, compute_reward

engine = RewardEngine()
r = engine.compute(quality=85, ranking_pred=40, cost_usd=0.005, latency_ms=2000, rewrites=0, serp_alignment=0.7, word_count=2000)
assert -1.0 <= r.total_reward <= 1.0
assert "quality" in r.components
print(f"  RewardEngine: {r.total_reward:.3f} — {r.explanation}")

r2 = engine.compute(quality=40, ranking_pred=10, cost_usd=0.08, latency_ms=45000, rewrites=2, serp_alignment=0.2, word_count=800)
assert r2.total_reward < 0
print(f"  RewardEngine (bad): {r2.total_reward:.3f}")

print("\n=== Testing Strategy Evolution ===")
with tempfile.TemporaryDirectory() as td:
    evo = StrategyEvolution(data_dir=td)
    evo.record_outcome("opener", "stat_open", 0.8)
    evo.record_outcome("opener", "stat_open", 0.9)
    evo.record_outcome("opener", "question_open", 0.4)
    recs = evo.recommend("opener", top_n=2)
    assert len(recs) > 0
    assert recs[0].value == "stat_open"
    print(f"  StrategyEvolution: best opener avg_reward={recs[0].avg_reward:.2f}")

    mut = evo.get_mutation("opener", "The best CRM in 2026")
    assert mut != "The best CRM in 2026"
    print(f"  Mutation: '{mut}'")

print("\n=== ALL PLANNER & RL TESTS PASSED ===")
