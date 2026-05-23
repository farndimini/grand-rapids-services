from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from typing import Any


class GscDataSimulator:
    """Generates synthetic 30-day ranking/CTR/impression data for testing."""

    @staticmethod
    def simulate_ranking_trajectory(
        keyword: str,
        days: int = 30,
        pattern: str = "stable",
        start_position: float = 15.0,
        noise: float = 1.5,
        seed: int | None = None,
    ) -> list[dict]:
        rng = random.Random(seed)
        positions = []
        pos = start_position

        for day in range(days):
            if pattern == "improving":
                pos = start_position - (day / days) * 10
                pos += rng.gauss(0, noise)
            elif pattern == "declining":
                pos = start_position + (day / days) * 10
                pos += rng.gauss(0, noise)
            elif pattern == "volatile":
                pos = start_position + rng.gauss(0, noise * 3)
                pos += math.sin(day * 0.5) * 3
            elif pattern == "plateau":
                if day < days * 0.3:
                    pos = start_position - (day / (days * 0.3)) * 8
                else:
                    pos = start_position - 8 + rng.gauss(0, noise * 0.5)
            elif pattern == "crash":
                if day < days * 0.7:
                    pos = start_position - 5 + rng.gauss(0, noise * 0.5)
                else:
                    pos = start_position + 20 + rng.gauss(0, noise)
            else:
                pos = start_position + rng.gauss(0, noise * 0.5)

            pos = max(1.0, min(100.0, pos))
            date = (datetime.now() - timedelta(days=days - 1 - day)).strftime("%Y-%m-%d")
            positions.append({"keyword": keyword, "date": date, "position": round(pos, 1)})

        return positions

    @staticmethod
    def simulate_ctr_from_positions(
        positions: list[dict],
        noise: float = 0.3,
        seed: int | None = None,
    ) -> list[dict]:
        rng = random.Random(seed if seed is not None else 42)
        from agent_core.gsc_feedback.ctr_tracker import CtrTracker
        tracker = CtrTracker()

        results = []
        for entry in positions:
            pos = entry["position"]
            expected = tracker.expected_ctr_for_position(pos)
            multiplier = max(0.3, rng.gauss(1.0, noise * 0.3))
            ctr = expected * multiplier
            ctr = max(0.1, min(60.0, ctr))

            impressions = int(max(10, rng.gauss(500 / max(1, pos), 100)))
            clicks = int(impressions * ctr / 100)

            results.append({
                **entry,
                "ctr": round(ctr, 2),
                "impressions": impressions,
                "clicks": clicks,
            })
        return results

    @staticmethod
    def inject_anomaly(
        data: list[dict],
        day_index: int,
        anomaly_type: str = "ranking_spike",
        severity: float = 3.0,
    ) -> list[dict]:
        if day_index >= len(data):
            return data

        modified = data.copy()
        entry = dict(modified[day_index])

        if anomaly_type == "ranking_spike":
            entry["position"] = entry.get("position", 15) + severity * 10
        elif anomaly_type == "ctr_drop":
            entry["ctr"] = entry.get("ctr", 5) / severity
        elif anomaly_type == "impression_surge":
            entry["impressions"] = int(entry.get("impressions", 500) * severity)

        modified[day_index] = entry
        return modified

    @staticmethod
    def inject_decay_signal(
        data: list[dict],
        start_day: int,
        decay_rate: float = 0.5,
    ) -> list[dict]:
        modified = data.copy()
        for i in range(start_day, len(modified)):
            days_since = i - start_day
            entry = dict(modified[i])
            if "position" in entry and entry["position"] is not None:
                entry["position"] = entry["position"] + days_since * decay_rate
            modified[i] = entry
        return modified

    @staticmethod
    def generate_30day_dataset(
        keywords: list[str],
        patterns: dict[str, str] | None = None,
        base_seed: int = 42,
    ) -> dict[str, list[dict]]:
        rng = random.Random(base_seed)
        dataset = {}

        for kw in keywords:
            pattern = patterns.get(kw, "stable") if patterns else rng.choice(
                ["stable", "improving", "declining", "volatile", "plateau"]
            )
            start_pos = rng.uniform(3, 25)
            seed = base_seed + hash(kw) % 10000

            positions = GscDataSimulator.simulate_ranking_trajectory(
                keyword=kw, days=30, pattern=pattern,
                start_position=start_pos, seed=seed,
            )
            enriched = GscDataSimulator.simulate_ctr_from_positions(
                positions, seed=seed + 1,
            )
            dataset[kw] = enriched

        return dataset

    @staticmethod
    def simulate_gsc_response(
        keyword: str, days: int = 28, avg_position: float = 10.0, pattern: str = "stable"
    ) -> dict:
        positions = GscDataSimulator.simulate_ranking_trajectory(
            keyword, days, pattern, start_position=avg_position,
        )
        enriched = GscDataSimulator.simulate_ctr_from_positions(positions)

        latest = enriched[-1]
        avg_pos = sum(p["position"] for p in enriched) / len(enriched)

        return {
            "keyword": keyword,
            "source": "simulated",
            "fetched_at": datetime.now().isoformat(),
            "position": round(avg_pos, 1),
            "ctr": latest["ctr"],
            "impressions": latest["impressions"],
            "clicks": latest["clicks"],
            "_daily": enriched,
        }

    @staticmethod
    def generate_reward_stable_pattern(
        keyword: str, days: int = 30, target_reward: float = 0.5
    ) -> list[dict]:
        daily_rewards = []
        for day in range(days):
            noise = random.gauss(0, 0.1)
            reward = max(-1.0, min(1.0, target_reward + noise))
            daily_rewards.append({
                "keyword": keyword,
                "timestamp": (datetime.now() - timedelta(days=days - 1 - day)).isoformat(),
                "total": round(reward, 3),
                "position_component": round(max(-1, min(1, target_reward * 0.6 + noise * 0.5)), 3),
                "ctr_component": round(max(-1, min(1, target_reward * 0.3 + noise * 0.3)), 3),
                "trajectory_component": round(max(-1, min(1, 0.2 + noise * 0.2)), 3),
                "stability_component": round(max(-1, min(1, 0.3 + noise * 0.1)), 3),
                "impression_component": round(max(-1, min(1, target_reward * 0.2 + noise * 0.2)), 3),
            })
        return daily_rewards

    @staticmethod
    def generate_reward_unstable_pattern(
        keyword: str, days: int = 30
    ) -> list[dict]:
        daily_rewards = []
        base = 0.0
        for day in range(days):
            if day < 10:
                base = 0.6 - day * 0.02
            elif day < 20:
                base = -0.2 - (day - 10) * 0.04
            else:
                base = -0.6 + (day - 20) * 0.03
            noise = random.gauss(0, 0.15)
            reward = max(-1.0, min(1.0, base + noise))
            daily_rewards.append({
                "keyword": keyword,
                "timestamp": (datetime.now() - timedelta(days=days - 1 - day)).isoformat(),
                "total": round(reward, 3),
                "position_component": round(max(-1, min(1, base * 0.6 + noise * 0.5)), 3),
                "ctr_component": round(max(-1, min(1, base * 0.3 + noise * 0.3)), 3),
                "trajectory_component": round(max(-1, min(1, -0.3 + noise * 0.2)), 3),
                "stability_component": round(max(-1, min(1, -0.2 + noise * 0.2)), 3),
                "impression_component": round(max(-1, min(1, base * 0.2 + noise * 0.3)), 3),
            })
        return daily_rewards
