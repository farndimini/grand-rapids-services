from __future__ import annotations

from typing import Any

from agent_core.multi_agent.context import SharedContext
from agent_core.multi_agent.orchestrator import BoundedOrchestrator
from agent_core.execution_graph import ExecutionGraph


def orchestrate_via_graph(
    keyword: str,
    topic: str = "",
    niche: str = "",
    target_audience: str = "",
    max_rounds: int = 3,
    agent_timeout: float = 30.0,
) -> SharedContext:
    from agent_core.multi_agent import Researcher, Strategist, Writer, Optimizer, Critic

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
        max_rounds=max_rounds,
        agent_timeout=agent_timeout,
    )
    return orch.execute(keyword, topic, niche, target_audience)


def build_execution_graph(
    keyword: str,
    max_rounds: int = 3,
    agent_timeout: float = 30.0,
) -> ExecutionGraph:
    from agent_core.multi_agent import Researcher, Strategist, Writer, Optimizer, Critic

    agents = {
        "researcher": Researcher(),
        "strategist": Strategist(),
        "writer": Writer(),
        "optimizer": Optimizer(),
        "critic": Critic(),
    }
    orch = BoundedOrchestrator(
        agents=agents,
        max_rounds=max_rounds,
        agent_timeout=agent_timeout,
    )
    return orch.to_execution_graph(keyword)
