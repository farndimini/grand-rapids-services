from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from agent_core.multi_agent.context import SharedContext

log = logging.getLogger("multi_agent")


class AgentBase(ABC):
    name: str
    model: str
    cost_per_call: float = 0.001

    def __init__(self, name: str, model: str = "local", cost_per_call: float = 0.001):
        self.name = name
        self.model = model
        self.cost_per_call = cost_per_call

    @abstractmethod
    def process(self, ctx: SharedContext, round_num: int) -> SharedContext:
        ...

    def emit_telemetry(
        self, ctx: SharedContext, round_num: int, status: str,
        latency_ms: float, cost: float, output: dict[str, Any],
    ) -> None:
        ctx.add_telemetry({
            "agent": self.name,
            "round": round_num,
            "status": status,
            "latency_ms": round(latency_ms, 2),
            "cost": round(cost, 6),
            "model": self.model,
            "output": output,
        })

    def structured_output(self, ctx: SharedContext) -> dict[str, Any]:
        return {
            "agent": self.name,
            "model": self.model,
            "round": ctx.round,
            "keyword": ctx.keyword,
            "timestamp": time.time(),
        }

    def run(self, ctx: SharedContext, round_num: int) -> SharedContext:
        t0 = time.perf_counter()
        try:
            ctx.round = round_num
            ctx = self.process(ctx, round_num)
            latency = (time.perf_counter() - t0) * 1000
            self.emit_telemetry(ctx, round_num, "success", latency, self.cost_per_call, self.structured_output(ctx))
            return ctx
        except Exception as e:
            latency = (time.perf_counter() - t0) * 1000
            ctx.add_error(self.name, str(e))
            self.emit_telemetry(ctx, round_num, "failed", latency, 0.0, {"error": str(e)})
            log.warning(f"[{self.name}] round {round_num} failed: {e}")
            raise
