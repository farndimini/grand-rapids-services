from __future__ import annotations

import json
import logging
import statistics
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from agent_core.gsc_feedback.ranking_history import RankingHistory, Trajectory

log = logging.getLogger("gsc_feedback.reward_generator")

DB_PATH = Path(__file__).resolve().parent.parent.parent / "metrics.db"


@dataclass
class RewardSignal:
    keyword: str
    timestamp: str
    total: float
    position_component: float
    ctr_component: float
    trajectory_component: float
    stability_component: float
    impression_component: float
    components: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "timestamp": self.timestamp,
            "total": round(self.total, 3),
            "position": round(self.position_component, 3),
            "ctr": round(self.ctr_component, 3),
            "trajectory": round(self.trajectory_component, 3),
            "stability": round(self.stability_component, 3),
            "impressions": round(self.impression_component, 3),
            "components": self.components,
            "metadata": self.metadata,
        }


class GscRewardGenerator:
    def __init__(self):
        self._ranking_history = RankingHistory()
        self._store = RewardStore()

    def generate(
        self,
        keyword: str,
        history: list | None = None,
        days: int = 28,
    ) -> RewardSignal:
        if history is None:
            history = self._ranking_history.get_history(keyword, days)

        positions = [h.position for h in history if h.position is not None]
        ctrs = [h.ctr for h in history if h.ctr is not None]
        imps = [h.impressions for h in history if h.impressions is not None]

        pos_reward = self._position_reward(positions)
        ctr_reward = self._ctr_reward(ctrs, positions)
        traj_reward = self._trajectory_reward(history, days)
        stab_reward = self._stability_reward(positions)
        imp_reward = self._impression_reward(imps)

        weights = {"position": 0.30, "ctr": 0.25, "trajectory": 0.20, "stability": 0.10, "impressions": 0.15}

        total = (
            pos_reward * weights["position"]
            + ctr_reward * weights["ctr"]
            + traj_reward * weights["trajectory"]
            + stab_reward * weights["stability"]
            + imp_reward * weights["impressions"]
        )

        total = max(-1.0, min(1.0, total))

        return RewardSignal(
            keyword=keyword,
            timestamp=datetime.now().isoformat(),
            total=total,
            position_component=pos_reward,
            ctr_component=ctr_reward,
            trajectory_component=traj_reward,
            stability_component=stab_reward,
            impression_component=imp_reward,
            components={
                "position_reward": round(pos_reward, 3),
                "ctr_reward": round(ctr_reward, 3),
                "trajectory_reward": round(traj_reward, 3),
                "stability_reward": round(stab_reward, 3),
                "impression_reward": round(imp_reward, 3),
                "weights": weights,
            },
            metadata={"days": days, "data_points": len(positions)},
        )

    def _position_reward(self, positions: list[float]) -> float:
        if not positions:
            return 0.0
        avg = statistics.mean(positions)
        if avg <= 1:
            return 1.0
        elif avg <= 3:
            return 0.8
        elif avg <= 5:
            return 0.6
        elif avg <= 10:
            return 0.3
        elif avg <= 20:
            return 0.0
        elif avg <= 30:
            return -0.3
        elif avg <= 50:
            return -0.6
        else:
            return -0.8

    def _ctr_reward(self, ctrs: list[float], positions: list[float]) -> float:
        if not ctrs or not positions:
            return 0.0
        from agent_core.gsc_feedback.ctr_tracker import CtrTracker
        tracker = CtrTracker()
        ratios = []
        for ctr, pos in zip(ctrs, positions):
            if pos is not None and ctr is not None:
                expected = tracker.expected_ctr_for_position(pos)
                ratios.append(ctr / expected if expected > 0 else 1.0)

        if not ratios:
            return 0.0

        avg_ratio = statistics.mean(ratios)
        if avg_ratio >= 1.5:
            return 1.0
        elif avg_ratio >= 1.0:
            return 0.5
        elif avg_ratio >= 0.7:
            return 0.0
        elif avg_ratio >= 0.4:
            return -0.5
        else:
            return -0.8

    def _trajectory_reward(self, history: list | None, days: int) -> float:
        positions = [h.position for h in history if h is not None and h.position is not None] if history else []
        if len(positions) < 3:
            return 0.0

        n = len(positions)
        slope = (positions[-1] - positions[0]) / max(1, n)
        volatility = statistics.stdev(positions) if n >= 2 else 0.0
        mean_p = statistics.mean(positions)
        cv = volatility / mean_p if mean_p > 0 else 0

        if slope < -0.1:
            return min(1.0, abs(slope) * 2.0)
        elif slope > 0.1:
            return -min(1.0, abs(slope) * 2.0)
        elif cv > 0.2:
            return -0.3
        else:
            return 0.2

    def _stability_reward(self, positions: list[float]) -> float:
        if len(positions) < 3:
            return 0.0
        std = statistics.stdev(positions)
        mean_p = statistics.mean(positions)
        cv = std / mean_p if mean_p > 0 else 0

        if cv < 0.05:
            return 0.5
        elif cv < 0.10:
            return 0.3
        elif cv < 0.20:
            return 0.0
        elif cv < 0.35:
            return -0.3
        else:
            return -0.6

    def _impression_reward(self, imps: list[int]) -> float:
        if len(imps) < 3:
            return 0.0
        first = statistics.mean(imps[:len(imps)//2])
        second = statistics.mean(imps[len(imps)//2:])

        if second > first * 1.5:
            return 1.0
        elif second > first * 1.2:
            return 0.5
        elif second > first * 0.8:
            return 0.0
        elif second > first * 0.5:
            return -0.3
        else:
            return -0.6


class RewardStore:
    def __init__(self, db_path: Path | str = DB_PATH):
        self._db_path = Path(db_path)
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        try:
            with self._lock, sqlite3.connect(self._db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS gsc_rewards (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        keyword TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        total_reward REAL NOT NULL,
                        position_component REAL,
                        ctr_component REAL,
                        trajectory_component REAL,
                        stability_component REAL,
                        impression_component REAL,
                        components TEXT,
                        metadata TEXT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_reward_kw_time
                    ON gsc_rewards(keyword, timestamp)
                """)
        except Exception:
            self._recreate_db()

    def _recreate_db(self) -> None:
        log.warning(f"Corrupt DB at {self._db_path}, recreating")
        try:
            with open(self._db_path, "wb"):
                pass
        except Exception:
            pass
        try:
            _wal = self._db_path.with_suffix(self._db_path.suffix + "-wal")
            _shm = self._db_path.with_suffix(self._db_path.suffix + "-shm")
            for p in [_wal, _shm]:
                if p.exists():
                    p.unlink()
        except Exception:
            pass
        with self._lock, sqlite3.connect(self._db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gsc_rewards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    total_reward REAL NOT NULL,
                    position_component REAL,
                    ctr_component REAL,
                    trajectory_component REAL,
                    stability_component REAL,
                    impression_component REAL,
                    components TEXT,
                    metadata TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reward_kw_time
                ON gsc_rewards(keyword, timestamp)
            """)

    def store_reward(self, keyword: str, signal: RewardSignal) -> None:
        with self._lock, sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO gsc_rewards
                   (keyword, timestamp, total_reward, position_component,
                    ctr_component, trajectory_component, stability_component,
                    impression_component, components, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    keyword, signal.timestamp, signal.total,
                    signal.position_component, signal.ctr_component,
                    signal.trajectory_component, signal.stability_component,
                    signal.impression_component,
                    json.dumps(signal.components),
                    json.dumps(signal.metadata),
                ),
            )

    def get_rewards(
        self, keyword: str, days: int = 28
    ) -> list[RewardSignal]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """SELECT keyword, timestamp, total_reward,
                          position_component, ctr_component,
                          trajectory_component, stability_component,
                          impression_component, components, metadata
                   FROM gsc_rewards
                   WHERE keyword = ? AND timestamp >= ?
                   ORDER BY timestamp ASC""",
                (keyword, cutoff),
            ).fetchall()
        return [
            RewardSignal(
                keyword=r[0], timestamp=r[1], total=r[2],
                position_component=r[3] or 0.0, ctr_component=r[4] or 0.0,
                trajectory_component=r[5] or 0.0, stability_component=r[6] or 0.0,
                impression_component=r[7] or 0.0,
                components=json.loads(r[8]) if r[8] else {},
                metadata=json.loads(r[9]) if r[9] else {},
            )
            for r in rows
        ]

    def get_reward_stats(self, keyword: str, days: int = 28) -> dict:
        rewards = self.get_rewards(keyword, days)
        if not rewards:
            return {"n": 0, "mean": None, "min": None, "max": None,
                    "trend": "insufficient_data"}

        totals = [r.total for r in rewards]
        n = len(totals)

        if n >= 3:
            first_half = statistics.mean(totals[:n//2])
            second_half = statistics.mean(totals[n//2:])
            if second_half > first_half * 1.1:
                trend = "improving"
            elif second_half < first_half * 0.9:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        return {
            "n": n,
            "mean": round(statistics.mean(totals), 3),
            "std": round(statistics.stdev(totals), 3) if n >= 2 else None,
            "min": round(min(totals), 3),
            "max": round(max(totals), 3),
            "trend": trend,
        }

    def get_aggregate_stats(self, keywords: list[str] | None = None, days: int = 28) -> dict:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            if keywords:
                placeholders = ",".join("?" * len(keywords))
                rows = conn.execute(
                    f"""SELECT keyword, total_reward
                        FROM gsc_rewards
                        WHERE keyword IN ({placeholders}) AND timestamp >= ?
                        ORDER BY timestamp""",
                    (*keywords, cutoff),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT keyword, total_reward FROM gsc_rewards WHERE timestamp >= ? ORDER BY timestamp",
                    (cutoff,),
                ).fetchall()

        if not rows:
            return {"n": 0, "mean": None, "keyword_count": 0}

        totals = [r[1] for r in rows]
        kw_set = set(r[0] for r in rows)

        return {
            "n": len(totals),
            "mean": round(statistics.mean(totals), 3),
            "std": round(statistics.stdev(totals), 3) if len(totals) >= 2 else None,
            "min": round(min(totals), 3),
            "max": round(max(totals), 3),
            "keyword_count": len(kw_set),
            "per_keyword": {
                kw: {
                    "n": sum(1 for r_ in rows if r_[0] == kw),
                    "mean": round(statistics.mean([r_[1] for r_ in rows if r_[0] == kw]), 3),
                }
                for kw in kw_set
            },
        }

    def get_latest_rewards(self, keywords: list[str]) -> dict[str, RewardSignal | None]:
        result = {}
        for kw in keywords:
            rewards = self.get_rewards(kw, days=7)
            result[kw] = rewards[-1] if rewards else None
        return result

    def prune_old(self, days: int = 365) -> int:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self._lock, sqlite3.connect(self._db_path) as conn:
            cur = conn.execute(
                "DELETE FROM gsc_rewards WHERE timestamp < ?", (cutoff,)
            )
            return cur.rowcount
