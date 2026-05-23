"""
Learning Loop — GSC feedback engine with LearningLoopOrchestrator integration.
Pipeline: GSC data → evaluate → reward → evolve → rewrite → record.
Preserves backward compatibility with the existing run_learning_cycle API.
When agent_core.learning_loop.LearningLoopOrchestrator is available,
the cycle runs through the orchestrator for full closed-loop learning
(reward engine, strategy evolution, benchmark runner, vector memory,
state machine checkpointing).

Usage via CLI:
    python main.py --mode learn --keyword "best laptop" --threshold 60
    python main.py --mode learn --keyword "best laptop" --dry-run
    python main.py --mode optimize  # runs on all stored articles
"""
from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import memory as mem_module
from llm_router import c

log = logging.getLogger("learning_loop")

OUTPUT_DIR = Path("output")

_HAS_ORCHESTRATOR = False
try:
    from agent_core.learning_loop import LearningLoopOrchestrator
    _HAS_ORCHESTRATOR = True
except ImportError:
    pass


def _header(t: str) -> None:
    line = "═" * 56
    print(f"\n{c('purple', line)}")
    print(c("bold", f"  {t}"))
    print(c("purple", line))

def _ok(m: str) -> None:     print(c("green", f"  ✓ {m}"))
def _info(m: str) -> None:    print(c("dim", f"  · {m}"))
def _warn(m: str) -> None:    print(c("yellow", f"  ⚠ {m}"))
def _err(m: str) -> None:     print(c("red", f"  ✗ {m}"))


def get_orchestrator(**kwargs) -> Any:
    """Get or create the LearningLoopOrchestrator singleton."""
    if _HAS_ORCHESTRATOR:
        return LearningLoopOrchestrator(**kwargs)
    return None


def run_learning_cycle(
    keyword: str | None = None,
    threshold: int = 50,
    dry_run: bool = False,
    use_orchestrator: bool = True,
) -> dict:
    """Run one GSC-driven learning cycle.

    Uses LearningLoopOrchestrator when available (default), otherwise
    falls back to the legacy direct GSC→evaluate→rewrite path.

    Args:
        keyword: Single keyword, or None to process all articles in memory.
        threshold: Articles with performance score below this get rewritten.
        dry_run: Report only, no file changes.
        use_orchestrator: If True (default), use LearningLoopOrchestrator.
    """
    if use_orchestrator and _HAS_ORCHESTRATOR:
        return _run_orchestrated_cycle(keyword=keyword, threshold=threshold, dry_run=dry_run)

    return _run_legacy_cycle(keyword=keyword, threshold=threshold, dry_run=dry_run)


def _run_orchestrated_cycle(
    keyword: str | None = None,
    threshold: int = 50,
    dry_run: bool = False,
) -> dict:
    """Run learning cycle through the LearningLoopOrchestrator."""
    from agent_core.learning_loop import LearningLoopOrchestrator

    _header(f"Learning Loop (Orchestrated)  [{datetime.now().strftime('%Y-%m-%d %H:%M')}]")

    loop = LearningLoopOrchestrator()
    results: dict[str, Any] = {
        "cycle_date": datetime.now().isoformat(),
        "articles_checked": 0,
        "articles_rewritten": 0,
        "articles_stable": 0,
        "dry_run": dry_run,
        "feedback_source": "gsc_api",
        "details": [],
        "orchestrator": True,
    }

    if keyword:
        keywords = [keyword]
    else:
        mem = mem_module.load()
        keywords = list(dict.fromkeys(
            a.get("keyword", "") for a in mem.get("articles_written", []) if a.get("keyword")
        ))

    if not keywords:
        _err("No keywords to process")
        return {**results, "error": "no_keywords"}

    for kw in keywords:
        print(c("cyan", f"\n  ── {kw[:55]}"))

        try:
            result = loop.run_cycle(
                keyword=kw,
                article_text="",
                article_html="",
                model="local",
                niche="",
                dry_run=dry_run,
                force=False,
            )
        except Exception as e:
            _err(f"Cycle failed for '{kw}': {e}")
            results["details"].append({"keyword": kw, "error": str(e)})
            results["articles_checked"] += 1
            continue

        _info(f"State: {result.state_before} → {result.state_after}")
        _info(f"Reward: {result.reward_value}")

        if result.gsc_position is not None:
            _info(f"GSC: #{result.gsc_position}  CTR: {result.gsc_ctr}%  Imp: {result.gsc_impressions}")

        if result.quality_score is not None:
            _info(f"Quality: {result.quality_score}/100")

        if result.strategy_updated:
            _info("Strategy patterns updated")

        if result.rewrite_triggered:
            _warn(f"Rewrite triggered — score below threshold ({threshold})")
            results["articles_rewritten"] += 1

            if not dry_run:
                _attempt_rewrite(
                    loop=loop,
                    keyword=kw,
                    threshold=threshold,
                    results=results,
                )
        else:
            _ok("Stable — no rewrite needed")
            results["articles_stable"] += 1

        results["details"].append(result.to_dict())
        results["articles_checked"] += 1

    _header("Cycle Complete (Orchestrated)")
    print(f"""
  ✓ Checked:   {results['articles_checked']}
  ✓ Stable:    {results['articles_stable']}
  ⚠ Rewritten: {results['articles_rewritten']}
  ──────────────────────
  Source: {results['feedback_source']}
  Date:   {results['cycle_date'][:19]}
""")

    _show_strategy_summary(loop)
    return results


def _run_legacy_cycle(
    keyword: str | None = None,
    threshold: int = 50,
    dry_run: bool = False,
) -> dict:
    """Legacy GSC→evaluate→rewrite path (original)."""
    try:
        from seo.gsc_client import GSCClient
        from config import GSC_CONFIG
        gsc = GSCClient(
            site_url=GSC_CONFIG.get("site_url", ""),
            credentials_path=GSC_CONFIG.get("credentials_path", ""),
        )
    except (ImportError, RuntimeError, FileNotFoundError) as e:
        _err(f"GSC not available: {e}")
        return {"error": str(e), "articles_processed": 0}

    from seo.google_feedback import (
        evaluate_real_performance,
        rewrite_decision,
        rewrite_with_real_data,
        estimate_ranking_potential,
    )

    memory = mem_module.load()
    articles = memory.get("articles_written", [])

    if keyword:
        articles = [a for a in articles if a["keyword"] == keyword]
        if not articles:
            _err(f"No article found for keyword: \"{keyword}\"")
            return {"error": "not_found", "articles_processed": 0}

    _header(f"GSC Learning Loop (Legacy)  [{datetime.now().strftime('%Y-%m-%d %H:%M')}]")
    print(f"  Articles: {len(articles)}")
    print(f"  Threshold: {threshold}/100")
    print(f"  Dry run:   {'YES' if dry_run else 'NO'}")
    print(f"  Source:    GSC API\n")

    results: dict[str, Any] = {
        "cycle_date": datetime.now().isoformat(),
        "articles_checked": 0,
        "articles_rewritten": 0,
        "articles_stable": 0,
        "dry_run": dry_run,
        "feedback_source": "gsc_api",
        "details": [],
        "orchestrator": False,
    }

    for article in articles:
        kw = article["keyword"]
        print(c("cyan", f"\n  ── {kw[:55]}"))

        gsc_data = gsc.get_keyword_data(kw)
        pos = gsc_data.get("position")
        ctr = gsc_data.get("ctr", 0)
        imp = gsc_data.get("impressions", 0)
        clicks = gsc_data.get("clicks", 0)

        if pos is None:
            _info("No GSC data yet for this keyword (0 impressions)")
            results["articles_checked"] += 1
            continue

        _info(f"Pos: #{pos}  CTR: {ctr}%  Imp: {imp}  Clicks: {clicks}")

        evaluation = evaluate_real_performance(gsc_data)
        score = evaluation["performance_score"]
        issues = evaluation["issues"]

        _info(f"Score: {score}/100  Status: {evaluation['status']}")
        for issue in issues:
            _warn(issue)

        if not dry_run:
            mem_module.record_performance(memory, kw, {
                "position": pos,
                "ctr": ctr,
                "impressions": imp,
                "clicks": clicks,
                "source": "gsc_api",
            })

        result_entry = {
            "keyword": kw,
            "score": score,
            "status": evaluation["status"],
            "issues": issues,
            "position": pos,
            "ctr": ctr,
            "impressions": imp,
            "clicks": clicks,
        }

        potential = estimate_ranking_potential(kw, pos)
        decision = rewrite_decision(evaluation, potential)

        if decision["should_rewrite"] and score < threshold:
            if dry_run:
                _warn(f"Would rewrite — {decision['reason']}")
                for ch in decision["changes_needed"]:
                    _info(f"  → {ch}")
                result_entry["would_rewrite"] = True
                result_entry["decision"] = decision
                results["articles_rewritten"] += 1
                results["details"].append(result_entry)
                results["articles_checked"] += 1
                continue

            article_html = _find_article_file(kw)
            if not article_html:
                _warn("Article not found on disk — skipping rewrite")
                result_entry["rewritten"] = False
                results["details"].append(result_entry)
                results["articles_checked"] += 1
                continue

            gap_angles = []
            try:
                from seo.content_gap import generate_gap_opportunities
                serp_data = {"common_headings": [], "entities": [], "content_gaps": []}
                gap_data = generate_gap_opportunities(kw, serp_data)
                gap_angles = gap_data.get("high_opportunity_angles", [])
            except Exception:
                log.warning("[LEARN] generate_gap_opportunities failed for '%s'", kw)

            rewrite_result = rewrite_with_real_data(
                article_html=article_html,
                keyword=kw,
                gsc_data=gsc_data,
                evaluation=evaluation,
                changes_needed=decision["changes_needed"],
                gap_angles=gap_angles,
            )
            changes = rewrite_result.get("changes_made", [])

            slug = kw.lower().replace(" ", "-").replace("/", "-")[:40]
            rev = len(article.get("performance_history", []))
            out_path = OUTPUT_DIR / f"{slug}_rev{rev}_gsc.html"
            out_path.write_text(rewrite_result["rewritten_html"], encoding="utf-8")

            _ok(f"Rewritten — {len(changes)} changes → {out_path}")
            for ch in changes:
                _info(f"  • {ch}")

            result_entry["rewritten"] = True
            result_entry["changes"] = changes
            result_entry["output_file"] = str(out_path)
            results["articles_rewritten"] += 1
        else:
            _ok("Performance acceptable — no rewrite needed")
            results["articles_stable"] += 1

        results["details"].append(result_entry)
        results["articles_checked"] += 1

    _header("Cycle Complete")
    print(f"""
  ✓ Checked:  {results['articles_checked']}
  ✓ Stable:   {results['articles_stable']}
  ⚠ Rewritten: {results['articles_rewritten']}
  ──────────────────────
  Source: {results['feedback_source']}
  Date:   {results['cycle_date'][:19]}
""")
    return results


def _attempt_rewrite(
    loop: Any,
    keyword: str,
    threshold: int,
    results: dict,
) -> None:
    """Attempt a rewrite for a decayed/underperforming article."""
    from seo.google_feedback import rewrite_with_real_data, evaluate_real_performance, estimate_ranking_potential, rewrite_decision
    from seo.gsc_client import GSCClient
    from config import GSC_CONFIG

    try:
        gsc = GSCClient(
            site_url=GSC_CONFIG.get("site_url", ""),
            credentials_path=GSC_CONFIG.get("credentials_path", ""),
        )
    except Exception as e:
        _warn(f"Cannot init GSC for rewrite: {e}")
        return

    article_html = _find_article_file(keyword)
    if not article_html:
        _warn("Article not found on disk — skipping rewrite")
        return

    gsc_data = gsc.get_keyword_data(keyword)
    pos = gsc_data.get("position")

    if pos is None:
        _info("No GSC position data — skipping rewrite")
        return

    evaluation = evaluate_real_performance(gsc_data)
    potential = estimate_ranking_potential(keyword, pos)
    decision = rewrite_decision(evaluation, potential)

    gap_angles = []
    try:
        from seo.content_gap import generate_gap_opportunities
        serp_data = {"common_headings": [], "entities": [], "content_gaps": []}
        gap_data = generate_gap_opportunities(keyword, serp_data)
        gap_angles = gap_data.get("high_opportunity_angles", [])
    except Exception:
        log.warning("[LEARN] generate_gap_opportunities failed for '%s'", keyword)

    rewrite_result = rewrite_with_real_data(
        article_html=article_html,
        keyword=keyword,
        gsc_data=gsc_data,
        evaluation=evaluation,
        changes_needed=decision["changes_needed"],
        gap_angles=gap_angles,
    )
    changes = rewrite_result.get("changes_made", [])

    slug = keyword.lower().replace(" ", "-").replace("/", "-")[:40]
    out_path = OUTPUT_DIR / f"{slug}_orchestrated.html"
    out_path.write_text(rewrite_result["rewritten_html"], encoding="utf-8")

    _ok(f"Rewritten — {len(changes)} changes → {out_path}")
    for ch in changes:
        _info(f"  • {ch}")


def _show_strategy_summary(loop: Any) -> None:
    """Print strategy evolution summary if available."""
    try:
        summary = loop.decay_summary()
        if summary.get("total_cycles", 0) > 0:
            print(c("dim", f"\n  Strategy: {summary['strategies_updated']} updated  "
                          f"Avg reward: {summary.get('avg_reward', 'N/A')}"))
    except Exception:
        log.debug("[LEARN] decay_summary() failed (expected during warm-up)")


def run_weekly_optimization(keywords: list[str] | None = None) -> dict:
    combined = {"cycles": [], "total_rewritten": 0, "total_checked": 0}
    targets = keywords or []
    if targets:
        for kw in targets:
            r = run_learning_cycle(keyword=kw)
            combined["cycles"].append(r)
            combined["total_rewritten"] += r.get("articles_rewritten", 0)
            combined["total_checked"] += r.get("articles_checked", 0)
    else:
        r = run_learning_cycle()
        combined["cycles"].append(r)
        combined["total_rewritten"] = r.get("articles_rewritten", 0)
        combined["total_checked"] = r.get("articles_checked", 0)
    return combined


def _find_article_file(keyword: str) -> str | None:
    if not OUTPUT_DIR.exists():
        return None
    slug = keyword.lower().replace(" ", "_").replace("/", "_")[:35]
    for f in OUTPUT_DIR.iterdir():
        if slug in f.stem.lower() and f.suffix in (".html", ".htm", ".md"):
            return f.read_text(encoding="utf-8")
    return None
