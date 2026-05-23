"""
Google Feedback Engine — translates real GSC data into rewrite decisions.

Pipeline:
  Real GSC data
    → evaluate_real_performance()
    → diagnose_issues()
    → estimate_ranking_potential()
    → rewrite_decision()
    → rewrite_with_real_data()
"""

import json
import logging
import re
from datetime import datetime

from seo.auto_rewriter import (
    improve_title,
    improve_meta_description,
    remove_fluff,
    compress_sentences,
    inject_gaps,
)
from llm_router import c

log = logging.getLogger("google_feedback")


def evaluate_real_performance(gsc_data: dict, article_word_count: int = 0) -> dict:
    """Score real performance 0-100 based on actual GSC data.

    Factors:
      - Position (0-40)
      - CTR vs position benchmark (0-25)
      - Impression-to-click conversion (0-15)
      - Dwell time proxy (0-10)
      - Position trend (0-10)
    """
    pos = gsc_data.get("position", 50)
    ctr = gsc_data.get("ctr", 0)
    impressions = gsc_data.get("impressions", 0)
    clicks = gsc_data.get("clicks", 0)
    dwell = gsc_data.get("dwell_time", 30)

    score = 0
    issues = []
    signals = []

    # ── Position score (0-40) ──
    if pos <= 1:
        score += 40
        signals.append("top_position")
    elif pos <= 3:
        score += 35
        signals.append("top_3")
    elif pos <= 5:
        score += 28
    elif pos <= 10:
        score += 20
        issues.append("position_outside_top_10")
        signals.append("needs_improvement")
    elif pos <= 15:
        score += 12
        issues.append("position_11_15")
        signals.append("needs_improvement")
    elif pos <= 20:
        score += 6
        issues.append("position_16_20")
        signals.append("needs_major_improvement")
    else:
        issues.append("position_below_20")
        signals.append("needs_rewrite")

    # ── CTR score vs position benchmark (0-25) ──
    expected_ctr = _expected_ctr_for_position(pos)
    if ctr >= expected_ctr * 1.3:
        score += 25
        signals.append("ctr_above_expected")
    elif ctr >= expected_ctr:
        score += 18
    elif ctr >= expected_ctr * 0.7:
        score += 10
    else:
        issues.append("ctr_below_expected")
        signals.append("title_meta_issue")

    # ── Impression-to-click ratio (0-15) ──
    if impressions > 0:
        ratio = clicks / impressions * 100
        serp_avg_for_pos = expected_ctr
        if ratio >= serp_avg_for_pos * 0.8:
            score += 15
        elif ratio >= serp_avg_for_pos * 0.5:
            score += 8
        else:
            issues.append("high_impressions_low_clicks")
            signals.append("intent_mismatch")

    # ── Dwell time proxy (0-10) ──
    if dwell >= 90:
        score += 10
    elif dwell >= 60:
        score += 7
    elif dwell >= 30:
        score += 4
    else:
        issues.append("low_dwell_time")
        signals.append("content_quality_issue")

    # ── Position trend (0-10) ──
    trend = gsc_data.get("position_trend", [])
    if trend and len(trend) >= 7:
        recent = trend[-7:]
        improving = sum(1 for i in range(1, len(recent)) if recent[i] < recent[i-1])
        declining = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i-1])
        if improving >= 5:
            score += 10
            signals.append("ranking_improving")
        elif improving >= 3:
            score += 5
        elif declining >= 5:
            score -= 5
            issues.append("ranking_declining")
            signals.append("needs_attention")
        else:
            score += 2

    score = max(0, min(100, score))

    if score >= 75:
        action = "stable"
        status = "good"
    elif score >= 50:
        action = "optimize"
        status = "weak"
    else:
        action = "rewrite"
        status = "critical"

    return {
        "performance_score": score,
        "action": action,
        "status": status,
        "issues": issues[:5],
        "signals": signals,
        "position": pos,
        "ctr": ctr,
        "impressions": impressions,
        "clicks": clicks,
    }


def _expected_ctr_for_position(position: int) -> float:
    """Average CTR for a given Google position (aggregate data)."""
    ctr_table = {
        1: 28.0, 2: 18.0, 3: 12.0, 4: 9.0, 5: 7.5,
        6: 6.0, 7: 5.0, 8: 4.0, 9: 3.5, 10: 3.0,
        11: 2.5, 12: 2.2, 13: 2.0, 14: 1.8, 15: 1.5,
        16: 1.3, 17: 1.2, 18: 1.0, 19: 0.8, 20: 0.6,
    }
    if position <= 20:
        return ctr_table[position]
    return max(0.2, 0.6 - (position - 20) * 0.03)


def diagnose_issues(evaluation: dict, gsc_data: dict, article_text: str) -> list[str]:
    """Diagnose specific issues causing poor performance."""
    issues = []
    pos = evaluation.get("position", 50)
    ctr = evaluation.get("ctr", 0)
    impressions = evaluation.get("impressions", 0)
    clicks = evaluation.get("clicks", 0)

    # Position-based diagnosis
    if pos > 20:
        issues.append("content_depth")
        issues.append("authority_gap")
        issues.append("structure")
    elif pos > 10:
        issues.append("content_depth")
        issues.append("title_meta")

    # CTR-based diagnosis
    if ctr < 2.0:
        issues.append("title_meta")
    if ctr < 1.0 and pos <= 10:
        issues.append("title_does_not_match_intent")

    # Intent mismatch
    if impressions > 1000 and clicks < 10:
        issues.append("intent_mismatch")

    # Dwell time
    dwell = gsc_data.get("dwell_time", 30)
    if dwell < 30:
        issues.append("content_relevance")

    # Content length check
    if article_text and len(article_text.split()) < 800:
        issues.append("content_too_short")

    # Keyword presence check
    if article_text:
        kw = gsc_data.get("keyword", "")
        if kw and kw.lower() not in article_text[:500].lower():
            issues.append("keyword_missing_in_intro")

    return list(dict.fromkeys(issues))[:6]


def estimate_ranking_potential(keyword: str, current_position: int) -> dict:
    """Estimate maximum achievable position for a keyword."""
    kw_l = keyword.lower()
    difficulty = 0

    if any(w in kw_l for w in ["best", "top", "review", "vs"]):
        difficulty += 3
    if any(w in kw_l for w in ["software", "tool", "app", "platform"]):
        difficulty += 2
    if len(kw_l.split()) <= 2:
        difficulty += 3

    best_possible = max(1, current_position - difficulty - _improvement_estimate(difficulty))
    estimated_months = max(1, difficulty + (current_position // 5))

    return {
        "keyword": keyword,
        "current_position": current_position,
        "best_possible_position": best_possible,
        "difficulty": min(10, difficulty),
        "estimated_months_to_improve": estimated_months,
        "requires_rewrite": current_position > 15 or difficulty >= 5,
    }


def _improvement_estimate(difficulty: int) -> int:
    """Deterministic improvement estimate based on keyword difficulty (0=hard, 10=easy)."""
    levels = {0: 5, 1: 4, 2: 4, 3: 3, 4: 3, 5: 2, 6: 2, 7: 1, 8: 1, 9: 1, 10: 1}
    return levels.get(difficulty, 1)


def rewrite_decision(evaluation: dict, ranking_potential: dict) -> dict:
    """Make the final rewrite decision with clear reasoning.

    Returns:
        {
            "should_rewrite": bool,
            "reason": str,
            "priority": "high" | "medium" | "low",
            "changes_needed": list[str]
        }
    """
    score = evaluation.get("performance_score", 0)
    action = evaluation.get("action", "stable")
    issues = evaluation.get("issues", [])
    requires_rewrite = ranking_potential.get("requires_rewrite", False)

    changes_needed = []
    for issue in issues:
        change_map = {
            "content_depth": "expand_content",
            "title_meta": "improve_title_meta",
            "title_does_not_match_intent": "rewrite_title_for_intent",
            "intent_mismatch": "restructure_for_intent",
            "content_relevance": "improve_relevance",
            "content_too_short": "expand_content",
            "keyword_missing_in_intro": "add_keyword_to_intro",
            "authority_gap": "add_authority_signals",
            "structure": "improve_structure",
            "ranking_declining": "full_rewrite",
        }
        for issue_type, change in change_map.items():
            if issue_type in issue or issue.startswith(issue_type):
                changes_needed.append(change)

    if action == "rewrite" or (action == "optimize" and requires_rewrite):
        return {
            "should_rewrite": True,
            "reason": f"Score {score}/100. Issues: {', '.join(issues[:3])}",
            "priority": "high" if score < 40 else "medium",
            "changes_needed": list(set(changes_needed)) or ["full_rewrite"],
        }

    if action == "optimize":
        return {
            "should_rewrite": True,
            "reason": f"Score {score}/100 — optimization needed",
            "priority": "medium",
            "changes_needed": list(set(changes_needed)) or ["targeted_optimization"],
        }

    return {
        "should_rewrite": False,
        "reason": f"Score {score}/100 — stable",
        "priority": "low",
        "changes_needed": [],
    }


def rewrite_with_real_data(
    article_html: str,
    keyword: str,
    gsc_data: dict,
    evaluation: dict,
    changes_needed: list[str],
    gap_angles: list[dict] | None = None,
) -> dict:
    """Rewrite article based on REAL Google data, not guesses.

    Targeted improvements:
      - Title/CTR fix if impressions but no clicks
      - Meta description if low CTR
      - Content depth if position > 10
      - Intent restructure if intent mismatch
      - Keyword injection if missing
      - Gap injection if authority gap
    """
    changes_made = []
    html = article_html

    current_title = ""
    title_m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
    if title_m:
        current_title = title_m.group(1)

    current_meta = ""
    meta_m = re.search(r'<meta name="description" content="([^"]*)"', html)
    if meta_m:
        current_meta = meta_m.group(1)

    for change in changes_needed:
        if change == "improve_title_meta":
            new_title = improve_title(keyword, current_title)
            if new_title and new_title != current_title:
                html = html.replace(f"<title>{current_title}</title>", f"<title>{new_title}</title>")
                html = html.replace(f"<h1>{current_title}</h1>", f"<h1>{new_title}</h1>")
                changes_made.append(f"title_updated: \"{new_title}\"")
                current_title = new_title

            new_meta = improve_meta_description(keyword, current_meta, html)
            if new_meta and new_meta != current_meta:
                html = html.replace(f'content="{current_meta}"', f'content="{new_meta}"')
                changes_made.append("meta_description_updated")
                current_meta = new_meta

        elif change == "expand_content":
            if gap_angles:
                before = len(html)
                html = inject_gaps(html, gap_angles, max_inject=3)
                if len(html) > before:
                    changes_made.append(f"gap_sections_injected")
            changes_made.append("content_expanded")

        elif change == "improve_relevance":
            html = remove_fluff(html)
            html = compress_sentences(html)
            changes_made.append("relevance_improved")

        elif change == "add_keyword_to_intro":
            kw_lower = keyword.lower()
            if kw_lower not in html[:1000].lower():
                intro_end = html.find("</h1>")
                if intro_end > 0:
                    first_p = html.find("<p>", intro_end)
                    if first_p > 0:
                        p_end = html.find("</p>", first_p)
                        if p_end > 0:
                            old_p = html[first_p:p_end + 4]
                            new_p = old_p.replace("<p>", f"<p>{keyword} — ")
                            html = html[:first_p] + new_p + html[p_end + 4:]
                            changes_made.append("keyword_added_to_intro")
            changes_made.append("keyword_check_passed")

        elif change == "improve_structure":
            html = remove_fluff(html)
            changes_made.append("structure_improved")

        elif change == "restructure_for_intent":
            intent_tag = re.search(r'<meta name="intent" content="([^"]*)"', html)
            if intent_tag:
                current_intent = intent_tag.group(1)
                new_intent = _detect_intent_from_gsc(gsc_data, keyword)
                if new_intent and new_intent != current_intent:
                    html = html.replace(f'content="{current_intent}"', f'content="{new_intent}"')
                    changes_made.append(f"intent_updated: {current_intent} -> {new_intent}")
            changes_made.append("intent_restructured")

    return {
        "rewritten_html": html,
        "changes_made": list(set(changes_made)),
        "new_title": current_title,
        "new_meta": current_meta,
    }


def _detect_intent_from_gsc(gsc_data: dict, keyword: str) -> str:
    """Detect correct intent from GSC data patterns."""
    ctr = gsc_data.get("ctr", 0)
    impressions = gsc_data.get("impressions", 0)
    clicks = gsc_data.get("clicks", 0)
    kw_l = keyword.lower()

    # High impressions, very low CTR = informational intent but article is commercial
    if impressions > 500 and ctr < 1.0:
        return "informational" if any(w in kw_l for w in ["what is", "how to", "guide", "meaning"]) else "commercial"

    # Commercial intent if keyword has commercial triggers
    if any(w in kw_l for w in ["best", "top", "review", "vs", "alternative", "compare"]):
        return "commercial"

    return "commercial"
