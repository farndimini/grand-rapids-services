"""
agent_core/learning_loop.py — Learning Loop Orchestrator
=========================================================
Closes the persistent learning loop:
  GscFeedback → RewardEngine → StrategyEvolution → evaluation

Wires together:
  - GscFeedbackOrchestrator for GSC data polling + reward signals
  - RewardEngine for unified reward computation
  - StrategyEvolution for strategy/prompt pattern tracking
  - BenchmarkRunner for article quality scoring
  - AgentPlanner for adaptive plan generation
  - PipelineStateMachine for per-keyword pipeline state
  - AsyncWorkflowRuntime for scheduling feedback/rewrite tasks
  - MemoryAdapter (JSON + vector) for article identity persistence
  - MetricsStore for analytics recording

Usage:
    from agent_core.learning_loop import LearningLoopOrchestrator
    loop = LearningLoopOrchestrator()
    result = loop.run_cycle(keyword="best laptop")
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

log = logging.getLogger("agent_core.learning_loop")


# ──────────────────────────────────────────────────────────────
#  Cycle Result
# ──────────────────────────────────────────────────────────────

@dataclass
class LearningCycleResult:
    keyword: str
    timestamp: str
    state_before: str
    state_after: str
    reward_signal: dict | None
    reward_value: float
    strategy_updated: bool
    rewrite_triggered: bool
    quality_score: int | None
    gsc_position: int | None
    gsc_ctr: float | None
    gsc_impressions: int | None
    artifacts: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "timestamp": self.timestamp,
            "state_before": self.state_before,
            "state_after": self.state_after,
            "reward_signal": self.reward_signal,
            "reward_value": self.reward_value,
            "strategy_updated": self.strategy_updated,
            "rewrite_triggered": self.rewrite_triggered,
            "quality_score": self.quality_score,
            "gsc_position": self.gsc_position,
            "gsc_ctr": self.gsc_ctr,
            "gsc_impressions": self.gsc_impressions,
            "artifacts": self.artifacts,
        }


# ──────────────────────────────────────────────────────────────
#  LearningLoopOrchestrator
# ──────────────────────────────────────────────────────────────

class LearningLoopOrchestrator:
    """Orchestrates one closed learning cycle for a keyword.

    Each cycle:
      1. Loads/resumes pipeline state for the keyword
      2. Polls GSC data (or uses cached) via GscFeedbackOrchestrator
      3. Scores current article quality via BenchmarkRunner
      4. Computes reward from GSC + quality signals via RewardEngine
      5. Records reward in StrategyEvolution for pattern tracking
      6. Detects decay — triggers rewrite priority if needed
      7. Persists article identity via MemoryAdapter
      8. Records analytics via MetricsStore
      9. Saves state machine checkpoint
    """

    def __init__(
        self,
        plans_dir: str | Path = "",
        checkpoints_dir: str | Path = "",
        state_machine=None,
        planner=None,
        gsc_orchestrator=None,
        reward_engine=None,
        strategy_evolution=None,
        benchmark_runner=None,
        memory_adapter=None,
        metrics_store=None,
        vector_memory=None,
    ):
        from agent_core.planner import AgentPlanner, Policy
        from agent_core.state_machine import PipelineStateMachine
        from evaluation.benchmark_runner import BenchmarkRunner
        from evaluation.scorers import SemanticScorer, StructureScorer, SERPScorer, ReadabilityScorer
        from agent_core.metrics_store import MetricsStore
        from agent_core.memory_adapter import MemoryAdapter

        self._plans_dir = Path(plans_dir) if plans_dir else Path("plans")
        self._checkpoints_dir = Path(checkpoints_dir) if checkpoints_dir else Path("checkpoints")
        self._plans_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoints_dir.mkdir(parents=True, exist_ok=True)

        self._planner = planner or AgentPlanner(policy=Policy(
            min_quality_score=65,
            max_rewrite_attempts=2,
            rewrite_threshold=60,
            enable_cluster=True,
            enable_calendar=True,
        ))
        self._state_machine_cls = state_machine or PipelineStateMachine
        self._gsc = gsc_orchestrator
        self._reward_engine = reward_engine
        self._strategy_evolution = strategy_evolution
        self._benchmark_runner = benchmark_runner
        self._memory_adapter = memory_adapter or MemoryAdapter()
        self._metrics_store = metrics_store
        self._vector_memory = vector_memory

        self._sm_cache: dict[str, Any] = {}
        self._cycle_history: list[LearningCycleResult] = []

    # ── Properties for lazy init ──────────────────────────────

    @property
    def gsc(self):
        if self._gsc is None:
            try:
                from agent_core.gsc_feedback import GscFeedbackOrchestrator
                self._gsc = GscFeedbackOrchestrator()
            except Exception as e:
                log.warning("GscFeedbackOrchestrator not available: %s", e)
                self._gsc = _NullGsc()
        return self._gsc

    @property
    def reward_engine(self):
        if self._reward_engine is None:
            try:
                from agent_core.rl_optimizer import RewardEngine
                self._reward_engine = RewardEngine()
            except Exception as e:
                log.warning("RewardEngine not available: %s", e)
                self._reward_engine = _NullRewardEngine()
        return self._reward_engine

    @property
    def strategy_evolution(self):
        if self._strategy_evolution is None:
            try:
                from agent_core.rl_optimizer import StrategyEvolution
                self._strategy_evolution = StrategyEvolution()
            except Exception as e:
                log.warning("StrategyEvolution not available: %s", e)
                self._strategy_evolution = _NullStrategyEvolution()
        return self._strategy_evolution

    @property
    def benchmark_runner(self):
        if self._benchmark_runner is None:
            try:
                from evaluation.benchmark_runner import BenchmarkRunner
                self._benchmark_runner = BenchmarkRunner()
            except Exception as e:
                log.warning("BenchmarkRunner not available: %s", e)
                self._benchmark_runner = _NullBenchmarkRunner()
        return self._benchmark_runner

    @property
    def metrics_store(self):
        if self._metrics_store is None:
            try:
                from agent_core.metrics_store import MetricsStore
                self._metrics_store = MetricsStore()
            except Exception as e:
                log.warning("MetricsStore not available: %s", e)
                self._metrics_store = _NullMetricsStore()
        return self._metrics_store

    # ── Core public API ──────────────────────────────────────

    def get_or_create_sm(self, keyword: str) -> Any:
        """Load existing PipelineStateMachine for keyword or create new."""
        from agent_core.state_machine import State
        pipeline_id = _pipeline_id(keyword)
        sm = self._state_machine_cls.resume(pipeline_id)
        if sm is None:
            sm = self._state_machine_cls(pipeline_id, keyword=keyword)
        self._sm_cache[keyword] = sm
        return sm

    def run_cycle(
        self,
        keyword: str,
        article_text: str = "",
        article_html: str = "",
        model: str = "local",
        niche: str = "",
        serp_data: dict | None = None,
        dry_run: bool = False,
        force: bool = False,
    ) -> LearningCycleResult:
        """Execute one closed learning cycle for a keyword.

        Args:
            keyword: The target keyword.
            article_text: Plain text of the article (for scoring/embedding).
            article_html: HTML of the article (for BenchmarkRunner structure scoring).
            model: Model name used for generation.
            niche: Content niche.
            serp_data: Optional SERP data dict.
            dry_run: If True, no state mutations or persistence.
            force: If True, run even if terminal state reached.

        Returns:
            LearningCycleResult with full cycle data.
        """
        from agent_core.state_machine import State
        from seo.google_feedback import evaluate_real_performance
        import memory as mem_module

        t0 = time.time()
        timestamp = datetime.now().isoformat()
        cycle_id = f"cycle_{keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # ── 1. State machine ──────────────────────────────────
        sm = self.get_or_create_sm(keyword)
        state_before = sm.state.name

        if sm.is_terminal and not force:
            log.info("[Loop] '%s' already terminal (%s), skipping", keyword, state_before)
            return self._make_result(
                keyword=keyword, timestamp=timestamp, cycle_id=cycle_id,
                state_before=state_before, state_after=state_before,
                skipped=True,
            )

        if not dry_run:
            sm.transition(State.RUNNING, reason="learning_cycle_started")

        # ── 2. GSC polling ───────────────────────────────────
        gsc_result = self._poll_gsc(keyword, dry_run=dry_run)
        gsc_position = gsc_result.get("position")
        gsc_ctr = gsc_result.get("ctr")
        gsc_impressions = gsc_result.get("impressions")
        gsc_clicks = gsc_result.get("clicks")
        decay_score = gsc_result.get("decay_score")
        anomalies = gsc_result.get("anomalies", [])

        # ── 3. Record GSC performance in JSON memory ──────────
        if not dry_run and (gsc_position is not None or gsc_impressions is not None):
            mem = mem_module.load()
            mem_module.record_performance(mem, keyword, {
                "position": gsc_position,
                "ctr": gsc_ctr,
                "impressions": gsc_impressions,
                "clicks": gsc_clicks,
                "source": gsc_result.get("source", "gsc_api"),
                "decay_score": decay_score,
                "cycle_timestamp": timestamp,
            })
            if not self._metrics_store_is_null():
                self.metrics_store.record_ranking(
                    keyword=keyword,
                    position=gsc_position,
                    ctr=gsc_ctr,
                    impressions=gsc_impressions,
                    clicks=gsc_clicks,
                )

        # ── 4. Quality scoring via BenchmarkRunner ────────────
        quality_score = None
        quality_report = None
        reward_from_quality = 0.0

        if article_html or article_text:
            try:
                report = self.benchmark_runner.evaluate(
                    article_html=article_html or article_text,
                    keyword=keyword,
                    serp_data=serp_data,
                    model=model,
                )
                quality_score = int(report.final_score)
                quality_report = report.to_dict() if hasattr(report, 'to_dict') else {}
                reward_from_quality = self._map_verdict_to_reward(report.verdict)

                if not dry_run and not self._metrics_store_is_null():
                    self.metrics_store.record_quality(
                        keyword=keyword,
                        score=quality_score,
                        reward=reward_from_quality,
                        serp_alignment=report.dimension_scores.get("serp_alignment", ScoreResult()).score / 100 if hasattr(report, 'dimension_scores') else None,
                    )
            except Exception as e:
                log.warning("[Loop] BenchmarkRunner failed for '%s': %s", keyword, e)

        # ── 5. GSC evaluation (from old google_feedback) ─────
        performance_score = None
        issues = []
        should_rewrite = False

        if gsc_position is not None:
            try:
                gsc_data_for_eval = {
                    "position": gsc_position,
                    "ctr": gsc_ctr,
                    "impressions": gsc_impressions,
                    "clicks": gsc_clicks,
                }
                evaluation = evaluate_real_performance(gsc_data_for_eval)
                performance_score = evaluation.get("performance_score", 0)
                issues = evaluation.get("issues", [])
                from seo.google_feedback import rewrite_decision, estimate_ranking_potential
                potential = estimate_ranking_potential(keyword, gsc_position)
                decision = rewrite_decision(evaluation, potential)
                should_rewrite = decision.get("should_rewrite", False)
            except Exception as e:
                log.warning("[Loop] GSC evaluation failed for '%s': %s", keyword, e)

        # ── 6. Compute unified reward ─────────────────────────
        # ranking_pred: 50 = neutral when no GSC data, else invert position (pos 1 → 95, pos 50 → 0)
        if gsc_position is not None:
            ranking_pred = float(max(0, 100 - gsc_position * 5))
        else:
            ranking_pred = 50.0  # neutral — no data

        reward = self.reward_engine.compute(
            quality=float(quality_score or performance_score or 50),
            ranking_pred=ranking_pred,
            cost_usd=gsc_result.get("cost_usd", 0.0),
            latency_ms=(time.time() - t0) * 1000,
            rewrites=0,
            serp_alignment=1.0 if gsc_position and gsc_position <= 10 else 0.5,
            factual_confidence=1.0,
            word_count=len(article_text.split()) if article_text else 0,
        )
        reward_value = reward.total_reward

        # ── 7. Record reward in StrategyEvolution ─────────────
        strategy_updated = False
        if not dry_run:
            try:
                score_for_pattern = quality_score or performance_score or 50
                pattern_value = _infer_pattern_type(keyword, score_for_pattern)
                self.strategy_evolution.record_outcome(
                    pattern_type="quality_strategy",
                    value=pattern_value,
                    reward=reward_value,
                )
                for issue_type in issues:
                    self.strategy_evolution.record_outcome(
                        pattern_type="failure_pattern",
                        value=issue_type,
                        reward=-0.3,
                    )
                # Extract and record actionable content patterns from article text
                if article_text:
                    _record_actionable_patterns(
                        self.strategy_evolution, article_text,
                        keyword, reward_value,
                    )
                strategy_updated = True
            except Exception as e:
                log.warning("[Loop] StrategyEvolution recording failed: %s", e)

        # ── 8. Persist article identity in MemoryAdapter ──────
        if not dry_run and article_text:
            try:
                self._memory_adapter.record_article(
                    keyword=keyword,
                    text=article_text,
                    model=model,
                    quality_score=quality_score or 0,
                    niche=niche,
                )
            except Exception as e:
                log.warning("[Loop] MemoryAdapter persist failed: %s", e)

        # ── 9. Store in vector memory ─────────────────────────
        if not dry_run and article_text and self._vector_memory is not None:
            try:
                self._vector_memory.async_store(
                    doc_id=_pipeline_id(keyword),
                    text=article_text,
                    metadata={
                        "keyword": keyword,
                        "model": model,
                        "quality_score": quality_score or 0,
                        "reward": reward_value,
                        "niche": niche,
                        "gsc_position": gsc_position,
                        "cycle_timestamp": timestamp,
                    },
                    keyword=keyword,
                )
            except Exception as e:
                log.warning("[Loop] VectorMemory store failed: %s", e)

        # ── 10. State machine transition ──────────────────────
        rewrite_triggered = False
        if not dry_run:
            self._advance_state_machine(
                sm, quality_score=quality_score or performance_score,
                should_rewrite=should_rewrite, decay_score=decay_score,
                dry_run=dry_run,
            )
            rewrite_triggered = (should_rewrite and (quality_score or 50) < 60)

        # ── 11. Record cycle in MetricsStore ──────────────────
        if not dry_run and not self._metrics_store_is_null():
            try:
                self.metrics_store.record_latency(
                    stage="learning_cycle",
                    latency_ms=(time.time() - t0) * 1000,
                    success=True,
                    keyword=keyword,
                    reward=reward_value,
                )
            except Exception as _lat_err:
                log.warning("[Loop] MetricsStore latency record failed for '%s': %s", keyword, _lat_err)

        result = LearningCycleResult(
            keyword=keyword,
            timestamp=timestamp,
            state_before=state_before,
            state_after=sm.state.name,
            reward_signal={
                "total": reward_value,
                "components": reward.components,
                "explanation": reward.explanation,
                "gsc_position": gsc_position,
                "quality_score": quality_score,
                "performance_score": performance_score,
                "decay_score": decay_score,
            },
            reward_value=reward_value,
            strategy_updated=strategy_updated,
            rewrite_triggered=rewrite_triggered,
            quality_score=quality_score or performance_score,
            gsc_position=gsc_position,
            gsc_ctr=gsc_ctr,
            gsc_impressions=gsc_impressions,
            artifacts={
                "cycle_id": cycle_id,
                "duration_sec": round(time.time() - t0, 3),
                "issues": issues,
                "anomalies": anomalies,
                "performance_score": performance_score,
                "quality_report": quality_report,
                "gsc_source": gsc_result.get("source", ""),
            },
        )
        self._cycle_history.append(result)
        return result

    def run_batch(
        self,
        keywords: list[str],
        batch_size: int = 5,
        article_map: dict[str, tuple[str, str]] | None = None,
        model: str = "local",
        niche: str = "",
        serp_data_map: dict[str, dict] | None = None,
        dry_run: bool = False,
    ) -> list[LearningCycleResult]:
        """Run learning cycles for multiple keywords.

        Args:
            keywords: List of keywords to process.
            batch_size: Process N keywords per batch.
            article_map: Optional mapping of keyword -> (article_text, article_html).
            model: Model name.
            niche: Content niche.
            serp_data_map: Optional mapping of keyword -> serp_data dict.
            dry_run: If True, no mutations.

        Returns:
            List of LearningCycleResult, one per keyword.
        """
        results = []
        for i in range(0, len(keywords), batch_size):
            batch_kws = keywords[i:i + batch_size]
            for kw in batch_kws:
                article_text = ""
                article_html = ""
                serp_data = None

                if article_map and kw in article_map:
                    pair = article_map[kw]
                    if isinstance(pair, tuple) and len(pair) >= 2:
                        article_text, article_html = pair[0], pair[1]
                    else:
                        article_text = str(pair)

                if serp_data_map and kw in serp_data_map:
                    serp_data = serp_data_map[kw]

                try:
                    result = self.run_cycle(
                        keyword=kw,
                        article_text=article_text,
                        article_html=article_html,
                        model=model,
                        niche=niche,
                        serp_data=serp_data,
                        dry_run=dry_run,
                    )
                    results.append(result)
                except Exception as e:
                    log.error("[Loop] Batch cycle failed for '%s': %s", kw, e)
                    results.append(LearningCycleResult(
                        keyword=kw,
                        timestamp=datetime.now().isoformat(),
                        state_before="ERROR",
                        state_after="FAILED",
                        reward_signal=None,
                        reward_value=0.0,
                        strategy_updated=False,
                        rewrite_triggered=False,
                        quality_score=None,
                        gsc_position=None,
                        gsc_ctr=None,
                        gsc_impressions=None,
                        artifacts={"error": str(e)},
                    ))
        return results

    def find_decayed_articles(
        self,
        keywords: list[str],
        decay_threshold: float = 0.3,
        dry_run: bool = False,
    ) -> list[dict]:
        """Check which keywords have decayed and need rewrite.

        Uses GscFeedbackOrchestrator.run_decay_check if available,
        otherwise compares current positions vs stored positions.

        Args:
            keywords: Keywords to check.
            decay_threshold: Min decay score to trigger alert (default 0.3).
            dry_run: If True, no state mutations.

        Returns:
            List of alert dicts with keyword, decay, and details.
        """
        if hasattr(self.gsc, 'run_decay_check'):
            return self.gsc.run_decay_check(keywords, threshold=decay_threshold)

        import memory as mem_module
        mem = mem_module.load()
        alerts = []

        for kw in keywords:
            decay = self._compute_decay_from_memory(mem, kw)
            if decay >= decay_threshold:
                gsc_data = self._poll_gsc(kw, dry_run=dry_run)
                alerts.append({
                    "keyword": kw,
                    "decay": round(decay, 3),
                    "current_position": gsc_data.get("position"),
                    "stored_position": self._get_stored_position(mem, kw),
                    "timestamp": datetime.now().isoformat(),
                })

        alerts.sort(key=lambda a: a["decay"], reverse=True)
        return alerts

    def get_strategy_recommendations(
        self,
        keyword: str,
        top_n: int = 3,
    ) -> list[dict]:
        """Get StrategyEvolution recommendations for a keyword.

        Returns best-performing strategy patterns from history.
        """
        try:
            patterns = self.strategy_evolution.recommend(
                pattern_type="quality_strategy",
                top_n=top_n,
            )
            return [
                {
                    "pattern_type": p.pattern_type,
                    "value": p.value,
                    "avg_reward": p.avg_reward,
                    "occurrences": p.occurrences,
                }
                for p in patterns
            ]
        except Exception as e:
            log.warning("[Loop] Strategy recommendations unavailable: %s", e)
            return []

    def get_similar_articles(
        self,
        keyword: str,
        top_k: int = 5,
    ) -> list[dict]:
        """Find semantically similar past articles via MemoryAdapter."""
        try:
            results = self._memory_adapter.find_similar(keyword, top_k=top_k)
            return [r.to_dict() if hasattr(r, 'to_dict') else {
                "keyword": r.keyword,
                "score": getattr(r, 'score', 0),
                "quality_score": getattr(r, 'quality_score', 0),
            } for r in results]
        except Exception:
            log.warning("[Loop] get_similar_articles failed for '%s'", keyword, exc_info=True)
            return []

    def decay_summary(self) -> dict:
        """Aggregate summary of all recent cycle results."""
        if not self._cycle_history:
            return {"cycles": 0, "message": "no cycles run yet"}

        avg_reward = sum(r.reward_value for r in self._cycle_history) / len(self._cycle_history)
        rewrites = sum(1 for r in self._cycle_history if r.rewrite_triggered)
        updated = sum(1 for r in self._cycle_history if r.strategy_updated)
        scores = [r.quality_score for r in self._cycle_history if r.quality_score is not None]

        return {
            "total_cycles": len(self._cycle_history),
            "avg_reward": round(avg_reward, 3),
            "rewrites_triggered": rewrites,
            "strategies_updated": updated,
            "avg_quality_score": round(sum(scores) / len(scores), 1) if scores else None,
            "keywords": [r.keyword for r in self._cycle_history[-10:]],
        }

    def history(
        self,
        limit: int = 10,
        min_reward: float | None = None,
    ) -> list[dict]:
        """Return recent cycle history, optionally filtered."""
        results = [r.to_dict() for r in self._cycle_history]
        if min_reward is not None:
            results = [r for r in results if r.get("reward_value", 0) >= min_reward]
        return results[-limit:]

    # ── Private helpers ──────────────────────────────────────

    def _poll_gsc(self, keyword: str, dry_run: bool = False) -> dict:
        """Poll GSC for keyword data.

        In dry_run mode, returns cached data only — no network calls.
        In normal mode, tries live GSC polling with memory fallback.
        """
        import memory as mem_module
        mem = mem_module.load()
        cached = self._get_stored_performance(mem, keyword)

        if dry_run:
            return {
                "position": cached.get("position"),
                "ctr": cached.get("ctr"),
                "impressions": cached.get("impressions"),
                "clicks": cached.get("clicks"),
                "decay_score": None,
                "anomalies": [],
                "source": "memory_cache",
                "cost_usd": 0.0,
            }

        try:
            if hasattr(self.gsc, 'poll_and_analyze'):
                result = self.gsc.poll_and_analyze([keyword], days=28)
                kw_data = result.get(keyword, {})
                # poll_and_analyze nests GSC metrics under "data" key,
                # decay/anomalies/reward under their own keys.
                # Extract from nested structure — NOT flat kw_data keys.
                nested_data = kw_data.get("data", {})
                decay_obj = kw_data.get("decay")
                anomaly_list = kw_data.get("anomalies", [])
                return {
                    "position": nested_data.get("position", cached.get("position")),
                    "ctr": nested_data.get("ctr", cached.get("ctr")),
                    "impressions": nested_data.get("impressions", cached.get("impressions")),
                    "clicks": nested_data.get("clicks", cached.get("clicks")),
                    "decay_score": decay_obj.score if decay_obj else None,
                    "anomalies": [a.to_dict() if hasattr(a, 'to_dict') else str(a) for a in anomaly_list],
                    "source": "gsc_api",
                    "cost_usd": 0.0,
                }
        except Exception as e:
            log.warning("[Loop] GSC poll failed for '%s': %s", keyword, e)

        return {
            "position": cached.get("position"),
            "ctr": cached.get("ctr"),
            "impressions": cached.get("impressions"),
            "clicks": cached.get("clicks"),
            "decay_score": None,
            "anomalies": [],
            "source": "memory_cache",
            "cost_usd": 0.0,
        }

    def _get_stored_performance(self, mem: dict, keyword: str) -> dict:
        """Get last stored performance entry for keyword from JSON memory."""
        articles = mem.get("articles_written", [])
        for a in articles:
            if a.get("keyword") == keyword:
                hist = a.get("performance_history", [])
                if hist:
                    return hist[-1]
        return {}

    def _get_stored_position(self, mem: dict, keyword: str) -> int | None:
        perf = self._get_stored_performance(mem, keyword)
        return perf.get("position")

    def _compute_decay_from_memory(self, mem: dict, keyword: str) -> float:
        """Estimate decay by comparing 1st vs last stored positions."""
        articles = mem.get("articles_written", [])
        for a in articles:
            if a.get("keyword") == keyword:
                hist = a.get("performance_history", [])
                if len(hist) >= 2:
                    first = hist[0].get("position", 50)
                    last = hist[-1].get("position", 50)
                    if first > 0:
                        return max(0.0, (last - first) / first)
        return 0.0

    def _advance_state_machine(
        self,
        sm: Any,
        quality_score: int | None,
        should_rewrite: bool,
        decay_score: float | None,
        dry_run: bool,
    ) -> None:
        """Advance the state machine based on cycle outcomes."""
        from agent_core.state_machine import State

        if dry_run:
            return

        if sm.is_terminal:
            return

        if sm.can_transition(State.VALIDATING):
            sm.transition(State.VALIDATING, reason="quality_check")

        if quality_score is not None and quality_score >= 65 and not should_rewrite:
            if sm.can_transition(State.COMPLETE):
                sm.transition(State.COMPLETE, reason="quality_pass_no_rewrite")
        elif quality_score is not None and quality_score < 60 and should_rewrite:
            if sm.can_transition(State.REWRITING):
                sm.transition(State.REWRITING, reason="low_quality_decay")
            if sm.can_transition(State.VALIDATING):
                sm.transition(State.VALIDATING, reason="post_rewrite_validation")
        elif decay_score is not None and decay_score >= 0.3 and should_rewrite:
            if sm.can_transition(State.REWRITING):
                sm.transition(State.REWRITING, reason="decay_detected")
            if sm.can_transition(State.VALIDATING):
                sm.transition(State.VALIDATING, reason="post_rewrite_validation")
        else:
            if sm.can_transition(State.COMPLETE):
                sm.transition(State.COMPLETE, reason="cycle_complete")

    def _map_verdict_to_reward(self, verdict: str) -> float:
        mapping = {
            "EXCELLENT": 1.0,
            "GOOD": 0.5,
            "ACCEPTABLE": 0.0,
            "NEEDS_IMPROVEMENT": -0.5,
            "POOR": -1.0,
        }
        return mapping.get(verdict, 0.0)

    def _make_result(
        self, keyword: str, timestamp: str, cycle_id: str,
        state_before: str, state_after: str, skipped: bool = False,
    ) -> LearningCycleResult:
        return LearningCycleResult(
            keyword=keyword, timestamp=timestamp,
            state_before=state_before, state_after=state_after,
            reward_signal=None, reward_value=0.0,
            strategy_updated=False, rewrite_triggered=False,
            quality_score=None, gsc_position=None,
            gsc_ctr=None, gsc_impressions=None,
            artifacts={"cycle_id": cycle_id, "skipped": skipped},
        )

    def _metrics_store_is_null(self) -> bool:
        return isinstance(self._metrics_store, _NullMetricsStore)

    def shutdown(self, wait: bool = True) -> None:
        """Release resources (MemoryAdapter vector thread pool, etc.)."""
        try:
            self._memory_adapter.shutdown(wait=wait)
        except Exception:
            log.debug("[Loop] memory_adapter.shutdown failed (expected if never started)")


# ──────────────────────────────────────────────────────────────
#  Null implementations (graceful fallback when deps missing)
# ──────────────────────────────────────────────────────────────

class _NullGsc:
    def poll_and_analyze(self, keywords, days=28):
        return {}
    def run_decay_check(self, keywords, threshold=0.3):
        return []
    def get_reward_summary(self, keywords):
        return {}
    def generate_feedback_report(self, keywords):
        return {}


class _NullRewardEngine:
    def compute(self, **kwargs):
        from agent_core.rl_optimizer import RewardSignal
        return RewardSignal(total_reward=0.0, components={}, explanation="not available")


class _NullStrategyEvolution:
    def record_outcome(self, pattern_type, value, reward):
        pass
    def recommend(self, pattern_type, top_n=3):
        return []
    def summary(self):
        return {"total_patterns": 0, "epsilon": 0.2, "by_type": {}}


class _NullBenchmarkRunner:
    def evaluate(self, article_html, keyword, serp_data=None, model="local"):
        from evaluation.scorers import ScoreResult
        from evaluation.benchmark_runner import BenchmarkReport
        return BenchmarkReport(
            keyword=keyword, final_score=50.0, verdict="ACCEPTABLE",
            dimension_scores={
                "semantic": ScoreResult(50.0),
                "structure": ScoreResult(50.0),
                "serp_alignment": ScoreResult(50.0),
                "readability": ScoreResult(50.0),
                "eeat": ScoreResult(50.0),
                "quality_gate": ScoreResult(50.0),
            },
            weights_used={},
            generated_at=datetime.now().isoformat(),
        )


class _NullMetricsStore:
    def record_latency(self, **kwargs): pass
    def record_ranking(self, **kwargs): pass
    def record_quality(self, **kwargs): pass
    def record_provider_call(self, **kwargs): pass
    def record_cache(self, **kwargs): pass
    def record_rewrite(self, **kwargs): pass
    def record_tokens(self, **kwargs): pass
    def cleanup_old(self, days=90): return {}
    def full_summary(self, days=7): return {}


def _pipeline_id(keyword: str) -> str:
    import hashlib
    return "loop_" + hashlib.sha256(keyword.encode("utf-8")).hexdigest()[:16]


def _infer_pattern_type(keyword: str, score: int) -> str:
    kw_l = keyword.lower()
    if score >= 80:
        return f"high_quality:{kw_l[:30]}"
    elif score >= 60:
        return f"medium_quality:{kw_l[:30]}"
    else:
        return f"low_quality:{kw_l[:30]}"


def _record_actionable_patterns(
    strategy_evolution: Any,
    article_text: str,
    keyword: str,
    reward: float,
) -> None:
    """Extract and record actionable content patterns from article text.

    Records opener type, structure type, and CTA presence as StrategyEvolution
    patterns so they can be injected into future article prompts.
    """
    import re

    text_lower = article_text[:500].lower()

    # Opener type detection
    if text_lower.startswith(("most", "the most")):
        strategy_evolution.record_outcome("opener", "superlative_open", reward)
    elif text_lower.startswith(("the best", "best ")):
        strategy_evolution.record_outcome("opener", "best_of_open", reward)
    elif text_lower.startswith(("how to", "how ")):
        strategy_evolution.record_outcome("opener", "how_to_open", reward)
    elif text_lower.startswith(("what is", "what ")):
        strategy_evolution.record_outcome("opener", "definition_open", reward)
    elif text_lower.startswith(("why ", "why")):
        strategy_evolution.record_outcome("opener", "why_open", reward)
    elif any(c.isdigit() for c in text_lower[:100]):
        strategy_evolution.record_outcome("opener", "stat_open", reward)
    else:
        strategy_evolution.record_outcome("opener", "narrative_open", reward)

    # Section structure detection (from markdown headers)
    h2_count = len(re.findall(r'^##\s', article_text, re.MULTILINE))
    h3_count = len(re.findall(r'^###\s', article_text, re.MULTILINE))
    if h2_count >= 8:
        strategy_evolution.record_outcome("structure", "deep_h2_sections", reward)
    elif h2_count >= 5:
        strategy_evolution.record_outcome("structure", "standard_h2_sections", reward)
    else:
        strategy_evolution.record_outcome("structure", "shallow_h2_sections", reward)
    if h3_count >= 5:
        strategy_evolution.record_outcome("structure", "deep_h3_nesting", reward)

    # CTA detection
    if any(p in text_lower for p in ["try ", "get started", "sign up", "download", "buy "]):
        strategy_evolution.record_outcome("cta", "direct_cta", reward)
    if any(p in text_lower for p in ["learn more", "read more", "check out"]):
        strategy_evolution.record_outcome("cta", "soft_cta", reward)


__all__ = [
    "LearningLoopOrchestrator",
    "LearningCycleResult",
]
