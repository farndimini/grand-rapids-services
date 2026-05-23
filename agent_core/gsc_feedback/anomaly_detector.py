from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from agent_core.gsc_feedback.ranking_history import RankingHistory

log = logging.getLogger("gsc_feedback.anomaly_detector")


@dataclass
class Anomaly:
    anomaly_type: str
    keyword: str
    severity: str  # low | medium | high | critical
    value: float | None
    expected: float | None
    z_score: float | None
    date: str
    description: str

    def to_dict(self) -> dict:
        return {
            "type": self.anomaly_type,
            "keyword": self.keyword,
            "severity": self.severity,
            "value": self.value,
            "expected": self.expected,
            "z_score": round(self.z_score, 2) if self.z_score else None,
            "date": self.date,
            "description": self.description,
        }


class AnomalyDetector:
    def __init__(self, z_threshold: float = 2.0):
        self._ranking_history = RankingHistory()
        self._z_threshold = z_threshold

    def detect_all(
        self, history: list | None = None, keyword: str = "", days: int = 28
    ) -> list[Anomaly]:
        anomalies = []
        anomalies.extend(self.detect_ranking_anomalies(history, keyword, days))
        anomalies.extend(self.detect_ctr_anomalies(history, keyword, days))
        return anomalies

    def detect_ranking_anomalies(
        self, history: list | None = None, keyword: str = "", days: int = 28
    ) -> list[Anomaly]:
        if history is None:
            history = self._ranking_history.get_history(keyword, days)

        positions = [(h.date, h.position) for h in history if h.position is not None]
        if len(positions) < 5:
            return []

        values = [p[1] for p in positions]
        anomalies = []

        z_anomalies = self._z_score_anomalies(values)
        for idx in z_anomalies:
            z, val, mean_val = z_anomalies[idx]
            sev = self._severity_from_z(abs(z))
            anomalies.append(Anomaly(
                anomaly_type="ranking_spike",
                keyword=keyword or history[idx].keyword if history else "",
                severity=sev,
                value=val,
                expected=round(mean_val, 1),
                z_score=round(z, 2),
                date=positions[idx][0],
                description=f"Ranking position {val} (expected ~{mean_val:.1f}, z={z:.1f})",
            ))

        iqr_anomalies = self._iqr_anomalies(values)
        for idx in iqr_anomalies:
            if idx not in z_anomalies:
                val = values[idx]
                q1, q3 = self._quartiles(values)
                iqr = q3 - q1
                anomalies.append(Anomaly(
                    anomaly_type="ranking_outlier_iqr",
                    keyword=keyword or history[idx].keyword if history else "",
                    severity="low",
                    value=val,
                    expected=round((q1 + q3) / 2, 1),
                    z_score=None,
                    date=positions[idx][0],
                    description=f"Ranking {val} outside IQR [{q1:.0f}, {q3:.0f}]",
                ))

        return anomalies

    def detect_ctr_anomalies(
        self, history: list | None = None, keyword: str = "", days: int = 28
    ) -> list[Anomaly]:
        if history is None:
            history = self._ranking_history.get_history(keyword, days)

        ctr_data = [(h.date, h.ctr) for h in history if h.ctr is not None]
        if len(ctr_data) < 5:
            return []

        values = [c[1] for c in ctr_data]
        anomalies = []

        z_anomalies = self._z_score_anomalies(values)
        for idx in z_anomalies:
            z, val, mean_val = z_anomalies[idx]
            sev = self._severity_from_z(abs(z))
            anomalies.append(Anomaly(
                anomaly_type="ctr_anomaly",
                keyword=keyword or history[idx].keyword if history else "",
                severity=sev,
                value=val,
                expected=round(mean_val, 2),
                z_score=round(z, 2),
                date=ctr_data[idx][0],
                description=f"CTR {val}% (expected ~{mean_val:.1f}%, z={z:.1f})",
            ))

        return anomalies

    def _z_score_anomalies(
        self, values: list[float]
    ) -> dict[int, tuple[float, float, float]]:
        if len(values) < 3:
            return {}
        mean_val = statistics.mean(values)
        std_val = statistics.stdev(values)
        if std_val == 0:
            return {}

        anomalies = {}
        for i, v in enumerate(values):
            z = (v - mean_val) / std_val
            if abs(z) >= self._z_threshold:
                anomalies[i] = (z, v, mean_val)
        return anomalies

    def _iqr_anomalies(self, values: list[float]) -> list[int]:
        if len(values) < 5:
            return []
        q1, q3 = self._quartiles(values)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        return [i for i, v in enumerate(values) if v < lower or v > upper]

    @staticmethod
    def _quartiles(values: list[float]) -> tuple[float, float]:
        sorted_v = sorted(values)
        n = len(sorted_v)
        q1 = sorted_v[n // 4]
        q3 = sorted_v[(3 * n) // 4]
        return q1, q3

    @staticmethod
    def _severity_from_z(abs_z: float) -> str:
        if abs_z >= 4.0:
            return "critical"
        elif abs_z >= 3.0:
            return "high"
        elif abs_z >= 2.5:
            return "medium"
        else:
            return "low"
