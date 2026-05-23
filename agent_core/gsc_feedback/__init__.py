from agent_core.gsc_feedback.poller import GscPoller, PollSchedule
from agent_core.gsc_feedback.ranking_history import RankingHistory, RankingSnapshot, Trajectory
from agent_core.gsc_feedback.ctr_tracker import CtrTracker
from agent_core.gsc_feedback.decay_detector import DecayDetector, DecaySignal
from agent_core.gsc_feedback.reward_generator import GscRewardGenerator, RewardSignal, RewardStore
from agent_core.gsc_feedback.anomaly_detector import AnomalyDetector, Anomaly
from agent_core.gsc_feedback.dashboard import FeedbackDashboard
from agent_core.gsc_feedback.simulator import GscDataSimulator

class GscFeedbackOrchestrator:
    def __init__(self):
        self.poller = GscPoller()
        self.ranking_history = RankingHistory()
        self.ctr_tracker = CtrTracker()
        self.decay_detector = DecayDetector()
        self.reward_gen = GscRewardGenerator()
        self.reward_store = RewardStore()
        self.anomaly_detector = AnomalyDetector()

    def poll_and_analyze(self, keywords: list[str], days: int = 28) -> dict:
        results = {}
        for kw in keywords:
            data = self.poller.poll_keyword(kw, days)
            history = self.ranking_history.get_history(kw, days)
            trajectory = self.ranking_history.analyze_trajectory(kw, days) if history else None
            decay = self.decay_detector.analyze(kw, history)
            anomalies = self.anomaly_detector.detect_all(history)
            reward = self.reward_gen.generate(kw, history)
            self.reward_store.store_reward(kw, reward)
            results[kw] = {
                "data": data,
                "trajectory": trajectory,
                "decay": decay,
                "anomalies": anomalies,
                "reward": reward,
            }
        return results

    def run_scheduled_polling(self, keywords: list[str], interval_minutes: int = 60):
        import time
        while True:
            results = self.poll_and_analyze(keywords)
            print(f"[ORCH] Poll cycle complete — {len(results)} keywords")
            time.sleep(interval_minutes * 60)

    def generate_feedback_report(self, keywords: list[str]) -> dict:
        return self.poll_and_analyze(keywords)

    def run_decay_check(self, keywords: list[str], threshold: float = 0.3) -> list[dict]:
        alerts = []
        history = self.ranking_history
        for kw in keywords:
            decay = self.decay_detector.analyze(kw, history.get_history(kw, 28))
            if decay and decay.score >= threshold:
                alerts.append({"keyword": kw, "decay": decay})
        return alerts

    def get_reward_summary(self, keywords: list[str]) -> dict:
        return self.reward_store.get_aggregate_stats(keywords)

__all__ = [
    "GscPoller", "PollSchedule",
    "RankingHistory", "RankingSnapshot", "Trajectory",
    "CtrTracker",
    "DecayDetector", "DecaySignal",
    "GscRewardGenerator", "RewardSignal",
    "RewardStore",
    "AnomalyDetector", "Anomaly",
    "FeedbackDashboard",
    "GscDataSimulator",
    "GscFeedbackOrchestrator",
]
