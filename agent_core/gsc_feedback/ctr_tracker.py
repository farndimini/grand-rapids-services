from __future__ import annotations

import logging
import statistics
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

log = logging.getLogger("gsc_feedback.ctr_tracker")

DB_PATH = Path(__file__).resolve().parent.parent.parent / "metrics.db"

# CTR benchmarks by position (industry average for organic search)
_POSITION_CTR_BENCHMARK = {
    1: 28.0, 2: 15.0, 3: 11.0, 4: 8.0, 5: 7.0,
    6: 5.0, 7: 4.0, 8: 3.0, 9: 2.5, 10: 2.0,
    11: 1.5, 12: 1.2, 13: 1.0, 14: 0.8, 15: 0.7,
    16: 0.6, 17: 0.5, 18: 0.4, 19: 0.3, 20: 0.3,
}


class CtrTracker:
    def __init__(self, db_path: Path | str = DB_PATH):
        self._db_path = Path(db_path)
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        try:
            with self._lock, sqlite3.connect(self._db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS ctr_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        keyword TEXT NOT NULL,
                        date TEXT NOT NULL,
                        position REAL,
                        ctr REAL,
                        impressions INTEGER,
                        clicks INTEGER,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ctr_kw_date
                    ON ctr_history(keyword, date)
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
                CREATE TABLE IF NOT EXISTS ctr_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL,
                    date TEXT NOT NULL,
                    position REAL,
                    ctr REAL,
                    impressions INTEGER,
                    clicks INTEGER,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ctr_kw_date
                ON ctr_history(keyword, date)
            """)

    def record_ctr(
        self, keyword: str, position: float | None, ctr: float | None,
        impressions: int | None = None, clicks: int | None = None,
    ) -> None:
        date = datetime.now().strftime("%Y-%m-%d")
        with self._lock, sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO ctr_history (keyword, date, position, ctr, impressions, clicks)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (keyword, date, position, ctr, impressions, clicks),
            )

    def get_ctr_history(
        self, keyword: str, days: int = 28
    ) -> list[dict]:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """SELECT keyword, date, position, ctr, impressions, clicks
                   FROM ctr_history
                   WHERE keyword = ? AND date >= ?
                   ORDER BY date ASC""",
                (keyword, cutoff),
            ).fetchall()
        return [
            {"keyword": r[0], "date": r[1], "position": r[2],
             "ctr": r[3], "impressions": r[4], "clicks": r[5]}
            for r in rows
        ]

    def expected_ctr_for_position(self, position: float | None) -> float:
        if position is None:
            return 1.0
        pos_int = round(position)
        if pos_int in _POSITION_CTR_BENCHMARK:
            return _POSITION_CTR_BENCHMARK[pos_int]
        if pos_int > 20:
            return 0.2
        return 1.0

    def ctr_vs_benchmark(
        self, keyword: str, days: int = 28
    ) -> dict:
        history = self.get_ctr_history(keyword, days)
        if not history:
            return {"ratio": None, "above_benchmark": None, "avg_ctr": None, "avg_expected": None, "n": 0}

        actuals = []
        expecteds = []
        for h in history:
            if h["ctr"] is not None and h["position"] is not None:
                actuals.append(h["ctr"])
                expecteds.append(self.expected_ctr_for_position(h["position"]))

        if not actuals:
            return {"ratio": None, "above_benchmark": None, "avg_ctr": None, "avg_expected": None, "n": 0}

        avg_ctr = statistics.mean(actuals)
        avg_expected = statistics.mean(expecteds)
        ratio = avg_ctr / avg_expected if avg_expected > 0 else 1.0

        return {
            "avg_ctr": round(avg_ctr, 2),
            "avg_expected": round(avg_expected, 2),
            "ratio": round(ratio, 3),
            "above_benchmark": avg_ctr > avg_expected,
            "n": len(actuals),
        }

    def ctr_trend(self, keyword: str, days: int = 28) -> str:
        history = self.get_ctr_history(keyword, days)
        ctrs = [h["ctr"] for h in history if h["ctr"] is not None]
        if len(ctrs) < 3:
            return "insufficient_data"

        first_half = statistics.mean(ctrs[:len(ctrs)//2])
        second_half = statistics.mean(ctrs[len(ctrs)//2:])

        if second_half > first_half * 1.15:
            return "improving"
        elif second_half < first_half * 0.85:
            return "declining"
        else:
            return "stable"

    def get_impression_trend(self, keyword: str, days: int = 28) -> dict:
        history = self.get_ctr_history(keyword, days)
        imps = [h["impressions"] for h in history if h["impressions"] is not None]
        if len(imps) < 3:
            return {"direction": "insufficient_data", "avg_impressions": None}

        first_half = statistics.mean(imps[:len(imps)//2])
        second_half = statistics.mean(imps[len(imps)//2:])
        total = sum(imps)

        if second_half > first_half * 1.2:
            direction = "growing"
        elif second_half < first_half * 0.8:
            direction = "shrinking"
        else:
            direction = "stable"

        return {
            "direction": direction,
            "avg_impressions": round(total / len(imps), 0),
            "total_impressions": total,
            "first_half_avg": round(first_half, 0),
            "second_half_avg": round(second_half, 0),
        }
