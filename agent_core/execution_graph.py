"""
agent_core/execution_graph.py — Execution Graph & Tracing
===========================================================
Represents a pipeline as a directed acyclic graph (DAG) of tasks
with dependencies, enabling:
  • Parallel execution of independent stages
  • Dependency-based sequencing
  • Execution tracing and telemetry
  • Resumable checkpoints

Usage:
    from agent_core.execution_graph import ExecutionGraph, TaskNode
    graph = ExecutionGraph("pipeline-1")
    graph.add_node("serp", fn=fetch_serp)
    graph.add_node("analyze", fn=analyze, depends_on=["serp"])
    graph.add_node("write", fn=write, depends_on=["analyze"])
    results = await graph.execute()
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from agent_core.metrics_collector import get_collector

log = logging.getLogger("agent_core.execution_graph")


TaskFn = Callable[..., Awaitable[Any]]


@dataclass
class TaskNode:
    name: str
    fn: TaskFn
    args: tuple = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    timeout: float = 90.0
    retries: int = 2
    result: Any = None
    exception: Exception | None = None
    started_at: float = 0.0
    finished_at: float = 0.0
    state: str = "pending"  # pending | running | success | failed | skipped


class ExecutionGraph:
    """DAG-based pipeline executor with async support."""

    def __init__(self, graph_id: str):
        self.id = graph_id
        self._nodes: dict[str, TaskNode] = {}
        self._lock = asyncio.Lock()

    def add_node(
        self,
        name: str,
        fn: TaskFn,
        *args,
        depends_on: list[str] | None = None,
        timeout: float = 90.0,
        retries: int = 2,
        **kwargs,
    ) -> TaskNode:
        if name in self._nodes:
            raise ValueError(f"Node '{name}' already exists")
        node = TaskNode(
            name=name,
            fn=fn,
            args=args,
            kwargs=kwargs,
            depends_on=depends_on or [],
            timeout=timeout,
            retries=retries,
        )
        self._nodes[name] = node
        return node

    def _topological_order(self) -> list[set[str]]:
        """Return layers of node names that can execute in parallel."""
        remaining = set(self._nodes.keys())
        completed: set[str] = set()
        layers: list[set[str]] = []
        while remaining:
            layer = {
                n for n in remaining
                if all(d in completed for d in self._nodes[n].depends_on)
            }
            if not layer:
                raise RuntimeError("Circular dependency detected in execution graph")
            layers.append(layer)
            completed |= layer
            remaining -= layer
        return layers

    async def execute(self, semaphore: asyncio.Semaphore | None = None) -> dict[str, Any]:
        """Execute the DAG layer by layer with bounded concurrency.

        Returns a dict mapping node name → result or exception.
        """
        sem = semaphore or asyncio.Semaphore(len(self._nodes))
        layers = self._topological_order()
        results: dict[str, Any] = {}

        for layer in layers:
            coros = [self._run_node(name, sem) for name in layer]
            layer_results = await asyncio.gather(*coros, return_exceptions=True)
            for name, res in zip(layer, layer_results):
                node = self._nodes[name]
                if isinstance(res, Exception):
                    node.exception = res
                    results[name] = res
                    log.error(f"[ExecGraph] Node '{name}' failed: {res}")
                else:
                    node.result = res
                    results[name] = res
                    log.debug(f"[ExecGraph] Node '{name}' completed")

        return results

    async def _run_node(self, name: str, sem: asyncio.Semaphore) -> Any:
        async with sem:
            node = self._nodes[name]
            node.state = "running"
            node.started_at = time.perf_counter()
            t0 = time.perf_counter()
            for attempt in range(node.retries + 1):
                try:
                    result = await asyncio.wait_for(
                        node.fn(*node.args, **node.kwargs),
                        timeout=node.timeout,
                    )
                    node.result = result
                    node.state = "success"
                    latency_ms = (time.perf_counter() - t0) * 1000
                    get_collector().record_stage(f"execgraph_{name}", latency_ms, True)
                    return result
                except asyncio.TimeoutError:
                    if attempt == node.retries:
                        node.state = "failed"
                        latency_ms = (time.perf_counter() - t0) * 1000
                        get_collector().record_stage(f"execgraph_{name}", latency_ms, False, error="timeout")
                        raise
                    delay = 1.5 * (2 ** attempt)
                    await asyncio.sleep(delay)
                except Exception as e:
                    if attempt == node.retries:
                        node.state = "failed"
                        latency_ms = (time.perf_counter() - t0) * 1000
                        get_collector().record_stage(f"execgraph_{name}", latency_ms, False, error=str(e)[:80])
                        raise
                    delay = 1.5 * (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(delay)
            return None  # unreachable

    def trace(self) -> list[dict[str, Any]]:
        """Return execution trace for all nodes."""
        return [
            {
                "name": n.name,
                "state": n.state,
                "depends_on": n.depends_on,
                "latency_ms": round((n.finished_at - n.started_at) * 1000, 1) if n.finished_at else None,
                "error": str(n.exception) if n.exception else None,
            }
            for n in self._nodes.values()
        ]

    def visualize_text(self) -> str:
        """ASCII visualization of the execution graph."""
        lines = [f"Execution Graph: {self.id}", "─" * 40]
        for name, node in self._nodes.items():
            deps = f" (after: {', '.join(node.depends_on)})" if node.depends_on else ""
            status = "✓" if node.state == "success" else "✗" if node.state == "failed" else "○"
            lines.append(f"  [{status}] {name}{deps}")
        return "\n".join(lines)
