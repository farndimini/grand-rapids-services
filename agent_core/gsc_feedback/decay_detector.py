from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from typing import Any

from agent_core.gsc_feedback.ranking_history import RankingHistory, Trajectory
from agent_core.gsc_feedback.ctr_tracker import CtrTracker

log = logging.getLogger("gsc_feedback.decay_detector")


@dataclass
class DecaySignal:
    keyword: str
    score: float
    severity: str  # none | mild | moderate | severe | critical
    direction: str
    components: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    triggered_rewrite: bool = False
    rewrite_priority: str = "none"

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "score": round(self.score, 3),
            "severity": self.severity,
            "direction": self.direction,
            "components": self.components,
            "reasons": self.reasons,
            "triggered_rewrite": self.triggered_rewrite,
            "rewrite_priority": self.rewrite_priority,
        }


class DecayDetector:
    def __init__(
        self,
        ranking_decay_weight: float = 0.40,
        ctr_decay_weight: float = 0.30,
        impression_decay_weight: float = 0.15,
        volatility_penalty_weight: float = 0.15,
        rewrite_threshold: float = 0.35,
    ):
        self._ranking_history = RankingHistory()
        self._ctr_tracker = CtrTracker()
        self._weights = {
            "ranking": ranking_decay_weight,
            "ctr": ctr_decay_weight,
            "impressions": impression_decay_weight,
            "volatility": volatility_penalty_weight,
        }
        self._rewrite_threshold = rewrite_threshold

    def analyze(
        self, keyword: str, history: list | None = None, days: int = 28
    ) -> DecaySignal | None:
        if history is None:
            history = self._ranking_history.get_history(keyword, days)

        positions = [h.position for h in history if h.position is not None] if history else []

        ranking_decay = self._detect_ranking_decay(history, keyword, days)
        ctr_decay = self._detect_ctr_decay(history, keyword, days)
        impression_decay = self._detect_impression_decay(history, keyword, days)
        volatility = self._detect_volatility(positions)

        components = {
            "ranking_slope": ranking_decay["score"],
            "ctr_vs_benchmark": ctr_decay["score"],
            "impression_trend": impression_decay["score"],
            "volatility": volatility["score"],
        }

        decay_score = (
            ranking_decay["score"] * self._weights["ranking"]
            + ctr_decay["score"] * self._weights["ctr"]
            + impression_decay["score"] * self._weights["impressions"]
            + volatility["score"] * self._weights["volatility"]
        )

        decay_score = max(0.0, min(1.0, decay_score))

        reasons = []
        if ranking_decay["score"] > 0.3:
            reasons.append(ranking_decay.get("reason", "Ranking position declining"))
        if ctr_decay["score"] > 0.3:
            reasons.append(ctr_decay.get("reason", "CTR below benchmark"))
        if impression_decay["score"] > 0.3:
            reasons.append(impression_decay.get("reason", "Impression volume dropping"))
        if volatility["score"] > 0.3:
            reasons.append(volatility.get("reason", "High ranking volatility"))

        if decay_score < 0.15:
            severity = "none"
            direction = "stable"
        elif decay_score < 0.30:
            severity = "mild"
            direction = "stable" if len(reasons) <= 1 else "declining"
        elif decay_score < 0.50:
            severity = "moderate"
            direction = "declining"
        elif decay_score < 0.75:
            severity = "severe"
            direction = "declining"
        else:
            severity = "critical"
            direction = "declining"

        triggered = decay_score >= self._rewrite_threshold
        if decay_score >= 0.60:
            priority = "high"
        elif decay_score >= 0.40:
            priority = "medium"
        elif triggered:
            priority = "low"
        else:
            priority = "none"

        return DecaySignal(
            keyword=keyword,
            score=decay_score,
            severity=severity,
            direction=direction,
            components=components,
            reasons=reasons,
            triggered_rewrite=triggered,
            rewrite_priority=priority,
        )

    def _detect_ranking_decay(self, history: list | None, keyword: str, days: int) -> dict:
        trajectory = self._ranking_history.analyze_trajectory(keyword, days)
        if trajectory is None and history and len([h for h in history if h.position is not None]) >= 3:
            from agent_core.gsc_feedback.ranking_history import Trajectory
            positions = [h.position for h in history if h.position is not None]
            n = len(positions)
            slope = (positions[-1] - positions[0]) / max(1, n)
            import statistics
            volatility = statistics.stdev(positions) if n >= 2 else 0.0
            trajectory = Trajectory(
                direction="declining" if slope > 0.2 else "improving" if slope < -0.2 else "stable",
                slope=slope, volatility=volatility, momentum=positions[-1] - positions[-min(3, n)],
                period_days=days, start_position=positions[0], end_position=positions[-1],
                best_position=min(positions), worst_position=max(positions),
                confidence=min(1.0, n / 28),
            )
        if trajectory is None:
            return {"score": 0.0, "reason": "Insufficient ranking data"}

        if trajectory.direction == "improving":
            slope_score = 0.0
        elif trajectory.direction == "declining":
            slope_score = min(1.0, abs(trajectory.slope) / 2.0)
        elif trajectory.direction == "volatile":
            slope_score = 0.4
        else:
            slope_score = 0.1

        decay_score = slope_score * 0.6 + (1.0 - trajectory.confidence) * 0.4

        reason = None
        if trajectory.direction == "declining":
            reason = f"Ranking declining (slope={trajectory.slope:.2f}, {trajectory.start_position}->{trajectory.end_position})"
        elif trajectory.direction == "volatile":
            reason = f"Ranking volatile (std={trajectory.volatility:.1f})"

        return {"score": round(decay_score, 3), "reason": reason}

    def _detect_ctr_decay(self, history: list | None, keyword: str, days: int) -> dict:
        ctrs = [h.ctr for h in history if h is not None and h.ctr is not None] if history else []
        positions = [h.position for h in history if h is not None and h.position is not None] if history else []

        if not ctrs or not positions:
            return {"score": 0.0, "reason": "No CTR data"}

        avg_ctr = statistics.mean(ctrs)
        avg_pos = statistics.mean(positions)
        expected = self._ctr_tracker.expected_ctr_for_position(avg_pos)
        ratio = avg_ctr / expected if expected > 0 else 1.0

        if len(ctrs) >= 4:
            mid = len(ctrs) // 2
            first_half = statistics.mean(ctrs[:mid])
            second_half = statistics.mean(ctrs[mid:])
            if second_half < first_half * 0.85:
                trend = "declining"
            elif second_half > first_half * 1.15:
                trend = "improving"
            else:
                trend = "stable"
        else:
            trend = "stable"

        if ratio >= 1.0 and trend != "declining":
            score = 0.0
        elif ratio >= 0.8:
            score = 0.2
        elif ratio >= 0.6:
            score = 0.4
        elif ratio >= 0.4:
            score = 0.6
        elif ratio >= 0.2:
            score = 0.8
        else:
            score = 1.0

        if trend == "declining":
            score = min(1.0, score + 0.2)
        elif trend == "improving":
            score = max(0.0, score - 0.15)

        goal_msg = None
        if score > 0.3:
            goal_msg = f"CTR {avg_ctr:.2f}% vs expected {expected:.2f}% (ratio={ratio:.2f})"

        return {"score": round(score, 3), "reason": goal_msg}

    def _detect_impression_decay(self, history: list | None, keyword: str, days: int) -> dict:
        imps = [h.impressions for h in history if h is not None and h.impressions is not None] if history else []

        if len(imps) < 3:
            return {"score": 0.0, "reason": None}

        mid = len(imps) // 2
        first_half = statistics.mean(imps[:mid])
        second_half = statistics.mean(imps[mid:])

        if second_half > first_half * 1.2:
            return {"score": 0.0, "reason": None}
        elif second_half > first_half * 0.8:
            return {"score": 0.1, "reason": None}
        else:
            avg_imps = sum(imps) / len(imps)
            if avg_imps > 100:
                return {"score": 0.6, "reason": f"Impressions shrinking ({first_half:.0f} -> {second_half:.0f})"}
            return {"score": 0.3, "reason": "Impressions slightly declining"}

    def _detect_volatility(self, positions: list[float]) -> dict:
        if len(positions) < 5:
            return {"score": 0.0, "reason": None}

        mean_pos = statistics.mean(positions)
        std = statistics.stdev(positions)

        cv = std / mean_pos if mean_pos > 0 else 0

        if cv < 0.1:
            score = 0.0
        elif cv < 0.2:
            score = 0.2
        elif cv < 0.35:
            score = 0.5
        elif cv < 0.5:
            score = 0.7
        else:
            score = 0.9

        reason = None
        if score > 0.4:
            reason = f"Ranking volatility CV={cv:.2f}"

        return {"score": round(score, 3), "reason": reason}

    def should_trigger_rewrite(
        self, decay_signal: DecaySignal, threshold: float | None = None
    ) -> bool:
        t = threshold if threshold is not None else self._rewrite_threshold
        return decay_signal.score >= t

    def batch_analyze(self, keywords: list[str]) -> list[DecaySignal]:
        return [self.analyze(kw) for kw in keywords if self.analyze(kw) is not None]
