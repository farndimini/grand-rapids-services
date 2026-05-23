from __future__ import annotations

import json
import logging
import sqlite3
import statistics
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

log = logging.getLogger("gsc_feedback.ranking_history")

DB_PATH = Path(__file__).resolve().parent.parent.parent / "metrics.db"


@dataclass
class RankingSnapshot:
    keyword: str
    date: str
    position: float | None
    ctr: float | None
    impressions: int | None
    clicks: int | None
    source: str = "gsc"

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "date": self.date,
            "position": self.position,
            "ctr": self.ctr,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "source": self.source,
        }


@dataclass
class Trajectory:
    direction: str  # improving | declining | stable | volatile
    slope: float
    volatility: float
    momentum: float
    period_days: int
    start_position: float | None
    end_position: float | None
    best_position: float | None
    worst_position: float | None
    confidence: float

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "slope": round(self.slope, 4),
            "volatility": round(self.volatility, 4),
            "momentum": round(self.momentum, 4),
            "period_days": self.period_days,
            "start_position": self.start_position,
            "end_position": self.end_position,
            "best_position": self.best_position,
            "worst_position": self.worst_position,
            "confidence": round(self.confidence, 3),
        }


class RankingHistory:
    def __init__(self, db_path: Path | str = DB_PATH):
        self._db_path = Path(db_path)
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        try:
            with self._lock, sqlite3.connect(self._db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS ranking_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        keyword TEXT NOT NULL,
                        date TEXT NOT NULL DEFAULT '',
                        position REAL,
                        ctr REAL,
                        impressions INTEGER,
                        clicks INTEGER,
                        source TEXT DEFAULT 'gsc',
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                """)
                for col, col_type in [("date", "TEXT NOT NULL DEFAULT ''"),
                                      ("source", "TEXT DEFAULT 'gsc'")]:
                    try:
                        conn.execute(f"ALTER TABLE ranking_snapshots ADD COLUMN {col} {col_type}")
                    except Exception:
                        pass
                try:
                    conn.execute("""
                        CREATE INDEX IF NOT EXISTS idx_rank_snap_kw_date
                        ON ranking_snapshots(keyword, date)
                    """)
                except Exception:
                    pass
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
                CREATE TABLE IF NOT EXISTS ranking_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL,
                    date TEXT NOT NULL DEFAULT '',
                    position REAL,
                    ctr REAL,
                    impressions INTEGER,
                    clicks INTEGER,
                    source TEXT DEFAULT 'gsc',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

    def add_snapshot(
        self,
        keyword: str,
        date: str | None = None,
        position: float | None = None,
        ctr: float | None = None,
        impressions: int | None = None,
        clicks: int | None = None,
        source: str = "gsc",
    ) -> None:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        with self._lock, sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO ranking_snapshots
                   (keyword, date, position, ctr, impressions, clicks, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (keyword, date, position, ctr, impressions, clicks, source),
            )

    def add_from_gsc_data(self, keyword: str, gsc_data: dict) -> None:
        self.add_snapshot(
            keyword=keyword,
            position=gsc_data.get("position"),
            ctr=gsc_data.get("ctr"),
            impressions=gsc_data.get("impressions"),
            clicks=gsc_data.get("clicks"),
            source="gsc",
        )

    def get_history(
        self, keyword: str, days: int = 28
    ) -> list[RankingSnapshot]:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """SELECT keyword, date, position, ctr, impressions, clicks, source
                   FROM ranking_snapshots
                   WHERE keyword = ? AND date >= ?
                   ORDER BY date ASC""",
                (keyword, cutoff),
            ).fetchall()
        return [
            RankingSnapshot(
                keyword=r[0], date=r[1], position=r[2],
                ctr=r[3], impressions=r[4], clicks=r[5], source=r[6],
            )
            for r in rows
        ]

    def get_all_keywords(self) -> list[str]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT DISTINCT keyword FROM ranking_snapshots ORDER BY keyword"
            ).fetchall()
        return [r[0] for r in rows]

    def analyze_trajectory(
        self, keyword: str, days: int = 28
    ) -> Trajectory | None:
        history = self.get_history(keyword, days)
        if len(history) < 3:
            return None

        positions = [h.position for h in history if h.position is not None]
        if len(positions) < 3:
            return None

        n = len(positions)
        slope, intercept = self._linear_regression(positions)
        volatility = statistics.stdev(positions) if n >= 2 else 0.0
        recent = positions[-max(3, n // 3):]
        momentum = positions[-1] - statistics.mean(recent) if recent else 0.0

        if slope < -0.2:
            direction = "improving"
        elif slope > 0.2:
            direction = "declining"
        elif volatility > statistics.mean(positions) * 0.3:
            direction = "volatile"
        else:
            direction = "stable"

        confidence = min(1.0, n / 28)

        return Trajectory(
            direction=direction,
            slope=slope,
            volatility=volatility,
            momentum=momentum,
            period_days=days,
            start_position=positions[0],
            end_position=positions[-1],
            best_position=min(positions),
            worst_position=max(positions),
            confidence=confidence,
        )

    def get_position_trend(
        self, keyword: str, days: int = 28
    ) -> dict:
        history = self.get_history(keyword, days)
        positions = [h.position for h in history if h.position is not None]
        if len(positions) < 2:
            return {"slope": 0, "intercept": 0, "r_squared": 0, "n": 0}

        slope, intercept = self._linear_regression(positions)
        predicted = [slope * i + intercept for i in range(len(positions))]
        ss_res = sum((p - pr) ** 2 for p, pr in zip(positions, predicted))
        ss_tot = sum((p - statistics.mean(positions)) ** 2 for p in positions)
        r_sq = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        return {
            "slope": round(slope, 4),
            "intercept": round(intercept, 2),
            "r_squared": round(r_sq, 4),
            "n": len(positions),
            "direction": "improving" if slope < -0.1 else "declining" if slope > 0.1 else "stable",
        }

    def get_weighted_moving_average(
        self, keyword: str, window: int = 7, days: int = 90
    ) -> list[dict]:
        history = self.get_history(keyword, days)
        positions = [(h.date, h.position) for h in history if h.position is not None]
        if len(positions) < window:
            return [{"date": d, "wma": p} for d, p in positions]

        result = []
        for i in range(len(positions) - window + 1):
            window_data = positions[i:i + window]
            weights = list(range(1, window + 1))
            wma = sum(p * w for (_, p), w in zip(window_data, weights)) / sum(weights)
            result.append({"date": window_data[-1][0], "wma": round(wma, 2)})
        return result

    def compare_periods(
        self, keyword: str, period1_days: int = 28, period2_days: int = 28
    ) -> dict:
        recent = self.get_history(keyword, period1_days)
        older = self.get_history(keyword, period1_days + period2_days)
        older = [h for h in older
                 if h.date < (datetime.now() - timedelta(days=period1_days)).strftime("%Y-%m-%d")]

        def _avg_pos(hist):
            pos = [h.position for h in hist if h.position is not None]
            return statistics.mean(pos) if pos else None

        def _avg_ctr(hist):
            ctrs = [h.ctr for h in hist if h.ctr is not None]
            return statistics.mean(ctrs) if ctrs else None

        recent_pos = _avg_pos(recent)
        older_pos = _avg_pos(older)
        recent_ctr = _avg_ctr(recent)
        older_ctr = _avg_ctr(older)

        return {
            "recent_period_days": period1_days,
            "older_period_days": period2_days,
            "recent_avg_position": recent_pos,
            "older_avg_position": older_pos,
            "position_change": (older_pos - recent_pos) if recent_pos is not None and older_pos is not None else None,
            "recent_avg_ctr": recent_ctr,
            "older_avg_ctr": older_ctr,
            "ctr_change": (recent_ctr - older_ctr) if recent_ctr is not None and older_ctr is not None else None,
            "improving": (recent_pos is not None and older_pos is not None and recent_pos < older_pos),
        }

    @staticmethod
    def _linear_regression(values: list[float]) -> tuple[float, float]:
        n = len(values)
        x_mean = (n - 1) / 2.0
        y_mean = statistics.mean(values)
        num = den = 0
        for i, y in enumerate(values):
            num += (i - x_mean) * (y - y_mean)
            den += (i - x_mean) ** 2
        slope = num / den if den else 0
        intercept = y_mean - slope * x_mean
        return slope, intercept
