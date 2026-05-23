"""
Feedback Engine — post-publish metrics fetch and performance analysis.

Simulates Google Search Console data. Replace fetch_post_publish_metrics()
with real GSC API when available — the interface stays the same.
"""

import logging
import random
from datetime import datetime

log = logging.getLogger("feedback")


# ── 1. Metrics Fetch ──────────────────────────────────────────

def fetch_post_publish_metrics(keyword: str, article_url: str = "") -> dict:
    """Fetch post-publish ranking and engagement metrics.

    In production, replace this with Google Search Console API call.
    Current implementation returns simulated data based on keyword
    characteristics for development/testing.
    """
    kw_l = keyword.lower()
    words = len(kw_l.split())

    # Simulate position based on keyword competitiveness
    base_pos = _estimate_base_position(keyword)

    # Simulate CTR based on position
    ctr = _estimate_ctr(base_pos)

    # Simulate impressions based on search volume proxy
    impressions = _estimate_impressions(keyword)

    clicks = int(impressions * ctr / 100)

    return {
        "keyword": keyword,
        "url": article_url,
        "position": base_pos,
        "ctr": round(ctr, 1),
        "impressions": impressions,
        "clicks": clicks,
        "dwell_time": _estimate_dwell(base_pos),
        "fetched_at": datetime.now().isoformat(),
        "_source": "simulated" if not article_url else "proxy",
    }


def _estimate_base_position(keyword: str) -> int:
    """Estimate ranking position based on keyword characteristics."""
    kw_l = keyword.lower()
    score = 0

    # Commercial keywords are more competitive
    if any(w in kw_l for w in ["best", "top", "review", "vs"]):
        score += 5
    if any(w in kw_l for w in ["software", "tool", "platform", "service"]):
        score += 3
    if any(w in kw_l for w in ["free", "cheap"]):
        score += 2

    # Longer keywords are less competitive
    words = len(kw_l.split())
    if words <= 2:
        score += 5
    elif words <= 3:
        score += 3
    elif words >= 5:
        score -= 2

    # Some randomness to simulate real variance
    score += random.randint(-3, 5)

    return max(3, min(50, 8 + score))


def _estimate_ctr(position: int) -> float:
    """Estimate CTR based on position using approximate Google averages."""
    if position == 1:
        return round(random.uniform(15, 30), 1)
    elif position == 2:
        return round(random.uniform(10, 20), 1)
    elif position <= 3:
        return round(random.uniform(8, 15), 1)
    elif position <= 5:
        return round(random.uniform(5, 12), 1)
    elif position <= 10:
        return round(random.uniform(2, 6), 1)
    elif position <= 20:
        return round(random.uniform(1, 3), 1)
    else:
        return round(random.uniform(0.2, 1.5), 1)


def _estimate_impressions(keyword: str) -> int:
    """Estimate monthly impressions based on keyword competition proxy."""
    kw_l = keyword.lower()
    base = 500
    if any(w in kw_l for w in ["best", "top", "review"]):
        base = 2000
    if any(w in kw_l for w in ["free", "cheap"]):
        base += 1000
    if len(kw_l.split()) >= 4:
        base = int(base * 0.6)
    return max(100, int(base * random.uniform(0.5, 1.5)))


def _estimate_dwell(position: int) -> int:
    """Estimate dwell time in seconds based on position."""
    base = 45 if position <= 3 else 35 if position <= 10 else 25
    return max(10, int(base * random.uniform(0.7, 1.3)))


# ── 2. Performance Analysis ───────────────────────────────────

def analyze_performance(memory_entry: dict, metrics: dict) -> dict:
    """Score article performance 0-100 and identify what needs fixing.

    Returns:
        {
            "score": int (0-100),
            "issues": list[str],
            "action": "stable" | "rewrite" | "optimize"
        }
    """
    pos = metrics.get("position", 50)
    ctr = metrics.get("ctr", 0)
    impressions = metrics.get("impressions", 0)
    clicks = metrics.get("clicks", 0)

    score = 0
    issues = []

    # Position score (0-50)
    if pos <= 3:
        score += 50
    elif pos <= 5:
        score += 40
    elif pos <= 10:
        score += 30
    elif pos <= 15:
        score += 20
    elif pos <= 20:
        score += 10
    else:
        issues.append("Position > 20 — needs major improvement")

    # CTR score (0-25)
    if ctr >= 10:
        score += 25
    elif ctr >= 5:
        score += 18
    elif ctr >= 3:
        score += 12
    elif ctr >= 1.5:
        score += 6
    else:
        issues.append("CTR below 1.5% — title and meta need rewriting")

    # Impressions-to-clicks ratio (0-15)
    if impressions > 0:
        ratio = clicks / impressions * 100
        if ratio >= 5:
            score += 15
        elif ratio >= 2:
            score += 10
        elif ratio >= 1:
            score += 5
        else:
            issues.append("High impressions but low clicks — meta description mismatch")

    # Dwell time (0-10)
    dwell = metrics.get("dwell_time", 0)
    if dwell:
        if dwell >= 90:
            score += 10
        elif dwell >= 60:
            score += 7
        elif dwell >= 30:
            score += 4
        else:
            issues.append("Low dwell time — content doesn't match search intent")

    # Action determination
    if score < 30 or pos > 20:
        action = "rewrite"
    elif score < 60 or pos > 10:
        action = "optimize"
    else:
        action = "stable"

    return {
        "score": min(100, score),
        "issues": issues[:4],
        "action": action,
        "position": pos,
        "ctr": ctr,
    }


def detect_issues(metrics: dict) -> list[str]:
    """Quick issue detection without full performance scoring."""
    issues = []
    pos = metrics.get("position", 50)
    ctr = metrics.get("ctr", 0)
    impressions = metrics.get("impressions", 0)
    clicks = metrics.get("clicks", 0)

    if pos > 10:
        issues.append("title_meta")
        if pos > 20:
            issues.append("content_depth")
            issues.append("structure")
    if ctr < 2:
        issues.append("title_meta")
    if impressions > 1000 and clicks < 10:
        issues.append("meta_description")
    if metrics.get("dwell_time", 60) < 30:
        issues.append("content_relevance")

    return issues[:5]


def estimate_ranking_potential(keyword: str) -> dict:
    """Quick ranking potential estimate before rewrite decision."""
    kw_l = keyword.lower()
    difficulty = 0
    if any(w in kw_l for w in ["best", "top", "review"]):
        difficulty += 3
    if any(w in kw_l for w in ["software", "tool", "app"]):
        difficulty += 2
    if len(kw_l.split()) <= 2:
        difficulty += 3

    return {
        "keyword": keyword,
        "difficulty": min(10, difficulty),
        "estimated_improvement_months": max(1, difficulty),
        "requires_rewrite": difficulty >= 4,
    }
