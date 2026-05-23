"""
ROI Reporting — measures real business value from SEO Agent.

Pipeline:
  Cluster ROI       → cost per article vs estimated traffic value
  Keyword ROI       → impressions, clicks, position trends per keyword
  Authority growth  → niche authority score over time
  Rewrite impact    → before/after performance comparison
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import memory as mem_module
from llm_router import c

log = logging.getLogger("reporting")


def generate_cluster_report(niche: str = "") -> dict:
    """Calculate ROI per keyword cluster.

    Returns:
        {
            "cluster": str,
            "articles_count": int,
            "total_estimated_traffic": int,
            "total_estimated_clicks": int,
            "avg_position": float,
            "estimated_monthly_value": float,
            "articles": [...]
        }
    """
    memory = mem_module.load()
    articles = memory.get("articles_written", [])
    clusters = memory.get("clusters", {})
    authority = memory.get("authority_scores", {})

    if niche:
        articles = [a for a in articles if niche.lower() in a.get("keyword", "").lower()]

    cluster_data = {}
    for article in articles:
        kw = article.get("keyword", "")
        perf = article.get("performance_history", [])
        latest = perf[-1] if perf else {}

        pos = latest.get("position", 50)
        imp = latest.get("impressions", 0)
        clicks = latest.get("clicks", 0)
        ctr = latest.get("ctr", 0)

        cluster_name = _detect_cluster(kw, clusters)
        if cluster_name not in cluster_data:
            cluster_data[cluster_name] = {
                "cluster": cluster_name,
                "articles_count": 0,
                "total_impressions": 0,
                "total_clicks": 0,
                "positions": [],
                "estimated_monthly_value": 0.0,
                "articles": [],
            }

        cd = cluster_data[cluster_name]
        cd["articles_count"] += 1
        cd["total_impressions"] += imp
        cd["total_clicks"] += clicks
        if pos:
            cd["positions"].append(pos)
        cd["articles"].append({
            "keyword": kw,
            "position": pos,
            "impressions": imp,
            "clicks": clicks,
            "ctr": ctr,
        })

    results = []
    for name, data in cluster_data.items():
        avg_pos = sum(data["positions"]) / len(data["positions"]) if data["positions"] else 0
        monthly_value = _estimate_traffic_value(data["total_clicks"])
        data["avg_position"] = round(avg_pos, 1)
        data["total_impressions_est"] = data["total_impressions"]
        data["total_clicks_est"] = data["total_clicks"]
        data["estimated_monthly_value"] = round(monthly_value, 2)
        results.append(data)

    results.sort(key=lambda r: r["estimated_monthly_value"], reverse=True)

    return {
        "generated_at": datetime.now().isoformat(),
        "total_clusters": len(results),
        "total_articles": len(articles),
        "niche": niche or "all",
        "clusters": results,
        "authority_scores": {n: s.get("score", 0) for n, s in authority.items()},
    }


def _detect_cluster(keyword: str, clusters: dict) -> str:
    for cluster_name, cluster_data in clusters.items():
        if cluster_name.lower() in keyword.lower():
            return cluster_name
    # Fallback: use first 2 words of keyword
    parts = keyword.split()
    return " ".join(parts[:2]) if len(parts) >= 2 else keyword


def _estimate_traffic_value(clicks: int, cost_per_click: float = 0.50) -> float:
    """Estimate monthly traffic value based on clicks and avg CPC."""
    return clicks * cost_per_click


def generate_keyword_report(keyword: str) -> dict:
    """Generate detailed performance report for a single keyword."""
    memory = mem_module.load()
    articles = memory.get("articles_written", [])

    article = None
    for a in articles:
        if a["keyword"] == keyword:
            article = a
            break

    if not article:
        return {"error": f"Keyword '{keyword}' not found in memory", "keyword": keyword}

    perf_history = article.get("performance_history", [])
    revisions = len(perf_history)
    latest = perf_history[-1] if perf_history else {}

    position_trend = [p.get("position") for p in perf_history if p.get("position")]
    ctr_trend = [p.get("ctr") for p in perf_history if p.get("ctr")]
    impression_trend = [p.get("impressions") for p in perf_history if p.get("impressions")]

    improving = False
    if len(position_trend) >= 2:
        improving = position_trend[-1] < position_trend[0]

    return {
        "keyword": keyword,
        "word_count": article.get("word_count", 0),
        "model": article.get("model", "local"),
        "written_at": article.get("date", ""),
        "revisions": revisions,
        "latest_position": latest.get("position"),
        "latest_ctr": latest.get("ctr"),
        "latest_impressions": latest.get("impressions"),
        "latest_clicks": latest.get("clicks"),
        "position_trend": position_trend,
        "ctr_trend": ctr_trend,
        "impression_trend": impression_trend,
        "is_improving": improving,
    }


def generate_rewrite_impact_report(keyword: str, before_score: int, after_score: int) -> dict:
    """Measure impact of a rewrite on performance."""
    improvement = after_score - before_score
    pct_change = round((improvement / max(before_score, 1)) * 100, 1)

    return {
        "keyword": keyword,
        "before_score": before_score,
        "after_score": after_score,
        "improvement": improvement,
        "pct_change": pct_change,
        "verdict": "positive" if improvement > 0 else ("neutral" if improvement == 0 else "negative"),
        "measured_at": datetime.now().isoformat(),
    }


def print_cluster_report(report: dict) -> None:
    """Pretty-print cluster ROI report."""
    print(c("bold", f"\n  Cluster ROI Report  [{report['niche']}]"))
    print(c("dim", f"  Generated: {report['generated_at'][:19]}"))
    print(c("dim", f"  Total clusters: {report['total_clusters']}  ·  Articles: {report['total_articles']}"))
    print(c("dim", "  " + "─" * 58))

    for cluster in report.get("clusters", []):
        name = cluster["cluster"][:40]
        articles = cluster["articles_count"]
        avg_pos = cluster.get("avg_position", "?")
        clicks = cluster.get("total_clicks_est", 0)
        value = cluster.get("estimated_monthly_value", 0)
        status = c("green", "●") if avg_pos != "?" and avg_pos <= 10 else c("yellow", "○") if avg_pos != "?" and avg_pos <= 20 else c("red", "○")

        print(f"  {status} {name:<40} {articles} art  pos {str(avg_pos):>4}  {clicks:>5} clk  ${value:<8.2f}")

    authorities = report.get("authority_scores", {})
    if authorities:
        print(c("dim", "  " + "─" * 58))
        for niche, score in authorities.items():
            color = c("green", "●") if score >= 60 else c("yellow", "○") if score >= 30 else c("red", "○")
            print(f"  {color} Authority ({niche}): {score}/100")


def print_keyword_report(report: dict) -> None:
    """Pretty-print keyword performance report."""
    if "error" in report:
        print(c("red", f"  ✗ {report['error']}"))
        return

    print(c("bold", f"\n  Keyword Report: {report['keyword']}"))
    print(c("dim", "  " + "─" * 50))
    print(f"  Written:     {report.get('written_at', '?')[:19]}")
    print(f"  Word count:  {report.get('word_count', 0)}")
    print(f"  Model:       {report.get('model', '?')}")
    print(f"  Revisions:   {report.get('revisions', 0)}")
    print(f"  Position:    {report.get('latest_position', '?')}")
    print(f"  CTR:         {report.get('latest_ctr', '?')}%")
    print(f"  Impressions: {report.get('latest_impressions', 0)}")
    print(f"  Clicks:      {report.get('latest_clicks', 0)}")
    trend = "📈 Improving" if report.get("is_improving") else "📉 Declining"
    print(f"  Trend:       {trend}")

    pos_trend = report.get("position_trend", [])
    if len(pos_trend) >= 2:
        print(c("dim", f"  Position history: {', '.join(str(p) for p in pos_trend)}"))
