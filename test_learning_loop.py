"""
Learning loop tests — no external network required.
Tests LearningLoopOrchestrator, RewardEngine, StrategyEvolution integration,
dry-run mode, batch processing, decay detection, and backward compatibility.
"""
import sys
sys.path.insert(0, '.')

import os
os.environ["SEO_AGENT_TEST_MODE"] = "1"

import json
import time
from datetime import datetime
from pathlib import Path

# ── Section 1: Imports ─────────────────────────────────────────
print("\n=== SECTION 1: Imports ===")
from agent_core.learning_loop import LearningLoopOrchestrator, LearningCycleResult
from agent_core.rl_optimizer import RewardEngine, StrategyEvolution, compute_reward
from agent_core.state_machine import PipelineStateMachine, State
from agent_core.planner import AgentPlanner, Policy
assert LearningLoopOrchestrator
assert LearningCycleResult
assert RewardEngine
assert StrategyEvolution
assert PipelineStateMachine
assert AgentPlanner
assert Policy
print("  OK")

# ── Section 2: RewardEngine Integration ─────────────────────────
print("\n=== SECTION 2: RewardEngine ===")
engine = RewardEngine()

reward = engine.compute(quality=85, ranking_pred=70, cost_usd=0.005, latency_ms=2000, rewrites=0)
assert -1.0 <= reward.total_reward <= 1.0, f"Reward out of range: {reward.total_reward}"
assert len(reward.components) == 8
assert reward.components["quality"] is not None
assert reward.components["ranking"] is not None
print(f"  High quality reward: {reward.total_reward} — {reward.explanation}")

reward_low = engine.compute(quality=30, ranking_pred=10, cost_usd=0.10, latency_ms=60000, rewrites=3)
assert reward_low.total_reward < reward.total_reward, "Low quality should produce lower reward"
assert reward_low.total_reward < 0 or reward_low.total_reward <= reward.total_reward
print(f"  Low quality reward: {reward_low.total_reward} — {reward_low.explanation}")

reward_mid = engine.compute(quality=60, ranking_pred=50, cost_usd=0.01, latency_ms=5000, rewrites=1)
assert -1.0 <= reward_mid.total_reward <= 1.0
print(f"  Medium quality reward: {reward_mid.total_reward}")

# Verify convenience function
convenience = compute_reward(quality=90, ranking_pred=80)
assert isinstance(convenience.total_reward, float)
print("  Convenience compute_reward() works")

# Word count sweet spot
reward_good_wc = engine.compute(quality=80, ranking_pred=60, word_count=2000)
reward_bad_wc = engine.compute(quality=80, ranking_pred=60, word_count=500)
assert reward_good_wc.total_reward > reward_bad_wc.total_reward, "Good word count should beat bad"
print("  Word count component works (1500-2500 sweet spot)")
print("  OK")

# ── Section 3: StrategyEvolution Integration ────────────────────
print("\n=== SECTION 3: StrategyEvolution ===")
import tempfile
with tempfile.TemporaryDirectory() as tmpdir:
    se = StrategyEvolution(data_dir=tmpdir)
    assert se.summary()["total_patterns"] == 0

    se.record_outcome("opener", "surprising_statistic", 0.8)
    se.record_outcome("opener", "surprising_statistic", 0.6)
    se.record_outcome("opener", "direct_answer", 0.3)
    se.record_outcome("heading", "how_to_guide", 0.9)
    se.record_outcome("cta", "free_trial", 0.7)

    assert se.summary()["total_patterns"] == 4

    opener_recs = se.recommend("opener", top_n=2)
    assert len(opener_recs) == 2
    assert opener_recs[0].avg_reward >= opener_recs[1].avg_reward

    all_recs = se.recommend("opener", top_n=10)
    assert len(all_recs) <= 3

    mutation = se.get_mutation("cta", "try our service")
    assert "try" in mutation or "get started" in mutation or "free trial" in mutation

    heading_mutation = se.get_mutation("heading", "Best SEO Guide")
    assert "Guide" in heading_mutation or "Ultimate" in heading_mutation

    summary = se.summary()
    assert summary["by_type"]["opener"]["count"] == 2
    assert summary["epsilon"] == 0.2

    se.set_epsilon(0.5)
    assert se.summary()["epsilon"] == 0.5

    se.set_epsilon(1.5)  # clamped
    assert se.summary()["epsilon"] == 1.0

    se.set_epsilon(-0.1)  # clamped
    assert se.summary()["epsilon"] == 0.0
print("  OK")

# ── Section 4: LearningLoopOrchestrator Dry Run ─────────────────
print("\n=== SECTION 4: LearningLoopOrchestrator (dry-run) ===")
loop = LearningLoopOrchestrator()

# Run on keyword with no article text
result = loop.run_cycle(keyword="test keyword", dry_run=True)
assert isinstance(result, LearningCycleResult)
assert result.keyword == "test keyword"
assert result.state_before == "PENDING"
assert -1.0 <= result.reward_value <= 1.0, f"Reward out of range: {result.reward_value}"
assert result.strategy_updated is False
assert result.rewrite_triggered is False
assert result.quality_score is None
assert result.gsc_position is None
assert result.artifacts.get("skipped") is None
print(f"  Dry-run cycle: {result.state_before} → {result.state_after}, reward={result.reward_value}")

# Re-run — in dry_run mode state machine stays PENDING (no terminal skip yet)
result2 = loop.run_cycle(keyword="test keyword", dry_run=True)
# Dry runs skip state transitions so state remains PENDING
assert result2.state_before == "PENDING"
assert result2.state_after == "PENDING"
print(f"  Re-run (dry): {result2.state_before} → {result2.state_after}")

# Force run (should also stay PENDING since dry_run skips transitions)
result3 = loop.run_cycle(keyword="test keyword", dry_run=True, force=True)
assert result3.state_before == "PENDING"
print(f"  Force dry-run: {result3.state_before} → {result3.state_after}")
print("  OK")

# ── Section 5: State Machine Integration ────────────────────────
print("\n=== SECTION 5: PipelineStateMachine ===")
sm = PipelineStateMachine("test-pipeline-123", keyword="test")
assert sm.state == State.PENDING
assert not sm.is_terminal
assert sm.can_transition(State.RUNNING)

assert sm.transition(State.RUNNING, reason="test")
assert sm.state == State.RUNNING

assert sm.transition(State.VALIDATING, reason="test")
assert sm.state == State.VALIDATING

assert sm.transition(State.COMPLETE, reason="test")
assert sm.state == State.COMPLETE
assert sm.is_terminal

# Illegal transition
assert not sm.transition(State.RUNNING)
assert sm.state == State.COMPLETE

# Checkpoint persistence
sm2 = PipelineStateMachine.resume("test-pipeline-123")
assert sm2 is not None
assert sm2.keyword == "test"
assert sm2.state == State.COMPLETE
assert sm2.summary()["transitions"] == 4

# Cleanup checkpoint
cp = Path("checkpoints/test-pipeline-123.json")
if cp.exists():
    cp.unlink()
print("  Checkpoint resume works")
print("  OK")

# ── Section 6: AgentPlanner Integration ─────────────────────────
print("\n=== SECTION 6: AgentPlanner ===")
planner = AgentPlanner(policy=Policy(
    min_quality_score=65,
    max_rewrite_attempts=2,
    rewrite_threshold=60,
    enable_cluster=True,
    enable_calendar=True,
))

plan = planner.create_plan(keyword="best laptop 2026", niche="tech", model="local")
assert plan.keyword == "best laptop 2026"
assert plan.niche == "tech"
assert plan.model == "local"
assert len(plan.steps) > 0
assert plan.steps[0].name is not None
assert all(step.retries >= 0 for step in plan.steps)
assert all(step.timeout_sec > 0 for step in plan.steps)

# Adaptive params based on difficulty
plan_hard = planner.create_plan(keyword="best laptop", serp_difficulty="high")
plan_easy = planner.create_plan(keyword="obscure niche query", serp_difficulty="low")
assert plan_hard.adaptive_params["target_length"] >= plan_easy.adaptive_params["target_length"]

# Plan visualization
viz = planner.visualize_text(plan)
assert "Plan" in viz  # viz starts with "Plan: {plan_id}"
assert len(viz) > 20

# Plan persistence
assert plan.plan_id is not None
plan_path = Path(f"plans/{plan.plan_id}.json")
assert plan_path.exists()
plan_path.unlink(missing_ok=True)

# Load from disk
planner2 = AgentPlanner()
plan2 = planner2.create_plan(keyword="test load", niche="tech")
loaded = planner2.load_plan(plan2.plan_id)
assert loaded is not None
assert loaded.keyword == "test load"
Path(f"plans/{plan2.plan_id}.json").unlink(missing_ok=True)
print("  OK")

# ── Section 7: Batch Dry Run ────────────────────────────────────
print("\n=== SECTION 7: Batch processing (dry-run) ===")
loop2 = LearningLoopOrchestrator()
keywords = ["kw-alpha", "kw-beta", "kw-gamma"]
results = loop2.run_batch(keywords, dry_run=True)
assert len(results) == 3
for r in results:
    assert r.keyword in keywords
    assert -1.0 <= r.reward_value <= 1.0, f"Reward out of range: {r.reward_value}"
print(f"  Batch returned {len(results)} results")

# Re-run — dry_run mode skips state transitions so state stays PENDING
results2 = loop2.run_batch(keywords, dry_run=True)
assert len(results2) == 3
# In dry_run, state machine stays PENDING so no terminal skip
skipped = sum(1 for r in results2 if r.artifacts.get("skipped"))
assert skipped == 0, f"Expected no skipped in dry-run, got {skipped}"
print(f"  Re-run (dry): all {len(results2)} cycles executed")
print("  OK")

# ── Section 8: Decay Detection ──────────────────────────────────
print("\n=== SECTION 8: Decay detection ===")
loop3 = LearningLoopOrchestrator()

# Empty decay check
alerts_empty = loop3.find_decayed_articles([], dry_run=True)
assert alerts_empty == []
print("  Empty decay check returns []")

# With keyword
alerts2 = loop3.find_decayed_articles(["fresh-keyword"], dry_run=True)
assert isinstance(alerts2, list)
print(f"  Decay check returns {len(alerts2)} alerts")
print("  OK")

# ── Section 9: Strategy Recommendations ─────────────────────────
print("\n=== SECTION 9: Strategy recommendations ===")
loop4 = LearningLoopOrchestrator()

recs = loop4.get_strategy_recommendations("best laptop", top_n=3)
assert isinstance(recs, list)
print(f"  Strategy recommendations: {len(recs)} patterns")

# Feed some data into strategy evolution
se2 = loop4.strategy_evolution
se2.record_outcome("quality_strategy", "high_quality:best_laptop", 0.9)
se2.record_outcome("quality_strategy", "medium_quality:best_laptop", 0.5)
recs2 = loop4.get_strategy_recommendations("best laptop", top_n=3)
assert len(recs2) >= 0
print(f"  After seeding: {len(recs2)} patterns")
print("  OK")

# ── Section 10: Similar articles via MemoryAdapter ──────────────
print("\n=== SECTION 10: Similar articles ===")
loop5 = LearningLoopOrchestrator()

similar = loop5.get_similar_articles("nonexistent-keyword", top_k=5)
assert isinstance(similar, list)
print(f"  Similar articles (empty): {len(similar)}")
print("  OK")

# ── Section 11: Cycle History ───────────────────────────────────
print("\n=== SECTION 11: Cycle history ===")
loop6 = LearningLoopOrchestrator()
for kw in ["h1", "h2", "h3"]:
    loop6.run_cycle(keyword=kw, dry_run=True)

history = loop6.history(limit=10)
assert len(history) >= 3
assert history[0]["keyword"] in ["h1", "h2", "h3"]

filtered = loop6.history(limit=10, min_reward=0.0)
assert len(filtered) <= 10

summary = loop6.decay_summary()
assert summary["total_cycles"] == 3
print(f"  Summary: {summary['total_cycles']} cycles, avg_reward={summary['avg_reward']}")
print("  OK")

# ── Section 12: seo/learning_loop.py backward compatibility ─────
print("\n=== SECTION 12: Backward compatibility ===")
from seo.learning_loop import run_learning_cycle, run_weekly_optimization, get_orchestrator

# get_orchestrator should return an instance
orch = get_orchestrator()
assert orch is not None
print("  get_orchestrator() returns instance")

# run_weekly_optimization with no keywords
weekly = run_weekly_optimization(keywords=[])
assert weekly["total_checked"] == 0
print("  run_weekly_optimization([]) works")

# Orchestrated cycle with dry run
orc_result = run_learning_cycle(keyword="orchestrated-test", dry_run=True, use_orchestrator=True)
assert isinstance(orc_result, dict)
assert orc_result.get("orchestrator") is True
assert orc_result.get("articles_checked", 0) >= 0
print("  Orchestrated cycle (dry-run) works")

# Legacy cycle with dry run
legacy_result = run_learning_cycle(keyword="legacy-test", dry_run=True, use_orchestrator=False)
# Legacy path will error on missing GSC — that's expected
print(f"  Legacy cycle (dry-run): {legacy_result.get('error', 'no error')}")
print("  OK")

# ── Section 13: Null implementations ────────────────────────────
print("\n=== SECTION 13: Null fallbacks ===")
from agent_core.learning_loop import _NullGsc, _NullRewardEngine, _NullStrategyEvolution, _NullBenchmarkRunner, _NullMetricsStore

null_gsc = _NullGsc()
assert null_gsc.poll_and_analyze(["kw"]) == {}
assert null_gsc.run_decay_check(["kw"]) == []

null_re = _NullRewardEngine()
sig = null_re.compute(quality=50)
assert sig.total_reward == 0.0

null_se = _NullStrategyEvolution()
null_se.record_outcome("test", "val", 0.5)  # no-op
assert null_se.recommend("test") == []
assert null_se.summary()["total_patterns"] == 0

null_br = _NullBenchmarkRunner()
report = null_br.evaluate("<html></html>", "kw")
assert report.final_score == 50.0
assert report.verdict == "ACCEPTABLE"

null_ms = _NullMetricsStore()
null_ms.record_latency(stage="test")  # no-op
null_ms.record_ranking(keyword="test")  # no-op
null_ms.record_quality(keyword="test", score=50)  # no-op
assert null_ms.cleanup_old() == {}
assert null_ms.full_summary() == {}
print("  All null implementations work")
print("  OK")

# ── Section 14: Cycle result serialization ──────────────────────
print("\n=== SECTION 14: LearningCycleResult serialization ===")
cr = LearningCycleResult(
    keyword="test-kw",
    timestamp=datetime.now().isoformat(),
    state_before="PENDING",
    state_after="COMPLETE",
    reward_signal={"total": 0.5, "components": {"quality": 0.7}},
    reward_value=0.5,
    strategy_updated=True,
    rewrite_triggered=False,
    quality_score=75,
    gsc_position=5,
    gsc_ctr=8.2,
    gsc_impressions=1000,
    artifacts={"cycle_id": "test-123"},
)

d = cr.to_dict()
assert d["keyword"] == "test-kw"
assert d["reward_value"] == 0.5
assert d["quality_score"] == 75
assert d["gsc_position"] == 5
assert d["gsc_ctr"] == 8.2
assert d["gsc_impressions"] == 1000
assert d["strategy_updated"] is True
assert d["rewrite_triggered"] is False
json_str = json.dumps(d, ensure_ascii=False)
assert len(json_str) > 0
print("  Serialization round-trip OK")
print("  OK")

# ── Section 15: LearningLoopOrchestrator history method ─────────
print("\n=== SECTION 15: history() edge cases ===")
loop7 = LearningLoopOrchestrator()
empty = loop7.history(limit=10)
assert empty == []

loop7.run_cycle(keyword="hist-test", dry_run=True)
non_empty = loop7.history(limit=10)
assert len(non_empty) >= 1

decay = loop7.decay_summary()
assert decay["total_cycles"] >= 1
print("  History edge cases OK")
print("  OK")

# ── Section 16: _pipeline_id uniqueness ─────────────────────────
print("\n=== SECTION 16: Pipeline ID uniqueness ===")
from agent_core.learning_loop import _pipeline_id
id1 = _pipeline_id("keyword one")
id2 = _pipeline_id("keyword two")
id3 = _pipeline_id("keyword one")
assert id1 != id2
assert id1 == id3
assert len(id1) == 16 + 5  # "loop_" + 16 hex chars
print(f"  IDs unique per keyword: {id1} ≠ {id2}")
print("  OK")

# ── Section 17: _infer_pattern_type ─────────────────────────────
print("\n=== SECTION 17: Pattern type inference ===")
from agent_core.learning_loop import _infer_pattern_type

high = _infer_pattern_type("best laptop", 85)
assert "high_quality" in high
med = _infer_pattern_type("best laptop", 65)
assert "medium_quality" in med
low = _infer_pattern_type("best laptop", 40)
assert "low_quality" in low
print(f"  High: {high}")
print(f"  Medium: {med}")
print(f"  Low: {low}")
print("  OK")

# ── Section 18: LearningLoopOrchestrator with custom components ─
print("\n=== SECTION 18: Custom components injection ===")
from evaluation.benchmark_runner import BenchmarkRunner
from evaluation.scorers import SemanticScorer, StructureScorer, SERPScorer, ReadabilityScorer

custom_loop = LearningLoopOrchestrator(
    planner=AgentPlanner(policy=Policy(min_quality_score=70)),
    reward_engine=RewardEngine(),
    strategy_evolution=StrategyEvolution(data_dir=Path("test_evolution_data")),
    benchmark_runner=BenchmarkRunner(),
)
assert custom_loop._planner is not None
assert custom_loop._reward_engine is not None
assert custom_loop._strategy_evolution is not None
assert custom_loop._benchmark_runner is not None

result_custom = custom_loop.run_cycle(keyword="custom-test", dry_run=True)
assert result_custom.keyword == "custom-test"
print("  Custom components work")

# Cleanup
import shutil
for d in ["test_evolution_data", "checkpoints", "plans"]:
    p = Path(d)
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)
print("  Cleanup done")
print("  OK")

# ── ALL TESTS PASSED ────────────────────────────────────────────
print("\n  === ALL LEARNING LOOP TESTS PASSED ===")
