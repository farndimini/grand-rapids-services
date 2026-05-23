from __future__ import annotations

import concurrent.futures
import logging
import time
from typing import Any

from agent_core.multi_agent.base_agent import AgentBase
from agent_core.multi_agent.context import SharedContext
from agent_core.execution_graph import ExecutionGraph, TaskNode

log = logging.getLogger("multi_agent.orchestrator")

MAX_ROUNDS = 3
AGENT_TIMEOUT = 30.0
MAX_RETRIES_PER_AGENT = 1


class BoundedOrchestrator:
    def __init__(
        self,
        agents: dict[str, AgentBase],
        execution_order: list[str] | None = None,
        max_rounds: int = MAX_ROUNDS,
        agent_timeout: float = AGENT_TIMEOUT,
    ):
        self.agents = agents
        self.execution_order = execution_order or list(agents.keys())
        self.max_rounds = max_rounds
        self.agent_timeout = agent_timeout

        unknown = set(self.execution_order) - set(self.agents.keys())
        if unknown:
            raise ValueError(f"Unknown agents in execution_order: {unknown}")

        self._benchmarks: dict[str, Any] = {
            "total_rounds": 0,
            "total_cost": 0.0,
            "total_latency_ms": 0.0,
            "agent_stats": {},
            "deadlocks_detected": 0,
            "retries": 0,
        }
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent_orch_")

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)

    def execute(self, keyword: str, topic: str = "", niche: str = "", target_audience: str = "") -> SharedContext:
        ctx = SharedContext(
            keyword=keyword,
            topic=topic or keyword,
            niche=niche,
            target_audience=target_audience,
            max_rounds=self.max_rounds,
        )

        for round_num in range(1, self.max_rounds + 1):
            ctx.round = round_num
            pre_snapshot = ctx.snapshot_business()

            for agent_name in self.execution_order:
                ctx = self._run_agent(agent_name, ctx, round_num)

            post_snapshot = ctx.snapshot_business()
            if pre_snapshot == post_snapshot:
                ctx.deadlock_rounds += 1
                self._benchmarks["deadlocks_detected"] += 1
                log.warning(f"[ORCH] Deadlock detected at round {round_num} — no state change")
                break

            if ctx.critique.get("approved", False):
                log.info(f"[ORCH] Critic approved at round {round_num}")

            self._benchmarks["total_rounds"] = round_num

        self._benchmarks["total_cost"] = round(ctx.cost_total, 4)
        self._benchmarks["total_latency_ms"] = round(ctx.latency_total, 2)
        return ctx

    def _run_agent(self, agent_name: str, ctx: SharedContext, round_num: int) -> SharedContext:
        agent = self.agents[agent_name]
        t0 = time.perf_counter()

        for attempt in range(1 + MAX_RETRIES_PER_AGENT):
            try:
                fut = self._executor.submit(agent.run, ctx, round_num)
                ctx = fut.result(timeout=self.agent_timeout)
                # Retry succeeded — clear transient errors added by agent.run()
                if attempt > 0:
                    prefix = f"[{agent.name}]"
                    ctx.errors = [e for e in ctx.errors if not e.startswith(prefix)]
                break
            except concurrent.futures.TimeoutError:
                log.warning(f"[ORCH] {agent_name} round {round_num} timed out (attempt {attempt + 1})")
                if attempt < MAX_RETRIES_PER_AGENT:
                    self._benchmarks["retries"] += 1
                    continue
                ctx.add_error(agent_name, f"Timeout ({self.agent_timeout}s)")
                break
            except Exception as e:
                log.warning(f"[ORCH] {agent_name} round {round_num} error (attempt {attempt + 1}): {e}")
                if attempt < MAX_RETRIES_PER_AGENT:
                    self._benchmarks["retries"] += 1
                    continue
                ctx.add_error(agent_name, str(e))
                break

        latency = (time.perf_counter() - t0) * 1000
        self._update_agent_stats(agent_name, latency)
        return ctx

    def _update_agent_stats(self, agent_name: str, latency_ms: float) -> None:
        stats = self._benchmarks["agent_stats"]
        if agent_name not in stats:
            stats[agent_name] = {"calls": 0, "total_latency_ms": 0.0, "failures": 0}
        stats[agent_name]["calls"] += 1
        stats[agent_name]["total_latency_ms"] += latency_ms

    def benchmark(self) -> dict[str, Any]:
        stats = self._benchmarks["agent_stats"]
        for name, s in stats.items():
            s["avg_latency_ms"] = round(s["total_latency_ms"] / max(s["calls"], 1), 2)
            s["total_latency_ms"] = round(s["total_latency_ms"], 2)
        return dict(self._benchmarks)

    def to_execution_graph(self, keyword: str) -> ExecutionGraph:
        import asyncio

        graph = ExecutionGraph(f"multi_agent_{keyword}")

        async def _wrap(
            agent_name: str, kw: str, topic: str, niche: str, audience: str,
        ) -> SharedContext:
            ctx = SharedContext(keyword=kw, topic=topic, niche=niche, target_audience=audience)
            for round_num in range(1, self.max_rounds + 1):
                for name in self.execution_order:
                    ctx = self._run_agent(name, ctx, round_num)
            return ctx

        prev = None
        for agent_name in self.execution_order:
            depends = [prev] if prev else None
            graph.add_node(
                agent_name,
                _wrap,
                agent_name, keyword, "", "",
                depends_on=depends,
                timeout=self.agent_timeout,
                retries=MAX_RETRIES_PER_AGENT,
            )
            prev = agent_name

        return graph
