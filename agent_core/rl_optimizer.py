"""
agent_core/rl_optimizer.py — RL-Like Optimization Foundation
=============================================================
Provides reinforcement-learning-style foundations:
  • Reward calibration engine (combines all signals into -1..+1)
  • Strategy evolution tracking (prompts, structures, openers, CTAs)
  • Success pattern extraction
  • Controlled mutation / A-B experimentation
  • Exploitation vs exploration balancing (epsilon-greedy)

Reward combines:
  - quality score (0-100)
  - ranking prediction (top-3 probability)
  - cost efficiency (inverse of cost per article)
  - latency efficiency
  - rewrite count penalty
  - SERP alignment
  - factual confidence proxy

Usage:
    from agent_core.rl_optimizer import RewardEngine, StrategyEvolution
    reward = RewardEngine().compute(quality=85, ranking_pred=30, cost_usd=0.005, latency_ms=2000, rewrites=0)
    # Returns ~0.7
"""

from __future__ import annotations

import json
import logging
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("agent_core.rl_optimizer")

EVOLUTION_DIR = Path(__file__).resolve().parent.parent / "evolution"


# ──────────────────────────────────────────────────────────────
#  Reward Engine
# ──────────────────────────────────────────────────────────────

@dataclass
class RewardSignal:
    total_reward: float = 0.0   # -1.0 to +1.0
    components: dict[str, float] = field(default_factory=dict)
    explanation: str = ""


class RewardEngine:
    """Calibrates a unified reward signal from multiple pipeline outcomes."""

    def compute(
        self,
        quality: float = 0.0,           # 0-100 article quality
        ranking_pred: float = 0.0,      # top-3 probability 0-100
        cost_usd: float = 0.0,          # total API cost
        latency_ms: float = 0.0,        # wall-clock latency
        rewrites: int = 0,              # number of rewrite attempts
        serp_alignment: float = 0.0,    # 0-1 SERP alignment
        factual_confidence: float = 1.0, # 0-1 (proxy: schema completeness)
        word_count: int = 0,
    ) -> RewardSignal:
        """Calculate unified reward in range [-1, +1]."""
        # Normalize each component to roughly -1..+1
        r_quality = (quality - 50) / 50.0  # 0→-1, 50→0, 100→+1
        r_ranking = (ranking_pred - 50) / 50.0  # same

        # Cost: optimal around $0.005, penalizes heavily above $0.05
        r_cost = 1.0 - min(1.0, cost_usd / 0.05)

        # Latency: optimal < 3s, penalizes above 30s
        r_latency = 1.0 - min(1.0, latency_ms / 30000.0)

        # Rewrite penalty: 0 rewrites = ideal, each rewrite reduces reward
        r_rewrites = max(-1.0, 1.0 - rewrites * 0.4)

        # SERP alignment: directly 0-1 scaled
        r_serp = (serp_alignment - 0.5) * 2.0

        # Factual confidence: penalty for low confidence
        r_factual = (factual_confidence - 0.5) * 2.0

        # Word count sweet spot: 1500-2500 words
        if 1500 <= word_count <= 2500:
            r_depth = 1.0
        elif 1000 <= word_count <= 3000:
            r_depth = 0.5
        else:
            r_depth = -0.5

        # Weighted sum
        weights = {
            "quality": 0.25,
            "ranking": 0.20,
            "cost": 0.15,
            "latency": 0.10,
            "rewrites": 0.10,
            "serp": 0.10,
            "factual": 0.05,
            "depth": 0.05,
        }
        components = {
            "quality": r_quality,
            "ranking": r_ranking,
            "cost": r_cost,
            "latency": r_latency,
            "rewrites": r_rewrites,
            "serp": r_serp,
            "factual": r_factual,
            "depth": r_depth,
        }
        total = sum(components[k] * weights[k] for k in weights)
        total = max(-1.0, min(1.0, total))

        explanations = []
        if r_quality < 0:
            explanations.append("quality low")
        if r_rewrites < 0.5:
            explanations.append(f"{rewrites} rewrites needed")
        if r_cost < 0.5:
            explanations.append("cost high")
        if r_ranking < 0:
            explanations.append("ranking potential low")

        return RewardSignal(
            total_reward=round(total, 3),
            components={k: round(v, 3) for k, v in components.items()},
            explanation="; ".join(explanations) if explanations else "all signals strong",
        )


# ──────────────────────────────────────────────────────────────
#  Strategy Evolution Tracker
# ──────────────────────────────────────────────────────────────

@dataclass
class StrategyPattern:
    pattern_type: str          # "opener", "structure", "cta", "heading", "prompt"
    value: str
    avg_reward: float
    occurrences: int
    last_used: str


class StrategyEvolution:
    """Tracks which strategies, prompts, and patterns produce high reward."""

    def __init__(self, data_dir: Path | str = EVOLUTION_DIR):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._patterns_file = self._dir / "patterns.json"
        self._patterns: list[StrategyPattern] = self._load_patterns()
        self._epsilon: float = 0.2  # exploration rate

    def _load_patterns(self) -> list[StrategyPattern]:
        if not self._patterns_file.exists():
            return []
        try:
            data = json.loads(self._patterns_file.read_text(encoding="utf-8"))
            return [StrategyPattern(**p) for p in data]
        except (json.JSONDecodeError, TypeError):
            return []

    def _save_patterns(self) -> None:
        payload = [
            {
                "pattern_type": p.pattern_type,
                "value": p.value,
                "avg_reward": p.avg_reward,
                "occurrences": p.occurrences,
                "last_used": p.last_used,
            }
            for p in self._patterns
        ]
        self._patterns_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def record_outcome(
        self,
        pattern_type: str,
        value: str,
        reward: float,
    ) -> None:
        """Update pattern statistics with a new reward observation."""
        for p in self._patterns:
            if p.pattern_type == pattern_type and p.value == value:
                # Update running average
                p.avg_reward = (p.avg_reward * p.occurrences + reward) / (p.occurrences + 1)
                p.occurrences += 1
                p.last_used = datetime.now().isoformat()
                self._save_patterns()
                return

        # New pattern
        self._patterns.append(StrategyPattern(
            pattern_type=pattern_type,
            value=value,
            avg_reward=reward,
            occurrences=1,
            last_used=datetime.now().isoformat(),
        ))
        self._save_patterns()

    def recommend(self, pattern_type: str, top_n: int = 3) -> list[StrategyPattern]:
        """Epsilon-greedy recommendation: exploit best N, or explore randomly."""
        candidates = [p for p in self._patterns if p.pattern_type == pattern_type]
        if not candidates:
            return []

        if random.random() < self._epsilon:
            # Exploration: random pick weighted by recency (more recent = more likely)
            weights = []
            now = datetime.now()
            for c in candidates:
                try:
                    dt = datetime.fromisoformat(c.last_used)
                    age_days = (now - dt).days
                    weights.append(max(0.1, 1.0 / (age_days + 1)))
                except ValueError:
                    weights.append(1.0)
            picked = random.choices(candidates, weights=weights, k=min(top_n, len(candidates)))
            return picked

        # Exploitation: highest avg_reward
        candidates.sort(key=lambda p: p.avg_reward, reverse=True)
        return candidates[:top_n]

    def get_mutation(self, pattern_type: str, base_value: str) -> str:
        """Generate a controlled mutation of a base pattern for A/B testing."""
        mutations = {
            "opener": [
                lambda v: v.replace("2026", "2027"),
                lambda v: v.replace("best", "top-rated"),
                lambda v: v + " (Updated for " + datetime.now().strftime("%B %Y") + ")",
            ],
            "heading": [
                lambda v: v.replace("Guide", "Complete Guide"),
                lambda v: v.replace("Review", "Honest Review"),
                lambda v: "Ultimate " + v,
            ],
            "cta": [
                lambda v: v.replace("try", "get started with"),
                lambda v: v + " — free trial available",
            ],
        }
        fns = mutations.get(pattern_type, [lambda v: v])
        fn = random.choice(fns)
        return fn(base_value)

    def set_epsilon(self, value: float) -> None:
        self._epsilon = max(0.0, min(1.0, value))

    def summary(self) -> dict[str, Any]:
        by_type: dict[str, list[float]] = {}
        for p in self._patterns:
            by_type.setdefault(p.pattern_type, []).append(p.avg_reward)
        return {
            "total_patterns": len(self._patterns),
            "epsilon": self._epsilon,
            "by_type": {
                t: {
                    "count": len(vals),
                    "avg_reward": round(statistics.mean(vals), 3) if vals else 0,
                    "best": round(max(vals), 3) if vals else 0,
                }
                for t, vals in by_type.items()
            },
        }


# ──────────────────────────────────────────────────────────────
#  Convenience entry point
# ──────────────────────────────────────────────────────────────

def compute_reward(**kwargs) -> RewardSignal:
    """Quick reward calculation."""
    return RewardEngine().compute(**kwargs)
