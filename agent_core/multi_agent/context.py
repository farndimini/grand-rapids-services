from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SharedContext:
    keyword: str
    topic: str = ""
    niche: str = ""
    target_audience: str = ""
    round: int = 0
    max_rounds: int = 3

    research_data: dict[str, Any] = field(default_factory=dict)
    strategy: dict[str, Any] = field(default_factory=dict)
    draft: str = ""
    optimized_draft: str = ""
    critique: dict[str, Any] = field(default_factory=dict)

    telemetry: list[dict[str, Any]] = field(default_factory=list)
    cost_total: float = 0.0
    latency_total: float = 0.0
    errors: list[str] = field(default_factory=list)
    deadlock_rounds: int = 0

    def add_telemetry(self, entry: dict[str, Any]) -> None:
        entry["_timestamp"] = time.time()
        self.telemetry.append(entry)
        self.cost_total += entry.get("cost", 0.0)
        self.latency_total += entry.get("latency_ms", 0.0)

    def add_error(self, agent: str, message: str) -> None:
        self.errors.append(f"[{agent}] {message}")

    def snapshot(self) -> dict[str, Any]:
        return {
            "keyword": self.keyword,
            "round": self.round,
            "has_research": bool(self.research_data),
            "has_strategy": bool(self.strategy),
            "has_draft": bool(self.draft),
            "has_optimized": bool(self.optimized_draft),
            "has_critique": bool(self.critique),
            "cost_total": round(self.cost_total, 4),
            "latency_total": round(self.latency_total, 2),
            "error_count": len(self.errors),
            "telemetry_count": len(self.telemetry),
        }

    def snapshot_business(self) -> dict[str, Any]:
        return {
            "research_data": self.research_data,
            "strategy": self.strategy,
            "draft": self.draft,
            "optimized_draft": self.optimized_draft,
            "critique": self.critique,
        }

    def is_stale(self, other: SharedContext) -> bool:
        return self.snapshot_business() == other.snapshot_business()
