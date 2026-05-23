from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from agent_core.gsc_feedback.ranking_history import RankingHistory
from agent_core.gsc_feedback.ctr_tracker import CtrTracker
from agent_core.gsc_feedback.decay_detector import DecayDetector
from agent_core.gsc_feedback.reward_generator import GscRewardGenerator, RewardStore
from agent_core.gsc_feedback.anomaly_detector import AnomalyDetector

log = logging.getLogger("gsc_feedback.dashboard")


class FeedbackDashboard:
    def __init__(self):
        self._ranking = RankingHistory()
        self._ctr = CtrTracker()
        self._decay = DecayDetector()
        self._rewards = GscRewardGenerator()
        self._reward_store = RewardStore()
        self._anomalies = AnomalyDetector()

    def show_keyword_health(self, keyword: str, days: int = 28) -> None:
        print(f"\n{'=' * 60}")
        print(f"  KEYWORD HEALTH: {keyword}")
        print(f"{'=' * 60}")

        history = self._ranking.get_history(keyword, days)
        trajectory = self._ranking.analyze_trajectory(keyword, days)
        decay = self._decay.analyze(keyword, history, days)
        anoms = self._anomalies.detect_all(history, keyword, days)
        reward_stats = self._reward_store.get_reward_stats(keyword, days)

        print(f"  Data points:      {len(history)}")
        print(f"  Period:           {days} days")

        if trajectory:
            print(f"\n  {'─' * 40}")
            print(f"  TRAJECTORY ANALYSIS")
            print(f"  {'─' * 40}")
            print(f"  Direction:        {trajectory.direction}")
            print(f"  Slope:            {trajectory.slope:.3f}")
            print(f"  Volatility:       {trajectory.volatility:.2f}")
            print(f"  Momentum:         {trajectory.momentum:.2f}")
            print(f"  Start→End:        {trajectory.start_position} → {trajectory.end_position}")
            print(f"  Best→Worst:       {trajectory.best_position} → {trajectory.worst_position}")
            print(f"  Confidence:       {trajectory.confidence:.1%}")

        if decay:
            print(f"\n  {'─' * 40}")
            print(f"  DECAY ANALYSIS")
            print(f"  {'─' * 40}")
            print(f"  Decay Score:      {decay.score:.2f}")
            print(f"  Severity:         {decay.severity}")
            print(f"  Direction:        {decay.direction}")
            print(f"  Rewrite Trigger:  {decay.triggered_rewrite} ({decay.rewrite_priority})")
            for r in decay.reasons:
                print(f"  ⚠ {r}")
            print(f"  Components:")
            for comp, val in decay.components.items():
                print(f"    {comp}: {val:.3f}")

        if anoms:
            print(f"\n  {'─' * 40}")
            print(f"  ANOMALIES ({len(anoms)})")
            print(f"  {'─' * 40}")
            for a in anoms:
                print(f"  [{a.severity}] {a.description}")

        print(f"\n  {'─' * 40}")
        print(f"  CTR ANALYSIS")
        print(f"  {'─' * 40}")
        ctr_bench = self._ctr.ctr_vs_benchmark(keyword, days)
        print(f"  Avg CTR:          {ctr_bench.get('avg_ctr', 'N/A')}%")
        print(f"  Expected CTR:     {ctr_bench.get('avg_expected', 'N/A')}%")
        print(f"  Ratio:            {ctr_bench.get('ratio', 'N/A')}")
        print(f"  Above Benchmark:  {ctr_bench.get('above_benchmark', 'N/A')}")
        print(f"  Trend:            {self._ctr.ctr_trend(keyword, days)}")
        imp_trend = self._ctr.get_impression_trend(keyword, days)
        print(f"  Impressions:      {imp_trend.get('direction', 'N/A')} ({imp_trend.get('avg_impressions', 'N/A')}/day)")

        print(f"\n  {'─' * 40}")
        print(f"  REWARD SIGNAL")
        print(f"  {'─' * 40}")
        latest_rewards = self._reward_store.get_rewards(keyword, 7)
        if latest_rewards:
            r = latest_rewards[-1]
            print(f"  Total Reward:     {r.total:+.3f}")
            print(f"  Position:         {r.position_component:+.3f}")
            print(f"  CTR:              {r.ctr_component:+.3f}")
            print(f"  Trajectory:       {r.trajectory_component:+.3f}")
            print(f"  Stability:        {r.stability_component:+.3f}")
            print(f"  Impressions:      {r.impression_component:+.3f}")
        if reward_stats.get("n", 0) >= 2:
            print(f"  Reward trend:     {reward_stats.get('trend')} (mean={reward_stats['mean']:.3f}, σ={reward_stats.get('std', 'N/A')})")

    def show_ranking_history(self, keyword: str, days: int = 28) -> None:
        history = self._ranking.get_history(keyword, days)
        if not history:
            print(f"  No ranking history for '{keyword}'")
            return

        print(f"\n  RANKING HISTORY: {keyword} (last {days} days)")
        print(f"  {'─' * 60}")
        print(f"  {'Date':<14} {'Position':<10} {'CTR':<8} {'Impressions':<12} {'Clicks':<8}")
        print(f"  {'─' * 60}")

        for h in history[-20:]:
            pos = f"{h.position}" if h.position is not None else "-"
            ctr = f"{h.ctr:.1f}" if h.ctr is not None else "-"
            imp = f"{h.impressions}" if h.impressions is not None else "-"
            clk = f"{h.clicks}" if h.clicks is not None else "-"
            print(f"  {h.date:<14} {pos:<10} {ctr:<8} {imp:<12} {clk:<8}")

        wma = self._ranking.get_weighted_moving_average(keyword, window=5, days=days)
        if len(wma) >= 3:
            print(f"\n  Weighted Moving Average (5-day window, last 5):")
            for entry in wma[-5:]:
                print(f"    {entry['date']}: {entry['wma']}")

        comparison = self._ranking.compare_periods(keyword, period1_days=14, period2_days=14)
        if comparison.get("position_change") is not None:
            print(f"\n  Period Comparison:")
            print(f"    Last 14d avg pos: {comparison['recent_avg_position']:.1f}")
            print(f"    Prior 14d avg pos: {comparison['older_avg_position']:.1f}")
            print(f"    Change: {comparison['position_change']:+.1f} {'✓' if comparison['improving'] else '✗'}")

    def show_ctr_tracking(self, keyword: str, days: int = 28) -> None:
        ctr_history = self._ctr.get_ctr_history(keyword, days)
        if not ctr_history:
            print(f"  No CTR data for '{keyword}'")
            return

        print(f"\n  CTR TRACKING: {keyword}")
        print(f"  {'─' * 50}")
        print(f"  {'Date':<14} {'CTR%':<8} {'Pos':<6} {'Expected':<10}")
        print(f"  {'─' * 50}")

        for h in ctr_history[-15:]:
            expected = self._ctr.expected_ctr_for_position(h["position"])
            marker = "✓" if h["ctr"] and h["ctr"] >= expected else "✗"
            ctr_str = f"{h['ctr']:.1f}" if h["ctr"] is not None else "-"
            pos_str = f"{h['position']}" if h["position"] is not None else "-"
            print(f"  {h['date']:<14} {ctr_str:<8} {pos_str:<6} {expected:<8.1f}  {marker}")

        trend = self._ctr.ctr_trend(keyword, days)
        imp_trend = self._ctr.get_impression_trend(keyword, days)
        print(f"\n  CTR Trend: {trend}")
        print(f"  Impression Trend: {imp_trend.get('direction', 'N/A')}")

    def show_decay_alerts(self, keywords: list[str] | None = None) -> list[dict]:
        if keywords is None:
            keywords = self._ranking.get_all_keywords()

        alerts = []
        print(f"\n  DECAY ALERTS")
        print(f"  {'─' * 60}")
        print(f"  {'Keyword':<30} {'Score':<8} {'Severity':<12} {'Rewrite':<10}")
        print(f"  {'─' * 60}")

        for kw in keywords:
            decay = self._decay.analyze(kw)
            if decay and decay.severity != "none":
                alerts.append(decay.to_dict())
                print(f"  {kw:<30} {decay.score:<8.2f} {decay.severity:<12} {decay.rewrite_priority:<10}")

        if not alerts:
            print(f"  (no active decay alerts)")

        return alerts

    def show_reward_history(self, keyword: str, days: int = 28) -> None:
        rewards = self._reward_store.get_rewards(keyword, days)
        if not rewards:
            print(f"  No reward history for '{keyword}'")
            return

        stats = self._reward_store.get_reward_stats(keyword, days)

        print(f"\n  REWARD HISTORY: {keyword}")
        print(f"  {'─' * 50}")
        print(f"  Stats: n={stats['n']}, mean={stats['mean']:.3f}, σ={stats.get('std', 'N/A')}")
        print(f"  Range: [{stats['min']:.3f}, {stats['max']:.3f}]")
        print(f"  Trend: {stats.get('trend', 'N/A')}")
        print(f"\n  {'Date':<22} {'Total':<8} {'Pos':<8} {'CTR':<8} {'Traj':<8}")
        print(f"  {'─' * 50}")

        for r in rewards[-10:]:
            print(f"  {r.timestamp[:19]:<22} {r.total:<+8.3f} {r.position_component:<+8.3f} {r.ctr_component:<+8.3f} {r.trajectory_component:<+8.3f}")

    def show_anomaly_alerts(self, keywords: list[str] | None = None) -> list[dict]:
        if keywords is None:
            keywords = self._ranking.get_all_keywords()

        all_anomalies = []
        print(f"\n  ANOMALY ALERTS")
        print(f"  {'─' * 70}")
        print(f"  {'Keyword':<25} {'Type':<18} {'Severity':<10} {'Description'}")
        print(f"  {'─' * 70}")

        for kw in keywords:
            history = self._ranking.get_history(kw, 28)
            anoms = self._anomalies.detect_all(history, kw, 28)
            for a in anoms:
                all_anomalies.append(a.to_dict())
                print(f"  {kw:<25} {a.anomaly_type:<18} {a.severity:<10} {a.description[:60]}")

        if not all_anomalies:
            print(f"  (no anomalies detected)")

        return all_anomalies

    def show_summary(self, keywords: list[str] | None = None) -> None:
        if keywords is None:
            keywords = self._ranking.get_all_keywords()

        print(f"\n{'=' * 60}")
        print(f"  GSC FEEDBACK DASHBOARD — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'=' * 60}")
        print(f"  Tracked keywords:  {len(keywords)}")

        decay_alerts = 0
        anomaly_count = 0
        total_reward = 0.0
        reward_count = 0

        for kw in keywords:
            decay = self._decay.analyze(kw)
            if decay and decay.severity != "none":
                decay_alerts += 1
            history = self._ranking.get_history(kw, 28)
            anoms = self._anomalies.detect_all(history, kw, 28)
            anomaly_count += len(anoms)
            stats = self._reward_store.get_reward_stats(kw, 28)
            if stats.get("mean") is not None:
                total_reward += stats["mean"]
                reward_count += 1

        print(f"  Decay alerts:     {decay_alerts}")
        print(f"  Anomalies:        {anomaly_count}")
        print(f"  Avg reward:       {total_reward / max(1, reward_count):.3f} (across {reward_count} kw)")
        print(f"{'=' * 60}")

    def full_report(self, keyword: str, days: int = 28) -> None:
        self.show_keyword_health(keyword, days)
        self.show_ranking_history(keyword, days)
        self.show_ctr_tracking(keyword, days)
        self.show_reward_history(keyword, days)
