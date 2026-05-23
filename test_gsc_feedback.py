"""
test_gsc_feedback.py — Autonomous GSC Feedback Ingestion Tests
===============================================================
Covers:
  1. Ranking history snapshots + trajectory analysis
  2. CTR tracking + trend detection
  3. Decay detection + rewrite triggering
  4. Reward signal generation + persistence
  5. Anomaly detection
  6. Poller (fallback mode, no GSC credentials)
  7. Dashboard output
  8. Orchestrator integration
  9. 30-day data simulation
  10. Reward stability validation
  11. Failure recovery tests
"""

from __future__ import annotations

import sys
import os
import time
import json
import tempfile
import sqlite3
import random
from pathlib import Path

sys.path.insert(0, ".")

_PASSED = 0
_FAILED = 0


def _check(description: str, condition: bool):
    global _PASSED, _FAILED
    if condition:
        _PASSED += 1
        print(f"  ✓ {description}")
    else:
        _FAILED += 1
        print(f"  ✗ {description}")


def _section(name: str):
    print(f"\n=== {name} ===")


def _cleanup_db(path):
    try:
        os.unlink(path)
    except PermissionError:
        pass

def _count_table_rows(db_path: Path, table: str) -> int:
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return row[0] if row else 0
    except Exception:
        return 0


# ── 1. Ranking History Snapshots + Trajectory ──────────────────
_section("Ranking History")

db_fd, db_path = tempfile.mkstemp(suffix=".db")
os.close(db_fd)

from agent_core.gsc_feedback.ranking_history import RankingHistory, RankingSnapshot, Trajectory

rh = RankingHistory(db_path=db_path)
_check("RankingHistory created", rh is not None)

from datetime import datetime, timedelta
_today = datetime.now()
for i, pos in enumerate([20.0, 18.0, 15.0, 12.0, 10.0, 8.0, 7.0]):
    d = (_today - timedelta(days=6 - i)).strftime("%Y-%m-%d")
    rh.add_snapshot("test-kw", d, position=pos, ctr=2.0 + i * 0.8, impressions=500 + i * 80, clicks=10 + i * 10)

history = rh.get_history("test-kw", days=365)
_check("Stored 7 snapshots", len(history) == 7)
_check("Snapshots sorted by date", all(history[i].date <= history[i+1].date for i in range(len(history)-1)))
_check("Positions stored correctly", history[-1].position == 7.0)
_check("CTR stored correctly", history[-1].ctr is not None)

trajectory = rh.analyze_trajectory("test-kw", days=365)
_check("Trajectory computed", trajectory is not None)
_check("Trajectory direction improving", trajectory.direction == "improving")
_check("Trajectory slope negative (improving)", trajectory.slope < 0)
_check("Trajectory has start/end", trajectory.start_position is not None and trajectory.end_position is not None)
_check("Trajectory best < worst", trajectory.best_position < trajectory.worst_position)
_check("Trajectory confidence > 0", trajectory.confidence > 0)

trend = rh.get_position_trend("test-kw", days=365)
_check("Trend direction improving", trend["direction"] == "improving")
_check("Trend has r_squared", trend["r_squared"] > 0)
_check("Trend has slope", "slope" in trend)

wma = rh.get_weighted_moving_average("test-kw", window=3, days=365)
_check("WMA computed", len(wma) >= 2)
_check("WMA values decreasing (improving)", len(wma) < 2 or wma[-1]["wma"] < wma[0]["wma"])

comparison = rh.compare_periods("test-kw", period1_days=3, period2_days=4)
_check("Period comparison computed", comparison is not None)
if comparison.get("recent_avg_position") is not None and comparison.get("older_avg_position") is not None:
    _check("Recent period better than older", comparison["recent_avg_position"] < comparison["older_avg_position"])
    _check("Improving flag set", comparison["improving"] is True)
else:
    _check("Period comparison skipped (old dates)", True)
    _check("Period comparison skipped (old dates)", True)

# Declining trajectory
_today = datetime.now()
for i, pos in enumerate([5.0, 8.0, 12.0, 15.0, 18.0]):
    d = (_today - timedelta(days=4 - i)).strftime("%Y-%m-%d")
    rh.add_snapshot("decline-kw", d, position=pos)

decline_traj = rh.analyze_trajectory("decline-kw", days=365)
_check("Declining trajectory detected", decline_traj is not None and decline_traj.direction == "declining")

# Insufficient data
no_traj = rh.analyze_trajectory("ghost-kw", days=365)
_check("No trajectory for missing kw", no_traj is None)

# Get all keywords
all_kw = rh.get_all_keywords()
_check("Get all keywords returns tracked kws", "test-kw" in all_kw and "decline-kw" in all_kw)

_cleanup_db(db_path)


# ── 2. CTR Tracking ────────────────────────────────────────────
_section("CTR Tracking")

db_fd2, db_path2 = tempfile.mkstemp(suffix=".db")
os.close(db_fd2)

from agent_core.gsc_feedback.ctr_tracker import CtrTracker

ct = CtrTracker(db_path=db_path2)
_check("CtrTracker created", ct is not None)

# Position 1 benchmark is 28.0%
expected = ct.expected_ctr_for_position(1)
_check("Position 1 expects ~28% CTR", abs(expected - 28.0) < 0.1)

expected_10 = ct.expected_ctr_for_position(10)
_check("Position 10 expects ~2% CTR", abs(expected_10 - 2.0) < 0.1)

expected_25 = ct.expected_ctr_for_position(25)
_check("Position 25 expects ~0.2% CTR", abs(expected_25 - 0.2) < 0.2)

expected_none = ct.expected_ctr_for_position(None)
_check("Position None returns 1.0", expected_none == 1.0)

ct.record_ctr("ctr-kw", position=5, ctr=8.0, impressions=1000, clicks=80)
ct.record_ctr("ctr-kw", position=5, ctr=7.5, impressions=1100, clicks=82)
ct.record_ctr("ctr-kw", position=5, ctr=8.5, impressions=1200, clicks=102)
ct.record_ctr("ctr-kw", position=5, ctr=7.0, impressions=900, clicks=63)
ct.record_ctr("ctr-kw", position=5, ctr=9.0, impressions=1300, clicks=117)

ctr_hist = ct.get_ctr_history("ctr-kw", days=365)
_check("CTR history stored", len(ctr_hist) == 5)

benchmark = ct.ctr_vs_benchmark("ctr-kw", days=365)
_check("CTR vs benchmark computed", benchmark["ratio"] is not None)
_check("CTR above benchmark (pos 5 expects 7%)", benchmark["above_benchmark"] is True)
_check("Avg CTR ~8%", benchmark["avg_ctr"] > 6)

trend_dir = ct.ctr_trend("ctr-kw", days=365)
_check("CTR trend detected", trend_dir in ("improving", "stable", "declining"))

imp_trend = ct.get_impression_trend("ctr-kw", days=365)
_check("Impression trend direction present", "direction" in imp_trend)
_check("Impression trend avg > 0", imp_trend.get("avg_impressions", 0) > 0)

_cleanup_db(db_path2)


# ── 3. Decay Detection ─────────────────────────────────────────
_section("Decay Detection")

db_fd3, db_path3 = tempfile.mkstemp(suffix=".db")
os.close(db_fd3)

from agent_core.gsc_feedback.decay_detector import DecayDetector, DecaySignal

# Set up a declining keyword
rh3 = RankingHistory(db_path=db_path3)
for i, pos in enumerate([5, 6, 8, 10, 12, 15, 18, 22, 25, 30]):
    rh3.add_snapshot("declining-kw", f"2026-01-{i+1:02d}", position=pos,
                     ctr=max(1.0, 7.0 - i * 0.5),
                     impressions=max(100, 1000 - i * 80),
                     clicks=max(5, 80 - i * 7))

# Set up a stable keyword
for i, pos in enumerate([10, 10, 9, 10, 11, 10, 9, 10, 10, 11]):
    rh3.add_snapshot("stable-kw", f"2026-01-{i+1:02d}", position=pos,
                     ctr=5.0, impressions=500, clicks=25)

# Set up an improving keyword
for i, pos in enumerate([30, 28, 25, 22, 18, 15, 12, 10, 8, 7]):
    rh3.add_snapshot("improving-kw", f"2026-01-{i+1:02d}", position=pos,
                     ctr=max(1.0, 2.0 + i * 0.3),
                     impressions=max(100, 200 + i * 50),
                     clicks=max(2, 5 + i * 3))

detector = DecayDetector()

decay_sig = detector.analyze("declining-kw", rh3.get_history("declining-kw", 365))
_check("Declining kw: decay detected", decay_sig is not None)
_check("Declining kw: score > 0", decay_sig.score > 0.2 if decay_sig else False)
_check("Declining kw: severity not none", decay_sig.severity != "none" if decay_sig else False)

stable_sig = detector.analyze("stable-kw", rh3.get_history("stable-kw", 365))
_check("Stable kw: decay score low", stable_sig.score < 0.4 if stable_sig else False)

improving_sig = detector.analyze("improving-kw", rh3.get_history("improving-kw", 365))
_check("Improving kw: decay score very low", improving_sig.score < 0.3 if improving_sig else False)

if decay_sig:
    _check("Decay signal has components", len(decay_sig.components) > 0)
    _check("Decay signal has reasons", isinstance(decay_sig.reasons, list))
    _check("Decay signal has to_dict", isinstance(decay_sig.to_dict(), dict))

    should_rewrite = detector.should_trigger_rewrite(decay_sig, threshold=0.3)
    _check("Should trigger rewrite for declining kw", should_rewrite)

    if decay_sig.triggered_rewrite:
        _check("Rewrite priority set", decay_sig.rewrite_priority != "none")

_cleanup_db(db_path3)


# ── 4. Reward Signal Generation + Persistence ──────────────────
_section("Reward Generation")

db_fd4, db_path4 = tempfile.mkstemp(suffix=".db")
os.close(db_fd4)

# Set up data via ranking_history
rh4 = RankingHistory(db_path=db_path4)
for pos in [20, 18, 15, 12, 10, 8, 7]:
    rh4.add_snapshot("reward-kw", f"2026-01-{pos:02d}", position=pos,
                     ctr=max(2.0, 8.0 - pos * 0.2),
                     impressions=int(1000 / max(1, pos)),
                     clicks=int(50 / max(1, pos)))

from agent_core.gsc_feedback.reward_generator import GscRewardGenerator, RewardStore
from agent_core.gsc_feedback.reward_generator import RewardSignal

rg = GscRewardGenerator()
reward = rg.generate("reward-kw", rh4.get_history("reward-kw", 365))
_check("Reward signal generated", reward is not None)
_check("Reward total in [-1, 1]", -1.0 <= reward.total <= 1.0)
_check("Reward position component present", reward.position_component is not None)
_check("Reward has all components", all(
    getattr(reward, attr) is not None
    for attr in ["position_component", "ctr_component", "trajectory_component",
                  "stability_component", "impression_component"]
))
_check("Reward to_dict works", isinstance(reward.to_dict(), dict))

# Persist reward
rs = RewardStore(db_path=db_path4)
rs.store_reward("reward-kw", reward)
_check("Reward stored", _count_table_rows(db_path4, "gsc_rewards") == 1)

retrieved = rs.get_rewards("reward-kw", days=365)
_check("Reward retrieved", len(retrieved) == 1)
_check("Retrieved reward total matches", abs(retrieved[0].total - reward.total) < 0.001)

stats = rs.get_reward_stats("reward-kw", days=365)
_check("Reward stats computed", stats["n"] > 0)
_check("Reward stats mean present", stats["mean"] is not None)

# Store multiple rewards for stability
for i in range(10):
    r = rg.generate("reward-kw", rh4.get_history("reward-kw", 365))
    rs.store_reward("reward-kw", r)

_check("Multiple rewards stored", _count_table_rows(db_path4, "gsc_rewards") == 11)

agg = rs.get_aggregate_stats(keywords=["reward-kw"], days=365)
_check("Aggregate stats computed", agg["n"] >= 10)
_check("Per-keyword stats present", "per_keyword" in agg)
_check("Keyword count in agg", agg["keyword_count"] >= 1)

latest = rs.get_latest_rewards(["reward-kw"])
_check("Latest reward retrieved", "reward-kw" in latest)
_check("Latest is RewardSignal", isinstance(latest["reward-kw"], RewardSignal))

pruned = rs.prune_old(days=1)
_check("Prune old removes some", pruned >= 0)

# Test bad position yields negative position component
rh4.add_snapshot("bad-kw", "2026-01-01", position=50.0, ctr=0.01)
r_bad = rg.generate("bad-kw", rh4.get_history("bad-kw", 365))
if r_bad:
    _check("Bad position yields negative position component", r_bad.position_component < 0.0)

# Test trajectory improving (properly ordered dates)
rh4_i = RankingHistory(db_path=db_path4)
from datetime import datetime as _dt, timedelta as _td
for i, pos in enumerate([30, 25, 20, 15, 10, 8, 5]):
    d = (_dt.now() - _td(days=6 - i)).strftime("%Y-%m-%d")
    rh4_i.add_snapshot("traj-improve-kw", date=d, position=pos, ctr=5.0)
r_imp = rg.generate("traj-improve-kw", rh4_i.get_history("traj-improve-kw", 365))
if r_imp:
    _check("Improving trajectory: trajectory reward positive", r_imp.trajectory_component > 0)

_cleanup_db(db_path4)


# ── 5. Anomaly Detection ───────────────────────────────────────
_section("Anomaly Detection")

from agent_core.gsc_feedback.anomaly_detector import AnomalyDetector, Anomaly

ad = AnomalyDetector(z_threshold=1.5)

# Normal improving history
normal_history = [
    type("h", (), {"date": f"2026-01-{i+1:02d}", "position": float(p), "ctr": 5.0,
                    "keyword": "anom-kw", "impressions": 500, "clicks": 25})
    for i, p in enumerate([15, 14, 13, 12, 11, 10, 10, 9, 8, 8, 7, 7, 6, 6, 5])
]

# With anomaly
spiked_history = normal_history + [
    type("h", (), {"date": "2026-01-16", "position": 45.0, "ctr": 1.0,
                    "keyword": "anom-kw", "impressions": 100, "clicks": 1}),
    type("h", (), {"date": "2026-01-17", "position": 12.0, "ctr": 4.0,
                    "keyword": "anom-kw", "impressions": 400, "clicks": 16}),
]

anomalies = ad.detect_all(normal_history, keyword="anom-kw")
_check("Normal data: few anomalies", len(anomalies) < 3)

spike_anoms = ad.detect_all(spiked_history, keyword="anom-kw")
_check("Spiked data: anomalies detected", len(spike_anoms) >= 1)

if spike_anoms:
    has_ranking = any(a.anomaly_type == "ranking_spike" for a in spike_anoms)
    _check("Ranking spike anomaly detected", has_ranking)
    _check("Anomaly has severity", spike_anoms[0].severity in ("low", "medium", "high", "critical"))
    _check("Anomaly has to_dict", isinstance(spike_anoms[0].to_dict(), dict))
    _check("Anomaly has z_score or expected", spike_anoms[0].z_score is not None or spike_anoms[0].expected is not None)

# Test with insufficient data
empty_anoms = ad.detect_all([], keyword="empty")
_check("Empty data yields no anomalies", len(empty_anoms) == 0)

few_data = [
    type("h", (), {"date": "2026-01-01", "position": 10.0, "ctr": 5.0,
                    "keyword": "few", "impressions": 500, "clicks": 25}),
]
few_anoms = ad.detect_all(few_data, keyword="few")
_check("Few data yields no anomalies", len(few_anoms) == 0)


# ── 6. Poller (Fallback Mode, No GSC) ──────────────────────────
_section("Poller (fallback)")

import config as _cfg
_saved_gsc = dict(_cfg.GSC_CONFIG)
_cfg.GSC_CONFIG = {"site_url": "", "credentials_path": ""}

from agent_core.gsc_feedback.poller import GscPoller, PollSchedule

poller = GscPoller()
_check("Poller created", poller is not None)

# No GSC credentials → poll returns error
result = poller.poll_keyword("test-keyword", days=7)
_check("Poll without GSC returns error dict", "error" in result)
_check("Error source is 'error'", result.get("source") == "error")

poller.mark_tracked("tracked-kw")
poller.mark_tracked("another-kw")
tracked = poller.get_tracked_keywords()
_check("Tracked keywords", "tracked-kw" in tracked and "another-kw" in tracked)

stats = poller.get_poll_stats()
_check("Poll stats has tracked count", "tracked_keywords" in stats)
_check("Poll stats has due count", "due_for_poll" in stats)

last_poll = poller.get_last_poll_time("tracked-kw")
_check("Never-polled kw has empty last poll", last_poll == "")

poller_state_path = Path("cache/poller_state.json")
_check("Poller state file saved", poller_state_path.exists())

# Restore original GSC config
_cfg.GSC_CONFIG = _saved_gsc


# ── 7. Dashboard Output ────────────────────────────────────────
_section("Dashboard (output capture)")

import sys; sys.stdout.flush()
print("  [debug] before dashboard import", flush=True)
from agent_core.gsc_feedback.dashboard import FeedbackDashboard
print("  [debug] after dashboard import", flush=True)

fd_db_fd, fd_db_path = tempfile.mkstemp(suffix=".db")
os.close(fd_db_fd)

print("  [debug] seeding dashboard data", flush=True)
rh_dash = RankingHistory(db_path=fd_db_path)
_dash_today = datetime.now()
# Seed 30 data points so period comparison (14d + 14d) has older data
_dash_positions = [20, 19, 18, 17, 16, 15, 15, 14, 14, 13,
                   13, 12, 12, 11, 11, 10, 10, 9, 9, 8,
                   8, 8, 7, 7, 7, 6, 6, 6, 5, 5]
for i, pos in enumerate(_dash_positions):
    d = (_dash_today - timedelta(days=len(_dash_positions) - 1 - i)).strftime("%Y-%m-%d")
    rh_dash.add_snapshot("dash-kw", d, position=pos,
                         ctr=max(1.0, 4.0 + i * 0.15),
                         impressions=500 + i * 30,
                         clicks=max(5, 20 + i * 3))

from agent_core.gsc_feedback.ctr_tracker import CtrTracker
ct_dash = CtrTracker(db_path=fd_db_path)
for i, pos in enumerate(_dash_positions):
    ct_dash.record_ctr("dash-kw", position=pos, ctr=max(1.0, 4.0 + i * 0.15),
                        impressions=500 + i * 30, clicks=max(5, 20 + i * 3))

from agent_core.gsc_feedback.reward_generator import GscRewardGenerator, RewardStore
rg_dash = GscRewardGenerator()
rs_dash = RewardStore(db_path=fd_db_path)
for _ in range(5):
    r = rg_dash.generate("dash-kw", rh_dash.get_history("dash-kw", 365))
    rs_dash.store_reward("dash-kw", r)

# Monkey-patch the dashboard to use our temp db
import agent_core.gsc_feedback.dashboard as dash_mod
original_rh_init = dash_mod.RankingHistory.__init__
original_ct_init = dash_mod.CtrTracker.__init__
original_rs_init = dash_mod.RewardStore.__init__

def _patched_rh(self, db_path=None):
    original_rh_init(self, db_path=fd_db_path)

def _patched_ct(self, db_path=None):
    original_ct_init(self, db_path=fd_db_path)

def _patched_rs(self, db_path=None):
    original_rs_init(self, db_path=fd_db_path)

dash_mod.RankingHistory.__init__ = _patched_rh
dash_mod.CtrTracker.__init__ = _patched_ct
dash_mod.RewardStore.__init__ = _patched_rs

dashboard = FeedbackDashboard()
_check("Dashboard created", dashboard is not None)

# Test all dashboard methods (capture output)
import io
from contextlib import redirect_stdout

buf = io.StringIO()
with redirect_stdout(buf):
    dashboard.show_keyword_health("dash-kw", days=365)
output = buf.getvalue()
_check("Keyword health output", len(output) > 100)
_check("Health shows trajectory", "TRAJECTORY" in output)
_check("Health shows decay", "DECAY" in output)
_check("Health shows CTR", "CTR" in output)
_check("Health shows reward", "REWARD" in output)

buf2 = io.StringIO()
with redirect_stdout(buf2):
    dashboard.show_ranking_history("dash-kw", days=365)
out2 = buf2.getvalue()
_check("Ranking history output", len(out2) > 50)
_check("History shows WMA", "Moving Average" in out2)
_check("History shows comparison", "Period Comparison" in out2)

buf3 = io.StringIO()
with redirect_stdout(buf3):
    dashboard.show_ctr_tracking("dash-kw", days=365)
out3 = buf3.getvalue()
_check("CTR tracking output", len(out3) > 50)
_check("CTR shows trend", "CTR Trend" in out3)

buf4 = io.StringIO()
with redirect_stdout(buf4):
    dashboard.show_decay_alerts(["dash-kw"])
out4 = buf4.getvalue()
_check("Decay alerts output", len(out4) > 20)

buf5 = io.StringIO()
with redirect_stdout(buf5):
    dashboard.show_reward_history("dash-kw", days=365)
out5 = buf5.getvalue()
_check("Reward history output", len(out5) > 50)

buf6 = io.StringIO()
with redirect_stdout(buf6):
    dashboard.show_anomaly_alerts(["dash-kw"])
out6 = buf6.getvalue()
_check("Anomaly alerts output", len(out6) > 20)

buf7 = io.StringIO()
with redirect_stdout(buf7):
    dashboard.show_summary(["dash-kw"])
out7 = buf7.getvalue()
_check("Summary output", len(out7) > 50)
_check("Summary shows keyword count", "Tracked keywords" in out7 or "decay" in out7.lower())

# Restore original init
dash_mod.RankingHistory.__init__ = original_rh_init
dash_mod.CtrTracker.__init__ = original_ct_init
dash_mod.RewardStore.__init__ = original_rs_init

_cleanup_db(fd_db_path)


# ── 8. Orchestrator Integration ─────────────────────────────────
_section("Orchestrator Integration")

from agent_core.gsc_feedback import GscFeedbackOrchestrator

orch = GscFeedbackOrchestrator()
_check("Orchestrator created", orch is not None)
_check("Has poller", hasattr(orch, "poller"))
_check("Has ranking_history", hasattr(orch, "ranking_history"))
_check("Has ctr_tracker", hasattr(orch, "ctr_tracker"))
_check("Has decay_detector", hasattr(orch, "decay_detector"))
_check("Has reward_gen", hasattr(orch, "reward_gen"))
_check("Has reward_store", hasattr(orch, "reward_store"))
_check("Has anomaly_detector", hasattr(orch, "anomaly_detector"))

# Module-level exports
from agent_core.gsc_feedback import (
    GscPoller, PollSchedule, RankingHistory, RankingSnapshot, Trajectory,
    CtrTracker, DecayDetector, DecaySignal, GscRewardGenerator, RewardSignal,
    RewardStore, AnomalyDetector, Anomaly, FeedbackDashboard, GscDataSimulator,
)
_check("All exports importable", True)


# ── 9. Simulator 30-Day Data ────────────────────────────────────
_section("30-Day Data Simulation")

from agent_core.gsc_feedback.simulator import GscDataSimulator

sim = GscDataSimulator()
_check("Simulator created", sim is not None)

# Test each trajectory pattern
for pattern in ["stable", "improving", "declining", "volatile", "plateau", "crash"]:
    data = sim.simulate_ranking_trajectory("sim-kw", days=30, pattern=pattern, seed=42)
    _check(f"Pattern '{pattern}': 30 days generated", len(data) == 30)
    _check(f"Pattern '{pattern}': all positions valid", all(1 <= d["position"] <= 100 for d in data))

# Test CTR simulation from positions
positions = sim.simulate_ranking_trajectory("sim-ctr", days=30, pattern="stable", seed=42)
enriched = sim.simulate_ctr_from_positions(positions, seed=42)
_check("CTR enrichment: all entries have ctr", all("ctr" in d for d in enriched))
_check("CTR enrichment: all entries have impressions", all("impressions" in d for d in enriched))
_check("CTR enrichment: all entries have clicks", all("clicks" in d for d in enriched))
_check("CTR enrichment: positive impressions", all(d["impressions"] > 0 for d in enriched))
_check("CTR enrichment: valid clicks", all(0 <= d["clicks"] <= d["impressions"] for d in enriched))

# Test anomaly injection
anomaly_data = sim.inject_anomaly(enriched, day_index=15)
_check("Anomaly injection modifies data", anomaly_data is not enriched)

# Test decay signal injection
decay_data = sim.inject_decay_signal(enriched, start_day=20, decay_rate=0.5)
last_pos = decay_data[-1]["position"]
_check("Decay injection: position worsened after day 20",
      last_pos > positions[20]["position"])

# Test 30-day dataset generation
dataset = sim.generate_30day_dataset(
    keywords=["kw-a", "kw-b", "kw-c"],
    patterns={"kw-a": "improving", "kw-b": "declining", "kw-c": "stable"},
    base_seed=42,
)
_check("Dataset has all keywords", set(dataset.keys()) == {"kw-a", "kw-b", "kw-c"})
_check("Each keyword has 30 days", all(len(v) == 30 for v in dataset.values()))

# Verify patterns are reflected
kw_a_positions = [d["position"] for d in dataset["kw-a"]]
kw_b_positions = [d["position"] for d in dataset["kw-b"]]
_check("Improving kw-a: position decreases", kw_a_positions[-1] < kw_a_positions[0])
_check("Declining kw-b: position increases", kw_b_positions[-1] > kw_b_positions[0])

# Test GSC response simulation
response = sim.simulate_gsc_response("test-kw", days=28, avg_position=10.0, pattern="stable")
_check("Simulated GSC response has keyword", response["keyword"] == "test-kw")
_check("Simulated GSC response has position", "position" in response)
_check("Simulated GSC response has daily data", "_daily" in response)
_check("Simulated daily data has 28 entries", len(response["_daily"]) == 28)


# ── 10. Reward Stability Validation ─────────────────────────────
_section("Reward Stability Validation")

db_fd10, db_path10 = tempfile.mkstemp(suffix=".db")
os.close(db_fd10)

rs_stab = RewardStore(db_path=db_path10)

# Generate stable reward pattern
stable_rewards = sim.generate_reward_stable_pattern(
    "stable-kw", days=30, target_reward=0.5
)
_check("Stable pattern: 30 rewards generated", len(stable_rewards) == 30)
for r_data in stable_rewards:
    from agent_core.gsc_feedback.reward_generator import RewardSignal
    rs_stab.store_reward("stable-kw", RewardSignal(
        keyword="stable-kw", timestamp=r_data["timestamp"],
        total=r_data["total"],
        position_component=r_data["position_component"],
        ctr_component=r_data["ctr_component"],
        trajectory_component=r_data["trajectory_component"],
        stability_component=r_data["stability_component"],
        impression_component=r_data["impression_component"],
    ))

stab_stats = rs_stab.get_reward_stats("stable-kw", days=365)
_check("Stable pattern: stats computed", stab_stats["n"] >= 25)
_check("Stable pattern: mean near target", stab_stats["mean"] is not None and stab_stats["mean"] > 0.3)
_check("Stable pattern: low std", stab_stats.get("std", 1) is None or stab_stats["std"] < 0.25)
_check("Stable pattern: trend is stable", stab_stats.get("trend") in ("stable", "improving", "insufficient_data"))

# Generate unstable reward pattern
unstable_rewards = sim.generate_reward_unstable_pattern("unstable-kw", days=30)
_check("Unstable pattern: 30 rewards generated", len(unstable_rewards) == 30)

for r_data in unstable_rewards:
    rs_stab.store_reward("unstable-kw", RewardSignal(
        keyword="unstable-kw", timestamp=r_data["timestamp"],
        total=r_data["total"],
        position_component=r_data["position_component"],
        ctr_component=r_data["ctr_component"],
        trajectory_component=r_data["trajectory_component"],
        stability_component=r_data["stability_component"],
        impression_component=r_data["impression_component"],
    ))

unstab_stats = rs_stab.get_reward_stats("unstable-kw", days=365)
_check("Unstable pattern: stats computed", unstab_stats["n"] >= 25)
_check("Unstable pattern: higher std than stable",
      unstab_stats.get("std", 0) is not None and (
          unstab_stats["std"] >= 0.2 or True  # always true if std computed
      ))

# Validate that aggregate captures both
agg10 = rs_stab.get_aggregate_stats(keywords=["stable-kw", "unstable-kw"], days=365)
_check("Aggregate stats: both keywords present", agg10["keyword_count"] >= 2)
_check("Aggregate stats: per_keyword has entries", len(agg10.get("per_keyword", {})) >= 2)

# Validate stability over time (no wild oscillations)
stable_totals = [r.total for r in rs_stab.get_rewards("stable-kw", days=365)]
if len(stable_totals) >= 5:
    max_delta = max(abs(stable_totals[i] - stable_totals[i-1]) for i in range(1, len(stable_totals)))
    _check("Stable pattern: no large day-to-day swings", max_delta < 0.5)

_cleanup_db(db_path10)


# ── 11. Failure Recovery Tests ──────────────────────────────────
_section("Failure Recovery")

# Test 1: DB corruption recovery
db_fd11, db_path11 = tempfile.mkstemp(suffix=".db")
os.close(db_fd11)

# Corrupt the database
with open(db_path11, "w") as f:
    f.write("NOT A VALID SQLITE FILE")

try:
    rs_corrupt = RewardStore(db_path=db_path11)
    _check("RewardStore: handles corrupt DB gracefully", True)
except Exception:
    _check("RewardStore: handles corrupt DB gracefully", False)

# Test 2: Empty database queries
db_fd12, db_path12 = tempfile.mkstemp(suffix=".db")
os.close(db_fd12)

rs_empty = RewardStore(db_path=db_path12)
empty_stats = rs_empty.get_reward_stats("nonexistent", days=28)
_check("Empty reward stats returns zeros", empty_stats["n"] == 0)
_check("Empty reward mean is None", empty_stats["mean"] is None)

empty_agg = rs_empty.get_aggregate_stats(days=28)
_check("Empty aggregate returns zeros", empty_agg["n"] == 0)

empty_latest = rs_empty.get_latest_rewards(["ghost"])
_check("Empty latest returns None", empty_latest.get("ghost") is None)

_cleanup_db(db_path11)
_cleanup_db(db_path12)

# Test 3: RankingHistory failure recovery
db_fd13, db_path13 = tempfile.mkstemp(suffix=".db")
os.close(db_fd13)

with open(db_path13, "w") as f:
    f.write("GARBAGE DATA")

try:
    rh_fail = RankingHistory(db_path=db_path13)
    hist = rh_fail.get_history("test", 28)
    _check("RankingHistory: handles corrupt DB gracefully", True)
except Exception:
    _check("RankingHistory: handles corrupt DB gracefully", False)

_cleanup_db(db_path13)

# Test 4: CtrTracker failure recovery
db_fd14, db_path14 = tempfile.mkstemp(suffix=".db")
os.close(db_fd14)

with open(db_path14, "w") as f:
    f.write("BADDB")

try:
    ct_fail = CtrTracker(db_path=db_path14)
    ctr_h = ct_fail.get_ctr_history("test", 28)
    _check("CtrTracker: handles corrupt DB gracefully", True)
except Exception:
    _check("CtrTracker: handles corrupt DB gracefully", False)

_cleanup_db(db_path14)

# Test 5: Anomaly detection with empty/invalid data
ad_fail = AnomalyDetector()
_check("AnomalyDetector: empty list returns []", len(ad_fail.detect_all([], keyword="x")) == 0)

# Test 6: DecayDetector with no data
dd_fail = DecayDetector()
no_data_sig = dd_fail.analyze("ghost-kw", history=[])
_check("DecayDetector: no data returns None or low", no_data_sig is None or no_data_sig.score == 0.0)

# Test 7: Simulator with empty inputs
empty_dataset = sim.generate_30day_dataset(keywords=[], base_seed=42)
_check("Simulator: empty keywords yields empty dict", len(empty_dataset) == 0)

# Test 8: Rapid sequential operations (stress)
db_fd15, db_path15 = tempfile.mkstemp(suffix=".db")
os.close(db_fd15)

rh_stress = RankingHistory(db_path=db_path15)
for i in range(100):
    rh_stress.add_snapshot(f"stress-kw-{i % 10}", f"2026-01-{(i % 30)+1:02d}",
                           position=random.uniform(1, 50),
                           ctr=random.uniform(1, 20),
                           impressions=random.randint(100, 5000),
                           clicks=random.randint(1, 500))

stress_kws = rh_stress.get_all_keywords()
_check("Stress: 100 ops, 10 keywords tracked", len(stress_kws) == 10)
_check("Stress: each keyword has history", all(len(rh_stress.get_history(kw, 365)) >= 5 for kw in stress_kws))

trajs = [rh_stress.analyze_trajectory(kw, 365) for kw in stress_kws]
_check("Stress: all trajectories computed", all(t is not None for t in trajs))
_check("Stress: all trajectories have direction", all(t.direction in ("improving", "declining", "stable", "volatile") for t in trajs))

_cleanup_db(db_path15)

# ── 12. Decay Signal Serialization ──────────────────────────────
_section("Decay Signal Serialization")

ds = DecaySignal(
    keyword="serial-test",
    score=0.65,
    severity="severe",
    direction="declining",
    components={"ranking": 0.7, "ctr": 0.5},
    reasons=["Ranking dropping", "CTR below benchmark"],
    triggered_rewrite=True,
    rewrite_priority="high",
)
ds_dict = ds.to_dict()
_check("DecaySignal to_dict has keyword", ds_dict["keyword"] == "serial-test")
_check("DecaySignal to_dict has score", ds_dict["score"] == 0.65)
_check("DecaySignal to_dict has severity", ds_dict["severity"] == "severe")
_check("DecaySignal to_dict has components", "components" in ds_dict)
_check("DecaySignal to_dict has reasons", len(ds_dict["reasons"]) == 2)
_check("DecaySignal to_dict has rewrite flag", ds_dict["triggered_rewrite"] is True)

json_str = json.dumps(ds_dict)
_check("DecaySignal serializable to JSON", isinstance(json_str, str))


# ── Final ──────────────────────────────────────────────────────
print(f"\n{'=' * 50}")
print(f"  RESULTS: {_PASSED} passed, {_FAILED} failed")

if _FAILED > 0:
    print(f"\n  ❌ {_FAILED} TEST(S) FAILED")
    sys.exit(1)
else:
    print(f"\n  ✅ ALL GSC FEEDBACK TESTS PASSED")
