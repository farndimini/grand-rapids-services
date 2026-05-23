"""
intelligent_fallback.py — Smart Provider Selector with Multi-Factor Scoring
=============================================================================
Replaces the naive FALLBACK_CHAIN with an intelligent scoring system that
considers: success rate, latency (p95), estimated cost, and model quality.

Usage:
    from agent_core.intelligent_fallback import IntelligentFallback
    fb = IntelligentFallback()
    provider = fb.select_best_provider(preferred="gpt-4o", budget_priority=True)
    sequence = fb.build_fallback_sequence(preferred="gpt-4o", min_success_rate=0.5)
"""

from __future__ import annotations

import logging
import statistics
import time
from dataclasses import dataclass
from typing import Any

from config import API_KEYS, MODELS
from agent_core.metrics_collector import get_collector

log = logging.getLogger("agent_core.intelligent_fallback")


# ── Provider profiles ──────────────────────────────────────
# Quality score: subjective capability ranking (1-10)
# Cost tier: approximate relative cost (1 = cheapest)

_PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    "anthropic": {"quality": 9.5, "cost_tier": 4, "speed_tier": 3, "reliability": 0.95},
    "openrouter": {"quality": 8.5, "cost_tier": 3, "speed_tier": 3, "reliability": 0.90},
    "groq": {"quality": 7.5, "cost_tier": 1, "speed_tier": 1, "reliability": 0.88},
    "google": {"quality": 8.0, "cost_tier": 2, "speed_tier": 2, "reliability": 0.92},
    "local": {"quality": 6.0, "cost_tier": 1, "speed_tier": 1, "reliability": 1.0},
}


@dataclass
class ProviderScore:
    provider: str
    success_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    estimated_cost_usd: float
    quality_score: float
    composite_score: float
    reason: str


class IntelligentFallback:
    """Smart provider selection based on live metrics + static profiles."""

    def __init__(self):
        self._metrics = get_collector()

    def evaluate_providers(self, window_secs: float = 3600.0) -> list[ProviderScore]:
        """Score all configured providers on multiple dimensions."""
        health = self._metrics.provider_summary(window_secs)
        scores: list[ProviderScore] = []

        for provider, profile in _PROVIDER_PROFILES.items():
            # Skip if no API key (except local)
            if provider != "local" and not API_KEYS.get(provider):
                continue

            stats = health.get(provider, {"ok": 0, "fail": 0, "avg_latency_ms": None, "p95_latency_ms": None, "estimated_cost_usd": 0.0})
            total = stats["ok"] + stats["fail"]
            success_rate = stats["success_rate"] if total > 0 else profile["reliability"]
            avg_lat = stats.get("avg_latency_ms") or 3000.0
            p95_lat = stats.get("p95_latency_ms") or 5000.0
            cost = stats.get("estimated_cost_usd", 0.0)

            # Normalize each factor to 0-1
            reliability_norm = success_rate
            speed_norm = max(0, 1.0 - (p95_lat / 20000))  # 20s = 0
            cost_norm = max(0, 1.0 - (cost * 1000))        # $1 = 0
            quality_norm = profile["quality"] / 10.0

            # Composite: weighted sum (tune as needed)
            composite = (
                reliability_norm * 0.35 +
                speed_norm * 0.25 +
                cost_norm * 0.15 +
                quality_norm * 0.25
            )

            reason = (
                f"success={success_rate:.0%} lat={avg_lat:.0f}ms "
                f"cost=${cost:.4f} quality={profile['quality']}"
            )

            scores.append(ProviderScore(
                provider=provider,
                success_rate=success_rate,
                avg_latency_ms=avg_lat,
                p95_latency_ms=p95_lat,
                estimated_cost_usd=cost,
                quality_score=profile["quality"],
                composite_score=round(composite, 3),
                reason=reason,
            ))

        return sorted(scores, key=lambda x: x.composite_score, reverse=True)

    def select_best_provider(self, preferred: str = "", budget_priority: bool = False,
                             min_success_rate: float = 0.3) -> str | None:
        """Select the best available provider based on current metrics."""
        scored = self.evaluate_providers()
        viable = [s for s in scored if s.success_rate >= min_success_rate]
        if not viable:
            log.warning("[IFB] No viable providers found — returning local")
            return "local"

        if budget_priority:
            # Sort primarily by cost, secondarily by reliability
            viable.sort(key=lambda s: (s.estimated_cost_usd, -s.success_rate))
        else:
            viable.sort(key=lambda s: s.composite_score, reverse=True)

        # Honor preference if it's viable
        if preferred:
            pref_provider = _guess_provider(preferred)
            for v in viable:
                if v.provider == pref_provider:
                    log.info(f"[IFB] Preferred {pref_provider} is viable (score={v.composite_score})")
                    return pref_provider
            log.warning(f"[IFB] Preferred provider {pref_provider} not viable, falling back to best")

        best = viable[0]
        log.info(f"[IFB] Selected {best.provider} (score={best.composite_score}, {best.reason})")
        return best.provider

    def build_fallback_sequence(self, preferred: str = "", budget_priority: bool = False,
                                min_success_rate: float = 0.3) -> list[str]:
        """Build ordered fallback chain using intelligence instead of hardcoded list."""
        scored = self.evaluate_providers()
        viable = [s for s in scored if s.success_rate >= min_success_rate]

        if budget_priority:
            viable.sort(key=lambda s: (s.estimated_cost_usd, -s.success_rate))
        else:
            viable.sort(key=lambda s: s.composite_score, reverse=True)

        sequence = [s.provider for s in viable]

        # Ensure preferred is first if viable
        if preferred:
            pref_p = _guess_provider(preferred)
            if pref_p in sequence:
                sequence.remove(pref_p)
                sequence.insert(0, pref_p)

        return sequence

    def explain(self, preferred: str = "") -> list[dict]:
        """Return human-readable provider rankings for diagnostics."""
        scored = self.evaluate_providers()
        if preferred:
            pref_p = _guess_provider(preferred)
            for s in scored:
                if s.provider == pref_p:
                    s.reason += " [PREFERRED]"
        return [
            {
                "provider": s.provider,
                "composite": s.composite_score,
                "success_rate": s.success_rate,
                "latency_ms": s.avg_latency_ms,
                "cost_usd": s.estimated_cost_usd,
                "reason": s.reason,
            }
            for s in sorted(scored, key=lambda x: x.composite_score, reverse=True)
        ]


def _guess_provider(model: str) -> str:
    """Resolve model name to provider."""
    if model in MODELS:
        return MODELS[model][0]
    model_l = model.lower()
    if "claude" in model_l:
        return "anthropic"
    if "gpt" in model_l or "openai" in model_l:
        return "openrouter"
    if "groq" in model_l:
        return "groq"
    if "gemini" in model_l:
        return "google"
    return "local"
