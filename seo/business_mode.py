"""
Autonomous SEO Business Mode — end-to-end niche domination.

Pipeline:
  1. pick_niche()          → choose profitable niche
  2. build_strategy()      → 50-article cluster map
  3. generate_all()        → write all articles with intelligent linking
  4. publish_and_track()   → monitor GSC for 14 days
  5. optimize_loop()       → rewrite based on real data
  6. roi_report()          → measure and report

Usage:
  python main.py --mode business --niche "tech" --articles 50
"""

import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import memory as mem_module
from llm_router import c

try:
    from seo.gsc_client import GSCClient
    _HAS_GSC = True
except ImportError:
    _HAS_GSC = False

try:
    from seo.google_feedback import (
        evaluate_real_performance,
        diagnose_issues,
        rewrite_decision,
        rewrite_with_real_data,
    )
    _HAS_REAL_FEEDBACK = True
except ImportError:
    _HAS_REAL_FEEDBACK = False

try:
    from seo.reporting import (
        generate_cluster_report,
        print_cluster_report,
    )
    _HAS_REPORTING = True
except ImportError:
    _HAS_REPORTING = False

try:
    from seo.learning_loop import run_learning_cycle
    _HAS_LEARNING = True
except ImportError:
    _HAS_LEARNING = False

import modules as agent

log = logging.getLogger("business_mode")

OUTPUT_DIR = Path("output")


def _header(title: str) -> None:
    line = "═" * 62
    print(f"\n{c('purple', line)}")
    print(c("bold", f"  {title}"))
    print(c("purple", line))


def _ok(msg: str) -> None:
    print(c("green", f"  ✓ {msg}"))


def _info(msg: str) -> None:
    print(c("dim", f"  · {msg}"))


def _warn(msg: str) -> None:
    print(c("yellow", f"  ⚠ {msg}"))


def _step(label: str) -> None:
    print(f"\n{c('cyan', '▸')} {c('bold', label)}")


def run_business_mode(
    niche: str,
    target_articles: int = 50,
    model: str = "local",
    gsc_site_url: str = "",
    gsc_credentials: str = "",
    learning_days: int = 14,
    dry_run: bool = False,
) -> dict:
    """Execute the full autonomous SEO business pipeline.

    Args:
        niche: Content niche (e.g. "tech", "health", "finance")
        target_articles: Total articles to generate (default: 50)
        model: LLM model to use
        gsc_site_url: Google Search Console site URL
        gsc_credentials: Path to GSC service account JSON
        learning_days: Days to wait before learning cycle
        dry_run: If True, plan only without writing

    Returns:
        dict with full campaign results
    """
    campaign_start = datetime.now()
    _header(f"Autonomous SEO Business Mode")
    print(f"""
  Niche:            {c('bold', niche)}
  Target articles:  {target_articles}
  Model:            {c('cyan', model)}
  Learning window:  {learning_days} days
  Dry run:          {'YES' if dry_run else 'NO'}
""")

    memory = mem_module.load()
    campaign = {
        "campaign_id": campaign_start.strftime("%Y%m%d_%H%M"),
        "niche": niche,
        "target_articles": target_articles,
        "model": model,
        "started_at": campaign_start.isoformat(),
        "phases": {},
    }

    # ── PHASE 1: Strategy ─────────────────────────────────────
    _step("Phase 1: Strategy — Building cluster map")
    seed_keywords = _generate_seed_keywords(niche)
    _info(f"Seed keywords: {', '.join(seed_keywords[:5])}...")

    clusters = {}
    for seed in seed_keywords[:5]:
        _info(f"Building cluster for: {seed}")
        cluster = agent.build_cluster(seed, niche, model)
        clusters[seed] = cluster

    campaign["phases"]["strategy"] = {
        "seed_keywords": seed_keywords,
        "clusters_built": len(clusters),
    }
    _ok(f"Strategy complete — {len(clusters)} clusters planned")

    # ── PHASE 2: Generate articles ────────────────────────────
    _step("Phase 2: Content Generation")
    all_keywords = _extract_all_keywords(clusters, target_articles)
    _info(f"Total keywords to write: {len(all_keywords)}")

    articles_written = 0
    for i, kw in enumerate(all_keywords):
        if articles_written >= target_articles:
            break

        print(c("cyan", f"\n  [{i+1}/{len(all_keywords)}] {kw[:55]}"))

        if dry_run:
            _info(f"Would write: {kw}")
            articles_written += 1
            continue

        try:
            comp = agent.analyze_competitors(kw, model)
            strategy = agent.decide_strategy(kw, comp, len(memory["articles_written"]), model)
            article = agent.write_article(kw, strategy, model)
            try:
                ctr_data = agent.optimize_ctr(kw, article, model)
            except BaseException:
                ctr_data = {"recommended_title": "", "recommended_description": ""}

            OUTPUT_DIR.mkdir(exist_ok=True)
            slug = kw.lower().replace(" ", "_").replace("/", "_")[:35]
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            filepath = OUTPUT_DIR / f"{slug}_{ts}.html"

            filepath.write_text(article, encoding="utf-8")

            mem_module.record_article(memory, kw, article, model)
            articles_written += 1
            _ok(f"[{articles_written}/{target_articles}] {kw}")

            # Small delay to avoid rate limits
            time.sleep(0.5)

        except Exception as e:
            _warn(f"Failed to write '{kw}': {e}")
            continue

    campaign["phases"]["generation"] = {
        "target": target_articles,
        "written": articles_written,
    }
    _ok(f"Generation complete — {articles_written} articles written")

    # ── PHASE 3: Intelligent Internal Linking ─────────────────
    _step("Phase 3: Internal Linking Map")
    link_map = _build_link_map(clusters, memory)
    campaign["phases"]["linking"] = {
        "total_links": sum(len(v) for v in link_map.values()),
    }
    if not dry_run:
        link_path = OUTPUT_DIR / f"internal_links_{campaign['campaign_id']}.json"
        link_path.write_text(json.dumps(link_map, ensure_ascii=False, indent=2), encoding="utf-8")
        _ok(f"Link map saved → {link_path}")
    _ok(f"Linking complete — {campaign['phases']['linking']['total_links']} connections mapped")

    # ── PHASE 4: Initial Learning Cycle ────────────────────────
    if _HAS_LEARNING and not dry_run:
        _step("Phase 4: Initial Learning Cycle")
        learn_result = run_learning_cycle(
            use_real_gsc=bool(gsc_site_url),
            gsc_site_url=gsc_site_url,
            gsc_credentials=gsc_credentials,
            threshold=60,
        )
        campaign["phases"]["initial_learn"] = {
            "checked": learn_result.get("articles_checked", 0),
            "rewritten": learn_result.get("articles_rewritten", 0),
        }
        _ok(f"Learning cycle done — {learn_result.get('articles_rewritten', 0)} rewritten")
    else:
        _info("Learning cycle skipped (dry run or missing modules)")

    # ── PHASE 5: ROI Report ────────────────────────────────────
    if _HAS_REPORTING and not dry_run:
        _step("Phase 5: ROI Report")
        report = generate_cluster_report(niche=niche)
        campaign["phases"]["roi"] = {
            "total_clusters": report.get("total_clusters", 0),
            "total_articles": report.get("total_articles", 0),
            "clusters": report.get("clusters", []),
            "authority_scores": report.get("authority_scores", {}),
        }
        print_cluster_report(report)

        report_path = OUTPUT_DIR / f"roi_report_{campaign['campaign_id']}.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        _ok(f"ROI report saved → {report_path}")

    # ── Summary ────────────────────────────────────────────────
    campaign["completed_at"] = datetime.now().isoformat()
    duration = (datetime.now() - campaign_start).total_seconds()

    _header("Business Mode Complete")
    print(f"""
  {c('green', '✓')} Niche:       {niche}
  {c('green', '✓')} Articles:    {articles_written}/{target_articles}
  {c('green', '✓')} Duration:    {duration:.0f}s ({duration/60:.1f} min)
  {c('green', '✓')} Clusters:    {len(clusters)}
  {c('green', '✓')} Links:       {campaign['phases']['linking']['total_links']}
  {c('dim', '─' * 40)}
  {c('dim', 'Campaign ID: ' + campaign['campaign_id'])}
""")

    # Save full campaign report
    campaign_path = OUTPUT_DIR / f"campaign_{campaign['campaign_id']}.json"
    campaign_path.write_text(json.dumps(campaign, ensure_ascii=False, indent=2), encoding="utf-8")
    _ok(f"Full campaign report → {campaign_path}")

    return campaign


def _generate_seed_keywords(niche: str) -> list[str]:
    """Generate seed keywords for a niche."""
    niche = niche.lower().strip()

    seed_map = {
        "tech": ["best laptops 2026", "best smartphones", "tech news", "software reviews", "AI tools"],
        "health": ["best vitamins", "health tips", "workout guide", "healthy diet", "mental health"],
        "finance": ["best credit cards", "investing tips", "saving money", "budgeting", "personal finance"],
        "marketing": ["SEO tips", "content marketing", "social media strategy", "email marketing", "digital marketing"],
        "travel": ["best travel destinations", "travel tips", "budget travel", "solo travel", "travel gear"],
        "food": ["healthy recipes", "meal prep", "diet plans", "cooking tips", "best kitchen tools"],
        "education": ["online courses", "study tips", "career guide", "skill development", "learning tools"],
        "lifestyle": ["productivity tips", "home office", "self improvement", "minimalism", "work life balance"],
    }

    if niche in seed_map:
        return seed_map[niche]

    return [
        f"best {niche} tools",
        f"{niche} guide",
        f"{niche} tips",
        f"what is {niche}",
        f"{niche} for beginners",
        f"{niche} review",
        f"{niche} vs alternatives",
        f"{niche} 2026",
    ]


def _extract_all_keywords(clusters: dict, max_count: int) -> list[str]:
    """Flatten cluster map into ordered keyword list."""
    keywords = []

    for seed, cluster in clusters.items():
        pillar = cluster.get("pillar", {})
        kw = pillar.get("keyword", "")
        if kw and kw not in keywords:
            keywords.append(kw)

        for item in cluster.get("clusters", []):
            kw = item.get("keyword", "")
            if kw and kw not in keywords:
                keywords.append(kw)

        for qw in cluster.get("quick_wins", []):
            if qw and qw not in keywords:
                keywords.append(qw)

    return keywords[:max_count]


def _build_link_map(clusters: dict, memory: dict) -> dict:
    """Build intelligent internal linking map across clusters."""
    link_map = {}

    for seed, cluster_data in clusters.items():
        pillar_kw = cluster_data.get("pillar", {}).get("keyword", "")
        if not pillar_kw:
            continue

        cluster_kws = [
            c.get("keyword", "")
            for c in cluster_data.get("clusters", [])
            if c.get("keyword")
        ]

        link_map[pillar_kw] = {
            "links_to": cluster_kws,
            "type": "pillar_to_clusters",
            "reasoning": "Pillar article links to all cluster articles",
        }

        for ckw in cluster_kws[:5]:
            related = [k for k in cluster_kws if k != ckw][:3]
            link_map[ckw] = {
                "links_to": [pillar_kw] + related,
                "type": "cluster_to_cluster",
                "reasoning": "Cluster article links to pillar + related clusters",
            }

    return link_map
