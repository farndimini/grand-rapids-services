#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║              SEO AGENT PRO — Multi-Model Edition                 ║
║                                                                  ║
║  Supports: Anthropic · OpenRouter · Groq                         ║
║  Models:   Claude · GPT-4o · Gemini · Llama · Mistral · DeepSeek║
╚══════════════════════════════════════════════════════════════════╝

Usage:
  python main.py --keyword "best laptop for students"
  python main.py --keyword "best laptop" --model gpt-4o --niche "tech"
  python main.py --mode cluster  --keyword "laptop"
  python main.py --mode calendar --keyword "tech" --niche "technology blog" --months 3
  python main.py --models          (list all available models)
  python main.py --stats           (show memory stats)
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import memory as mem_module
import modules as agent
from config import DEFAULT_MODEL, SETTINGS
from llm_router import c, list_models
from modules import PublishBlocked

# Self-learning loop
try:
    from seo.learning_loop import run_learning_cycle, run_weekly_optimization
    _HAS_LEARNING_LOOP = True
except ImportError:
    _HAS_LEARNING_LOOP = False

try:
    from seo_intelligence_layer import run_intelligence_cycle
    _HAS_INTELLIGENCE = True
except ImportError:
    _HAS_INTELLIGENCE = False

try:
    from seo.business_mode import run_business_mode
    _HAS_BUSINESS_MODE = True
except ImportError:
    _HAS_BUSINESS_MODE = False

try:
    from seo.reporting import (
        generate_cluster_report,
        print_cluster_report,
        generate_keyword_report,
        print_keyword_report,
        generate_rewrite_impact_report,
    )
    _HAS_REPORTING = True
except ImportError:
    _HAS_REPORTING = False

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
        estimate_ranking_potential,
    )
    _HAS_REAL_FEEDBACK = True
except ImportError:
    _HAS_REAL_FEEDBACK = False

# Enhanced pipeline layer (optional — adds caching, parallel, validation)
try:
    import pipeline_enhancer as _enhanced
    _HAS_ENHANCED = True
except ImportError:
    _HAS_ENHANCED = False

# Distributed execution layer (optional — Celery/Redis task queue)
try:
    import agent_core.distributed as _dist_module
    from agent_core.distributed import patch_pipeline as _patch_pipeline
    from agent_core.distributed import DistributedPipeline as _DistributedPipeline
    _HAS_DIST_MODULE = True
except ImportError:
    _HAS_DIST_MODULE = False
    _patch_pipeline = None
    _DistributedPipeline = None


def _has_distributed() -> bool:
    """Evaluate distributed availability at dispatch time.

    Reads agent_core.distributed._HAS_DISTRIBUTED dynamically instead of
    capturing the value at import time. This allows RuntimeQueue._ensure_queue()
    to update the flag (e.g., when Redis becomes available) and have main.py
    see the updated value at dispatch time.
    """
    if not _HAS_DIST_MODULE:
        return False
    try:
        return getattr(_dist_module, '_HAS_DISTRIBUTED', False)
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────
#  Output helpers
# ──────────────────────────────────────────────────────────────

OUTPUT_DIR = Path(SETTINGS["output_dir"])

def _format_html(content: str) -> str:
    """Apply professional CSS template to HTML articles automatically."""
    # Strip YAML frontmatter before checking for HTML
    raw = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)
    if not raw.strip().startswith("<!DOCTYPE"):
        return content
    title = ""
    desc = ""
    m = re.search(r'<title>(.*?)</title>', raw, re.IGNORECASE | re.DOTALL)
    if m: title = m.group(1).strip()
    m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', raw, re.IGNORECASE)
    if m: desc = m.group(1)
    body = raw
    m = re.search(r'(<h1[^>]*>.*?)</body>', body, re.IGNORECASE | re.DOTALL)
    if m: body = m.group(1)
    else:
        m = re.search(r'<body[^>]*>(.*?)</body>', body, re.IGNORECASE | re.DOTALL)
        if m: body = m.group(1)
    body = re.sub(r'<!--.*?-->', '', body, flags=re.DOTALL)
    body = re.sub(r'<meta\s+itemprop[^>]*>', '', body)
    body = re.sub(r'</?meta[^>]*>', '', body)
    body = body.strip()
    today = datetime.now().strftime("%B %d, %Y")
    today_iso = datetime.now().strftime("%Y-%m-%d")
    from config import SETTINGS as _cfg
    author_name = _cfg.get("author_name", "SEO Agent Pro")
    publisher_name = _cfg.get("site_name", author_name)
    site_url = _cfg.get("site_url", "https://yoursite.com").rstrip("/")
    meta_line = f'<div class="meta"><span>📅 {today}</span><span>✍️ {author_name}</span><span>⏱ {max(1, len(body.split()) // 200 + 1)} min read</span></div>'
    slug = re.sub(r"[^a-z0-9-]+", "-", title.lower()).strip("-")[:60]
    canonical = f"{site_url}/{slug}"
    import json as _json
    schema_data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": desc,
        "author": {"@type": "Person", "name": author_name},
        "datePublished": today_iso,
        "dateModified": today_iso,
        "publisher": {"@type": "Organization", "name": publisher_name},
    }
    schema = f'<script type="application/ld+json">\n{_json.dumps(schema_data, ensure_ascii=False, indent=2)}\n</script>'
    # Extract existing JSON-LD schemas from body (FAQPage, ItemList) and append them
    existing_jsonld = re.findall(
        r'<script\s+type="application/ld\+json"[^>]*>.*?</script>',
        raw, re.IGNORECASE | re.DOTALL
    )
    for es in existing_jsonld:
        if '"@type"' in es:
            schema += '\n' + es
    css = """<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.8; color: #1a1a2e; background: #f0f2f5; padding: 20px; }
.container { max-width: 820px; margin: 0 auto; background: #fff; padding: 45px; border-radius: 12px; box-shadow: 0 2px 20px rgba(0,0,0,0.08); }
h1 { font-size: 2.1em; color: #1a1a2e; margin-bottom: 8px; line-height: 1.3; font-weight: 700; }
h2 { font-size: 1.5em; color: #16213e; margin-top: 40px; margin-bottom: 15px; padding-left: 12px; border-left: 4px solid #0f3460; }
h3 { font-size: 1.2em; color: #0f3460; margin-top: 25px; margin-bottom: 10px; }
p { margin-bottom: 16px; color: #333; }
ul, ol { margin: 10px 0 20px 25px; }
li { margin-bottom: 8px; color: #333; }
a { color: #0f3460; } a:hover { color: #e94560; }
.meta { color: #666; font-size: 0.9em; margin-bottom: 30px; border-bottom: 1px solid #eee; padding-bottom: 15px; display: flex; gap: 15px; flex-wrap: wrap; }
.meta span { display: inline-flex; align-items: center; gap: 4px; }
.toc { background: #f0f4ff; padding: 20px 25px; border-radius: 8px; margin: 20px 0 30px; }
.toc h3 { margin-top: 0; color: #1a1a2e; }
.toc a { color: #0f3460; text-decoration: none; display: block; padding: 6px 0; border-bottom: 1px solid #e0e7ff; }
.toc a:last-child { border-bottom: none; } .toc a:hover { color: #e94560; padding-left: 4px; }
.comparison-table { width: 100%; border-collapse: collapse; margin: 20px 0; border-radius: 8px; overflow: hidden; }
.comparison-table th { background: #0f3460; color: #fff; padding: 12px 10px; text-align: left; }
.comparison-table td { padding: 10px; border-bottom: 1px solid #ddd; color: #333; }
.comparison-table tr:nth-child(even) { background: #f8f9fa; }
.pro-con { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 20px 0; }
.pro, .con { padding: 18px; border-radius: 8px; }
.pro { background: #e8f5e9; border-left: 4px solid #2e7d32; }
.con { background: #fbe9e7; border-left: 4px solid #c62828; }
.verdict { background: linear-gradient(135deg, #0f3460, #1a1a2e); color: #fff; padding: 28px; border-radius: 8px; margin: 25px 0; }
.verdict h3 { color: #e94560; margin-top: 0; } .verdict p, .verdict strong { color: #fff; }
.faq-item { border: 1px solid #ddd; border-radius: 8px; margin: 12px 0; overflow: hidden; }
.faq-q { background: #f0f4ff; padding: 14px 16px; font-weight: 600; color: #1a1a2e; }
.faq-a { padding: 14px 16px; background: #fff; color: #333; }
.note { background: #fff8e1; border-left: 4px solid #ffc107; padding: 14px 18px; border-radius: 4px; margin: 18px 0; }
.tip { background: #e8f5e9; border-left: 4px solid #28a745; padding: 14px 18px; border-radius: 4px; margin: 18px 0; }
.warning { background: #fbe9e7; border-left: 4px solid #c62828; padding: 14px 18px; border-radius: 4px; margin: 18px 0; }
.highlight { background: #e8f5e9; padding: 2px 6px; border-radius: 3px; font-weight: 600; color: #1a3d2b; }
.benchmark { background: #1a1a2e; color: #fff; padding: 20px; border-radius: 8px; margin: 20px 0; }
.benchmark th, .benchmark td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #333; color: #fff; }
.benchmark th { color: #e94560; } .benchmark .highlight { background: #1d6b4a; color: #b8f0d4; }
.ext-screenshot { max-width:100%; border-radius:8px; margin:10px 0; box-shadow:0 2px 12px rgba(0,0,0,0.1); border:1px solid #e0e0e0; }
.ext-category { background:#f0f4ff; padding:15px 20px; border-radius:8px; margin:30px 0 20px; border-left:5px solid #0f3460; }
.ext-category h3 { margin:0; color:#0f3460; font-size:1.2em; }
.ext-card { background:#fafbfc; border:1px solid #e8ecf1; border-radius:10px; padding:20px; margin:15px 0; }
.ext-card:hover { box-shadow:0 4px 15px rgba(0,0,0,0.08); }
.ext-rating { display:inline-block; background:#1a73e8; color:#fff; padding:2px 10px; border-radius:12px; font-size:0.85em; font-weight:600; }
.ext-price { display:inline-block; background:#e8f5e9; color:#2e7d32; padding:2px 10px; border-radius:12px; font-size:0.85em; font-weight:600; }
.quick-answer-box { background:#e8f4fd; border-left:5px solid #0f3460; border-radius:8px; padding:20px 24px; margin:20px 0; font-size:1.05em; line-height:1.7; }
.quick-answer-box strong { color:#0f3460; }
.flowchart { background:#f8f9fa; border:2px solid #e0e7ff; border-radius:12px; padding:24px; margin:25px 0; text-align:center; }
.flow-btn { display:inline-block; background:#0f3460; color:#fff; padding:10px 20px; border-radius:6px; margin:6px; font-weight:600; font-size:0.95em; }
.flow-btn:hover { background:#e94560; color:#fff; }
.flow-arrow { display:inline-block; font-size:1.5em; color:#0f3460; margin:4px 0; font-weight:700; }
.hidden-costs { background:#fef3e2; border-left:4px solid #e67e22; border-radius:8px; padding:18px 22px; margin:20px 0; }
.hidden-costs h3 { color:#e67e22; margin-top:0; }
.step-guide { counter-reset:step-counter; list-style:none; padding-left:0; }
.step-guide li { counter-increment:step-counter; padding:12px 16px 12px 48px; margin:10px 0; background:#f8f9fa; border-radius:8px; position:relative; border:1px solid #e8ecf1; }
.step-guide li::before { content:counter(step-counter); position:absolute; left:12px; top:12px; background:#0f3460; color:#fff; width:26px; height:26px; border-radius:50%; text-align:center; font-size:0.85em; font-weight:700; line-height:26px; }
.ext-screenshot-wrapper { margin:20px 0; text-align:center; }
@media (max-width: 600px) { .container { padding: 20px; } h1 { font-size: 1.6em; } .pro-con { grid-template-columns: 1fr; } }
</style>"""
    words = body.split()
    toc_items = re.findall(r'<h2[^>]*>(.*?)</h2>', body, re.IGNORECASE | re.DOTALL)
    toc_html = ""
    if toc_items:
        lines = []
        for h in toc_items:
            text = re.sub(r'<[^>]+>', '', h).strip()
            hid = re.sub(r"[^\w\s-]", "", text).lower().replace(" ", "-")[:40]
            lines.append(f'<a href="#{hid}">{text}</a>')
            body = body.replace(f'<h2>{h}</h2>', f'<h2 id="{hid}">{h}</h2>', 1)
        toc_html = f'<div class="toc"><h3>📑 Table of Contents</h3>{"".join(lines)}</div>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title><meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">{schema}{css}</head>
<body><div class="container">
<h1>{title.replace('"', '&quot;')}</h1>
{meta_line}
{toc_html}
{body}
</div></body></html>"""

# Will be set in main() from --project argument
_PROJECT_ROOT: Path = Path("")

def _get_project_root(project_name: str = "") -> Path:
    """Return project root path if --project is set, else empty Path."""
    if project_name:
        slug = re.sub(r"[^a-z0-9-]+", "_", project_name.lower()).strip("_")
        return Path(__file__).parent / "projects" / slug
    return Path("")

def _save(filename: str, content: str) -> Path:
    save_dir = (_PROJECT_ROOT / "articles") if _PROJECT_ROOT else OUTPUT_DIR
    save_dir.mkdir(exist_ok=True)
    path = save_dir / filename
    # Apply HTML template to .html files and .md files containing HTML
    if filename.endswith(".html") or (filename.endswith(".md") and content.strip().startswith("<!DOCTYPE")):
        formatted = _format_html(content)
    else:
        formatted = content
    path.write_text(formatted, encoding="utf-8")
    print(c("green", f"  ✓ Saved → {path}"))
    return path

def _slug(text: str) -> str:
    return re.sub(r"[^\w\s-]", "", text).replace(" ", "_")[:35]

def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M")

def _header(title: str) -> None:
    line = "═" * 62
    print(f"\n{c('purple', line)}")
    print(c("bold", f"  {title}"))
    print(c("purple", line))


# ──────────────────────────────────────────────────────────────
#  Quality Gate — blocks template-bleed articles before output
# ──────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────
#  Run modes
# ──────────────────────────────────────────────────────────────

def run_full(keyword: str, niche: str, model: str, months: int) -> None:
    memory = mem_module.load()
    ts     = _ts()
    slug   = _slug(keyword)

    # ── Generation State — unified observability ─────────────
    try:
        from generation_state import GenerationState
        state = GenerationState(keyword, model)
        state.niche = niche or "auto-detect"
        state.mark_stage("pipeline_start")
        _HAS_STATE = True
    except ImportError:
        state = None
        _HAS_STATE = False

    _header(f"SEO Agent Pro — Full Pipeline  [{model}]")
    print(f"""
  Keyword   : {c('bold', keyword)}
  Niche     : {c('bold', niche or 'auto-detect')}
  Model     : {c('cyan', model)}
  Articles  : {len(memory['articles_written'])} in memory
  Time      : {datetime.now().strftime('%Y-%m-%d %H:%M')}
""")

    # ── 1. Competitor analysis ─────────────────────────────────
    if _HAS_STATE:
        state.mark_stage("competitor_analysis")
    competitor_data = agent.analyze_competitors(keyword, model)
    if _HAS_STATE:
        state.competitors_analyzed = competitor_data.get("_competitors_analyzed", 0)
        state.evidence_entity_count = len(competitor_data.get("entities", []))

    # ── 2. Strategy decision ───────────────────────────────────
    if _HAS_STATE:
        state.mark_stage("strategy_decision")
    strategy = agent.decide_strategy(
        keyword, competitor_data,
        len(memory["articles_written"]), model
    )
    if _HAS_STATE:
        state.strategy = strategy
        state.intent = strategy.get("intent", competitor_data.get("dominant_search_intent", "informational"))
        state.coverage_sections_before = len(strategy.get("required_sections", []))
        state.coverage_sections_after = len(strategy.get("required_sections", []))

    # ── 3. Write article ───────────────────────────────────────
    if _HAS_STATE:
        state.mark_stage("article_generation")
    article_blocked = False
    article_blocked_reason = ""
    ctr = {"recommended_title": "", "recommended_description": ""}
    article = ""
    try:
        article = agent.write_article(keyword, strategy, model)
    except PublishBlocked as _pb:
        print(c("red", f"  🛑 Article blocked: {_pb.reason}"))
        article_blocked = True
        article_blocked_reason = _pb.reason
        if _HAS_STATE:
            state.publish_blocked = True
            state.block_reason = _pb.reason
    else:
        # ── 3b. Quality gate ────────────────────────────────────
        quality = agent.validate_article_quality(article, keyword)
        if not quality["pass"]:
            for f in quality["failures"]:
                print(c("red", f"  ✗ {f}"))
            for w in quality["warnings"]:
                print(c("yellow", f"  ⚠ {w}"))
            print(c("red", f"  ✗ Quality score: {quality['score']}/100 — {quality['verdict']}"))
        else:
            print(c("green", f"  ✓ Quality score: {quality['score']}/100 — {quality['verdict']}"))

        _save(f"{slug}_{ts}.md", article)

        # ── 4. CTR optimization ────────────────────────────────────
        try:
            ctr = agent.optimize_ctr(keyword, article, model)
        except Exception as e:
            print(c("red", f"  ✗ CTR optimization skipped: {e}"))

    # ── 5. Keyword cluster (V3) ────────────────────────────────
    cluster = agent.build_cluster(keyword, niche, model)
    _save(f"cluster_{slug}_{ts}.json",
          json.dumps(cluster, ensure_ascii=False, indent=2))

    # ── 6. Content calendar (V3) ───────────────────────────────
    if niche:
        calendar = agent.build_calendar(keyword, niche, months, model)
        _save(f"calendar_{slug}_{ts}.json",
              json.dumps(calendar, ensure_ascii=False, indent=2))
    else:
        calendar = []

    # ── 7. Authority score (V3) ────────────────────────────────
    if niche and len(memory["articles_written"]) >= 1:
        authority = agent.score_authority(niche, memory["articles_written"], model)
        mem_module.record_authority(memory, niche, authority)

    # ── 8. Update memory ───────────────────────────────────────
    if not article_blocked:
        mem_module.record_article(memory, keyword, article, model)
    mem_module.record_cluster(memory, keyword, cluster)

    # ── Final report ───────────────────────────────────────────
    status_tag = "🛑 BLOCKED" if article_blocked else "✓"
    report = f"""# SEO Agent Pro — Report
**Keyword:** {keyword}
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Model:** {model}
**Status:** {status_tag}

---

## Recommended Title
{ctr.get('recommended_title', '')}

## Recommended Meta Description
{ctr.get('recommended_description', '')}

## Strategy
- Type: {strategy.get('strategy', '').upper()}
- Angle: {strategy.get('unique_angle', '')}
- Target length: {strategy.get('ideal_length', 0)} words
- Reasoning: {strategy.get('reasoning', '')}

## Keyword Cluster
- Pillar: {cluster.get('pillar', {}).get('keyword', '')}
- Supporting topics: {len(cluster.get('clusters', []))}
- Quick wins: {len(cluster.get('quick_wins', []))}

## Output Files
{'🛑 Article blocked — not saved' if article_blocked else '- Article  : output/' + slug + '_' + ts + '.md'}
- Cluster  : output/cluster_{slug}_{ts}.json
{'- Calendar: output/calendar_' + slug + '_' + ts + '.json' if niche else ''}
- Report   : output/report_{slug}_{ts}.md

---
*Generated by SEO Agent Pro*
"""

    _save(f"report_{slug}_{ts}.md", report)

    # ── Save generation state for replay ──────────────────────
    if _HAS_STATE and article:
        state.article = article
        state.word_count = len(article.split())
        state.mark_stage("pipeline_end")
        state_path = state.save()
        state_line = f"  State     →  {state_path}"
    else:
        state_line = ""

    _header("Pipeline Complete")
    _abr = article_blocked_reason if article_blocked else ""
    article_line = f"  {c('red', '🛑')} Article   →  BLOCKED ({_abr})" if article_blocked else f"  {c('green', '✓')} Article   →  output/{slug}_{ts}.md"
    # Show state summary if available
    state_summary = ""
    if _HAS_STATE and state:
        state_summary = f"""
  {c('cyan', 'Editorial Score')}: {state.editorial_score}/100 → {state.editorial_verdict}
  {c('cyan', 'Benchmarks')}:     {state.benchmark_overall}/100
  {c('cyan', 'Temporal')}:       {state.temporal_violations_high} violations"""
    print(f"""
{article_line}
{state_line}
  {c('green', '✓')} Cluster   →  output/cluster_{slug}_{ts}.json
  {c('green', '✓')} Report    →  output/report_{slug}_{ts}.md
  {c('green', '✓')} Memory    →  {SETTINGS['memory_file']}
{state_summary}
  {c('yellow', 'Summary')}
  Clusters ready  : {len(cluster.get('clusters', []))}
  Calendar items  : {len(calendar)}
  Total articles  : {len(memory['articles_written'])}
""")


def run_article(keyword: str, model: str) -> None:
    memory = mem_module.load()
    ts     = _ts()
    slug   = _slug(keyword)

    _header(f"Article Mode  [{model}]")

    comp     = agent.analyze_competitors(keyword, model)
    strategy = agent.decide_strategy(keyword, comp, len(memory["articles_written"]), model)
    article_blocked = False
    article_blocked_reason = ""
    ctr = {"recommended_title": keyword, "recommended_description": ""}
    article = ""
    try:
        article = agent.write_article(keyword, strategy, model)
    except PublishBlocked as _pb:
        print(c("red", f"  🛑 Article blocked: {_pb.reason}"))
        article_blocked = True
        article_blocked_reason = _pb.reason
    else:
        quality = agent.validate_article_quality(article, keyword)
        if not quality["pass"]:
            for f in quality["failures"]:
                print(c("red", f"  ✗ {f}"))
            for w in quality["warnings"]:
                print(c("yellow", f"  ⚠ {w}"))
            print(c("red", f"  ✗ Quality score: {quality['score']}/100 — {quality['verdict']}"))
        else:
            print(c("green", f"  ✓ Quality score: {quality['score']}/100 — {quality['verdict']}"))

        try:
            ctr = agent.optimize_ctr(keyword, article, model)
        except Exception as e:
            print(c("red", f"  ✗ CTR optimization skipped: {e}"))

    if not article_blocked:
        output = f"""---
title: {ctr.get('recommended_title', keyword)}
description: {ctr.get('recommended_description', '')}
keyword: {keyword}
model: {model}
date: {datetime.now().strftime('%Y-%m-%d')}
---

{article}
"""
        _save(f"{slug}_{ts}.md", output)
        mem_module.record_article(memory, keyword, article, model)
    else:
        print(c("red", f"  🛑 Article '{keyword}' blocked — not saved"))


def run_cluster(keyword: str, niche: str, model: str) -> None:
    memory = mem_module.load()
    ts     = _ts()
    slug   = _slug(keyword)

    _header(f"Cluster Mode  [{model}]")

    result = agent.build_cluster(keyword, niche, model)
    _save(f"cluster_{slug}_{ts}.json", json.dumps(result, ensure_ascii=False, indent=2))
    mem_module.record_cluster(memory, keyword, result)


def run_calendar(keyword: str, niche: str, months: int, model: str) -> None:
    ts   = _ts()
    slug = _slug(keyword)

    _header(f"Calendar Mode  [{model}]")

    result = agent.build_calendar(keyword, niche or keyword, months, model)
    _save(f"calendar_{slug}_{ts}.json", json.dumps(result, ensure_ascii=False, indent=2))


# ──────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="seo-agent",
        description="SEO Agent Pro — Multi-model SEO content pipeline",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["full", "article", "cluster", "calendar", "learn", "optimize",
                  "business", "report", "keyword-report", "gsc-fetch", "gsc-feedback",
                  "intelligence", "production", "evolve", "strategy", "track",
                  "multi-agent", "prompt-evolve"],
        default="full",
        help=(
            "full           → Complete V2+V3 pipeline  (default)\n"
            "article        → Single article only\n"
            "cluster        → Keyword cluster map only\n"
            "calendar       → Publishing calendar only\n"
        "learn          → Run learning cycle on one keyword\n"
        "optimize       → Run learning cycle on all stored articles\n"
        "intelligence   → External intelligence layer (serp scrape + crawl + analyze + rewrite)\n"
        "production     → Full production cycle (stealth scrape + safety + evolution)\n"
        "evolve         → Run evolution engine across all articles\n"
        "strategy       → Strategic intelligence (keyword investment + portfolio)\n"
            "track          → Live SERP position tracking (use --keyword --url)\n"
            "multi-agent    → Run multi-agent pipeline (researcher→strategist→writer→optimizer→critic)\n"
            "prompt-evolve  → Prompt version history demonstration\n"
            "business       → Autonomous SEO Business Mode (niche domination)\n"
            "report         → Show cluster ROI report\n"
            "keyword-report → Show performance for one keyword (use --keyword)\n"
            "gsc-fetch      → Fetch GSC data for a keyword (use --keyword)\n"
            "gsc-feedback    → Run feedback loop on one keyword with GSC data"
        ),
    )
    parser.add_argument("--keyword", help='Target keyword, e.g. "best laptop for students"')
    parser.add_argument("--url",     default="", help='Our article URL (for track mode)')
    parser.add_argument("--niche",   default="", help='Content niche, e.g. "technology"')
    parser.add_argument("--model",   default=DEFAULT_MODEL, help=f"Model name from config.py (default: {DEFAULT_MODEL})")
    parser.add_argument("--months",  type=int, default=3, help="Calendar duration in months (default: 3)")
    parser.add_argument("--models",  action="store_true", help="List all available models and exit")
    parser.add_argument("--stats",   action="store_true", help="Show memory stats and exit")
    parser.add_argument("--dry-run", action="store_true", help="Learning loop: show changes without applying")
    parser.add_argument("--threshold", type=int, default=50, help="Learning loop: min performance score (default: 50)")
    parser.add_argument("--enhanced", action="store_true", help="Use enhanced pipeline (cache, parallel, auto-rewrite, validation)")
    parser.add_argument("--batch",     nargs="+", help="Batch mode: generate articles for multiple keywords")
    parser.add_argument("--no-parallel", action="store_true", help="Disable parallel execution even in enhanced mode")
    parser.add_argument("--no-rewrite",  action="store_true", help="Disable auto-rewrite loop even in enhanced mode")
    parser.add_argument("--distributed", action="store_true", help="Route tasks through Celery/Redis worker queue (falls back to in-process)")
    parser.add_argument("--health-check", action="store_true", help="Show system-wide health diagnostics")
    parser.add_argument("--metrics", action="store_true", help="Show metrics collector summary")
    parser.add_argument("--metrics-history", action="store_true", help="Show metrics history for last 7 days")
    parser.add_argument("--provider-analysis", action="store_true", help="Show provider health analysis")
    parser.add_argument("--trend-report", action="store_true", help="Show quality trend report for last 30 days")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate article quality vs SERP")
    parser.add_argument("--benchmark", action="store_true", help="Run full benchmark on keyword")
    parser.add_argument("--leaderboard", action="store_true", help="Show evaluation leaderboard")
    parser.add_argument("--replay", type=str, default="", help="Replay a saved GenerationState file for debugging")
    parser.add_argument("--list-replays", action="store_true", help="List all available replay files")
    parser.add_argument("--project", type=str, default="", help='Project name (e.g. "grand_rapids"). Output goes to projects/{name}/')

    args = parser.parse_args()

    # Set up project root if --project is specified
    global _PROJECT_ROOT
    if args.project:
        slug = re.sub(r"[^a-z0-9-]+", "_", args.project.lower()).strip("_")
        _PROJECT_ROOT = Path(__file__).parent / "projects" / slug

    # ── Info-only flags ────────────────────────────────────────
    if args.models:
        print(f"\n{c('bold', 'Available Models')}")
        list_models()
        print()
        return

    if args.stats:
        memory = mem_module.load()
        mem_module.print_stats(memory)

        # Enhanced stats via agent_core layers
        try:
            from agent_core.memory_index import MemoryIndex
            idx = MemoryIndex()
            s = idx.summary()
            trend = idx.trend_analysis()
            dups = idx.find_duplicates(threshold=0.75)
            print(f"""
  {c('bold', 'Enhanced Stats (agent_core)')}
  ─────────────────────────────
  Indexed keywords:     {s.get('indexed_keywords', 0)}
  Indexed niches:       {len(s.get('indexed_niches', []))}
  Models used:          {', '.join(s.get('models_used', []))}
  Avg word count:       {s.get('avg_word_count', 0):.0f}
  Duplicates detected:  {len(dups)}
  Trend avg position:   {trend.get('avg_position', '?')}
  Trend avg CTR:        {trend.get('avg_ctr', '?')}
  Underperformers:      {trend.get('underperformers', '?')}
  Stars (top-3):        {trend.get('stars', '?')}
""")
        except Exception as e:
            print(c("dim", f"  · Enhanced stats unavailable: {e}"))
        return

    if args.health_check:
        from agent_core.health_dashboard import HealthDashboard
        dash = HealthDashboard()
        dash.print_report()
        return

    if args.metrics:
        from agent_core.metrics_collector import get_collector
        get_collector().print_summary()
        return

    if args.metrics_history:
        from agent_core.metrics_store import MetricsStore
        store = MetricsStore()
        summary = store.full_summary(days=7)
        print(f"\n{'═' * 56}")
        print("  METRICS HISTORY (Last 7 Days)")
        print(f"{'═' * 56}")
        for provider, stats in summary["provider_health"].items():
            print(f"  {provider:12s}  calls={stats['calls']:>4d}  rate={stats['success_rate']:.0%}  "
                  f"cost=${stats['total_cost_usd']:.4f}")
        print(f"  Cache hit rates: {summary['cache_ratio']}")
        qt = summary["quality_trend"]
        if qt["count"]:
            print(f"  Quality: avg={qt['avg_score']}/100  reward={qt['avg_reward']}")
        rt = summary["rewrite_effectiveness"]
        if rt["count"]:
            print(f"  Rewrites: {rt['count']} avg_improvement={rt['avg_improvement']:.1f}pts")
        print(f"  Fallback failures: {summary['fallback_failures']}")
        print(f"{'═' * 56}\n")
        return

    if args.provider_analysis:
        from agent_core.metrics_store import MetricsStore
        store = MetricsStore()
        health = store.get_provider_health(days=7)
        print(f"\n{'═' * 56}")
        print("  PROVIDER ANALYSIS")
        print(f"{'═' * 56}")
        for prov, s in sorted(health.items(), key=lambda x: x[1]["success_rate"], reverse=True):
            status = "HEALTHY" if s["success_rate"] >= 0.9 else "DEGRADED" if s["success_rate"] >= 0.5 else "CRITICAL"
            print(f"  {prov:12s}  {status:8s}  rate={s['success_rate']:.0%}  "
                  f"lat={s['avg_latency_ms'] or '?':>5}ms  cost=${s['total_cost_usd']:.4f}")
        print(f"{'═' * 56}\n")
        return

    if args.trend_report:
        from agent_core.metrics_store import MetricsStore
        store = MetricsStore()
        qt = store.get_quality_trend(days=30)
        print(f"\n{'═' * 56}")
        print("  TREND REPORT (Last 30 Days)")
        print(f"{'═' * 56}")
        if qt["count"]:
            print(f"  Articles evaluated: {qt['count']}")
            print(f"  Avg quality:        {qt['avg_score']}/100")
            print(f"  Min/Max:            {qt['min_score']} / {qt['max_score']}")
            print(f"  Median:             {qt['p50_score']}")
            print(f"  Avg reward:         {qt['avg_reward']}")
        else:
            print("  No quality data recorded yet.")
        print(f"{'═' * 56}\n")
        return

    if args.evaluate or args.benchmark:
        if not args.keyword:
            parser.error("--keyword is required for --evaluate/--benchmark")
        from evaluation.benchmark_runner import BenchmarkRunner
        from seo.research_engine import build_serp_analysis
        runner = BenchmarkRunner()
        serp = None
        try:
            serp = build_serp_analysis(args.keyword)
        except Exception as _e:
            print(c("yellow", f"  ⚠ SERP analysis failed: {_e}"))
        # Load last generated article for keyword from memory
        mem = mem_module.load()
        article = ""
        for a in reversed(mem.get("articles_written", [])):
            if a.get("keyword") == args.keyword:
                # Memory doesn't store full article; generate fresh in benchmark mode
                break
        # For --benchmark, generate one fresh
        if args.benchmark or not article:
            comp = agent.analyze_competitors(args.keyword, args.model)
            strategy = agent.decide_strategy(args.keyword, comp, len(mem["articles_written"]), args.model)
            try:
                article = agent.write_article(args.keyword, strategy, args.model)
            except PublishBlocked as _pb:
                print(c("red", f"  🛑 Benchmark blocked: {_pb.reason}"))
                return
        report = runner.evaluate(article, args.keyword, serp, model=args.model)
        print(f"\n{'═' * 56}")
        print(f"  BENCHMARK REPORT: {args.keyword}")
        print(f"{'═' * 56}")
        print(f"  Final Score:  {report.final_score}/100  [{report.verdict}]")
        print(f"  Dimensions:")
        for dim, res in report.dimension_scores.items():
            print(f"    {dim:20s} {res.score:>6.1f}  {', '.join(res.feedback[:2])}")
        if report.regression_delta is not None:
            print(f"  Regression:   {report.regression_delta:+.1f} from baseline {report.baseline_score}")
        print(f"{'═' * 56}\n")
        return

    if args.leaderboard:
        from evaluation.benchmark_runner import BenchmarkRunner
        runner = BenchmarkRunner()
        leaders = runner.leaderboard(args.keyword, top_n=10)
        print(f"\n{'═' * 56}")
        print("  EVALUATION LEADERBOARD")
        print(f"{'═' * 56}")
        for i, e in enumerate(leaders, 1):
            print(f"  #{i}  {e['model']:<20s}  {e['keyword'][:30]:<30s}  {e['final_score']:>5.1f}")
        if not leaders:
            print("  No benchmark data yet.")
        print(f"{'═' * 56}\n")
        return

    # ── Batch Mode (enhanced or distributed) — check before keyword requirement ──
    if args.batch:
        if args.distributed and _has_distributed():
            _header(f"Distributed Batch Article Generation  [{args.model}]")
            _dist_pipeline = _DistributedPipeline()
            articles = _dist_pipeline.run_batch_articles(args.batch, args.model)
            _header("Batch Complete")
            for kw in args.batch:
                status = "✓" if kw in articles else "✗"
                print(f"  {status} {kw[:50]}")
            return
        elif not _HAS_ENHANCED:
            print(c("red", "  ✗ Batch mode requires enhanced pipeline (install pipeline_enhancer.py)"))
            sys.exit(1)
        _header(f"Batch Article Generation  [{args.model}]")
        batch_out = str(_PROJECT_ROOT / "articles") if _PROJECT_ROOT else "grand_rapids"
        articles = _enhanced.run_batch_articles(args.batch, args.model, output_dir=batch_out)
        _header("Batch Complete")
        for kw in args.batch:
            status = "✓" if kw in articles else "✗"
            print(f"  {status} {kw[:50]}")
        return

    # ── Modes that do NOT require --keyword ────────────────────
    no_keyword_modes = ["business", "report", "optimize"]
    if args.mode in no_keyword_modes:
        pass  # keyword is optional for these
    elif not args.keyword and args.mode not in ("stats", "models") and not args.list_replays and not args.replay:
        parser.error("--keyword is required for this mode. Example: --keyword \"best laptop\"")

    # ── Replay mode ───────────────────────────────────────────
    if args.list_replays:
        try:
            from generation_state import GenerationState
            replays = GenerationState.list_replays()
            if not replays:
                print("  No replay files found.")
                return
            print(f"\n{c('bold', 'Replay Files')} ({len(replays)} found)")
            print(f"  {'Path':<35} {'Keyword':<30} {'Score':<6} {'Verdict':<10} {'Blocked':<8}")
            print(f"  {'─'*35} {'─'*30} {'─'*6} {'─'*10} {'─'*8}")
            for r in replays:
                blocked = "✓" if not r['blocked'] else "✗ BLOCKED"
                print(f"  {r['path'][:33]:<35} {r['keyword'][:28]:<30} {str(r['score']):<6} {str(r['verdict']):<10} {blocked:<8}")
        except ImportError:
            print("  Replay system not available.")
        return

    if args.replay:
        try:
            from generation_state import GenerationState
            state = GenerationState.load(args.replay)
            print(c("bold", f"\n  Replaying: {state.keyword}"))
            print(state.summary())
            if state.article:
                print(f"\n  Article preview ({state.word_count} words, first 500 chars):")
                print(f"  {state.article[:500]}...")
        except Exception as e:
            print(c("red", f"  ✗ Replay failed: {e}"))
        return

    # ── Dispatch ───────────────────────────────────────────────
    try:
        if args.mode == "full":
            if args.enhanced and _HAS_ENHANCED:
                _enhanced.run_full_enhanced(
                    keyword=args.keyword,
                    niche=args.niche,
                    model=args.model,
                    months=args.months,
                    parallel=not args.no_parallel,
                    auto_rewrite=not args.no_rewrite,
                    semantic_validate=True,
                )
            elif args.distributed and _has_distributed():
                _header(f"Distributed Full Pipeline  [{args.model}]")
                _dist_pipeline = _DistributedPipeline()
                _patch_pipeline(_dist_pipeline)
                result = _dist_pipeline.run_full_enhanced(
                    keyword=args.keyword,
                    niche=args.niche,
                    model=args.model,
                    months=args.months,
                )
                # Save output files from result if they exist
                if isinstance(result, dict):
                    print(c("green", f"  ✓ Distributed pipeline completed"))
            else:
                run_full(args.keyword, args.niche, args.model, args.months)

        elif args.mode == "article":
            run_article(args.keyword, args.model)

        elif args.mode == "cluster":
            run_cluster(args.keyword, args.niche, args.model)

        elif args.mode == "calendar":
            run_calendar(args.keyword, args.niche, args.months, args.model)

        # ── Business Mode ───────────────────────────────────
        elif args.mode == "business":
            if not _HAS_BUSINESS_MODE:
                print(c("red", "  ✗ Business mode not available (install seo/business_mode.py)"))
                sys.exit(1)
            from config import GSC_CONFIG
            run_business_mode(
                niche=args.niche or args.keyword or "general",
                target_articles=args.months * 4,  # ~4 articles per month target
                model=args.model,
                gsc_site_url=GSC_CONFIG.get("site_url", ""),
                gsc_credentials=GSC_CONFIG.get("credentials_path", ""),
                learning_days=14,
                dry_run=args.dry_run,
            )

        # ── ROI Report ──────────────────────────────────────
        elif args.mode == "report":
            if not _HAS_REPORTING:
                print(c("red", "  ✗ Reporting module not available"))
                sys.exit(1)
            report = generate_cluster_report(niche=args.niche)
            print_cluster_report(report)

        # ── Keyword Report ──────────────────────────────────
        elif args.mode == "keyword-report":
            if not _HAS_REPORTING:
                print(c("red", "  ✗ Reporting module not available"))
                sys.exit(1)
            if not args.keyword:
                parser.error("--keyword is required for keyword-report mode")
            report = generate_keyword_report(args.keyword)
            print_keyword_report(report)

        # ── GSC Fetch ───────────────────────────────────────
        elif args.mode == "gsc-fetch":
            if not _HAS_GSC:
                print(c("red", "  ✗ GSC client not available"))
                sys.exit(1)
            if not args.keyword:
                parser.error("--keyword is required for gsc-fetch mode")
            from config import GSC_CONFIG
            try:
                gsc = GSCClient(
                    site_url=GSC_CONFIG.get("site_url", ""),
                    credentials_path=GSC_CONFIG.get("credentials_path", ""),
                )
                data = gsc.get_keyword_data(args.keyword)
                _header(f"GSC Data for: {args.keyword}")
                pos = data.get("position")
                print(f"  Position:    {f'#{pos}' if pos else 'no data'}")
                print(f"  CTR:         {data.get('ctr', 0)}%")
                print(f"  Impressions: {data.get('impressions', 0)}")
                print(f"  Clicks:      {data.get('clicks', 0)}")
            except (RuntimeError, FileNotFoundError) as e:
                print(c("red", f"  ✗ {e}"))

        # ── GSC Feedback Loop ──────────────────────────────
        elif args.mode == "gsc-feedback":
            if not _HAS_GSC:
                print(c("red", "  ✗ GSC client not available"))
                sys.exit(1)
            if not args.keyword:
                parser.error("--keyword is required for gsc-feedback mode")
            from config import GSC_CONFIG

            # Try the new GscFeedbackOrchestrator first
            try:
                from agent_core.gsc_feedback import GscFeedbackOrchestrator, FeedbackDashboard
                orch = GscFeedbackOrchestrator()
                results = orch.poll_and_analyze([args.keyword], days=28)
                r = results.get(args.keyword, {})
                data = r.get("data", {})
                if "error" in data and data.get("source") == "error":
                    print(c("yellow", f"  ⚠ GSC unavailable: {data.get('error')}"))
                else:
                    _header(f"GSC Feedback Orchestrator — {args.keyword}")
                    dashboard = FeedbackDashboard()
                    dashboard.show_keyword_health(args.keyword, days=28)
                    if data:
                        print(f"\n  Fetched at: {data.get('_fetched_at', 'N/A')}")
                sys.exit(0)
            except ImportError:
                pass

            # Fall back to legacy feedback system
            if not _HAS_REAL_FEEDBACK:
                print(c("red", "  ✗ Legacy feedback modules not available"))
                sys.exit(1)
            try:
                gsc = GSCClient(
                    site_url=GSC_CONFIG.get("site_url", ""),
                    credentials_path=GSC_CONFIG.get("credentials_path", ""),
                )
                gsc_data = gsc.get_keyword_data(args.keyword)
                if gsc_data.get("position") is None:
                    print(c("yellow", f"  ⚠ No GSC data yet for '{args.keyword}'"))
                    sys.exit(0)
                evaluation = evaluate_real_performance(gsc_data)
                potential = estimate_ranking_potential(args.keyword, gsc_data.get("position", 50))
                decision = rewrite_decision(evaluation, potential)

                _header(f"GSC Feedback for: {args.keyword}")
                print(f"  Score:      {evaluation['performance_score']}/100")
                print(f"  Status:     {evaluation['status']}")
                print(f"  Action:     {evaluation['action']}")
                print(f"  Position:   #{evaluation['position']}")
                print(f"  CTR:        {evaluation['ctr']}%")
                print(f"  Issues:     {', '.join(evaluation['issues']) if evaluation['issues'] else 'none'}")
                print(f"  Rewrite:    {'YES' if decision['should_rewrite'] else 'NO'}")
                print(f"  Reason:     {decision['reason']}")
                if decision['changes_needed']:
                    print(f"  Changes:    {', '.join(decision['changes_needed'])}")
            except (RuntimeError, FileNotFoundError) as e:
                print(c("red", f"  ✗ {e}"))

        # ── Intelligence Layer ───────────────────────────────
        elif args.mode == "intelligence":
            if _HAS_INTELLIGENCE:
                _header("Intelligence Layer Mode (external)")
                run_intelligence_cycle(
                    keyword=args.keyword,
                    max_competitors=5,
                    dry_run=args.dry_run,
                    force_serp_fresh=False,
                )
            else:
                _header("Intelligence Engine Mode (local)")
                print(c("dim", "  Using local seo_intelligence.py — Phase 3 engines"))
                try:
                    from seo_intelligence import (
                        get_serp_gap_engine, get_citation_engine,
                        get_human_rewriter, get_conversion_optimizer,
                        get_authority_graph, get_ai_resistance,
                        get_pattern_tracker, get_intelligence_telemetry,
                    )
                    if args.keyword:
                        article_path = Path(args.keyword)
                        if article_path.exists():
                            article_text = article_path.read_text(encoding="utf-8")
                            _header(f"Analyzing: {article_path.name}")
                            hr = get_human_rewriter().detect_ai_patterns(article_text)
                            print(f"  AI detection risk:   {hr['ai_detection_risk']}")
                            print(f"  AI phrases found:    {hr['ai_phrase_count']}")
                            print(f"  Sentence length std: {hr['sentence_length_std']}")
                            print(f"  Repetitive starts:   {hr['repetitive_start_rate']}")
                            ai = get_ai_resistance().analyze(article_text)
                            print(f"  Human score:         {ai.overall_human_score}")
                            print(f"  Burstiness:          {ai.burstiness_score}")
                            print(f"  Entropy:             {ai.entropy_score}")
                            cc = get_citation_engine().analyze(article_text)
                            print(f"  Claims found:        {len(cc.claims)}")
                            print(f"  Claims supported:    {sum(1 for c in cc.claims.values() if c.is_supported)}")
                            cr = get_conversion_optimizer().analyze(args.keyword if not article_path.exists() else article_path.stem, article_text)
                            print(f"  CTAs:                {cr.ctas_found} ({cr.ctas_effective} effective)")
                            print(f"  Friction points:     {len(cr.friction_points)}")
                    else:
                        telemetry = get_intelligence_telemetry()
                        _header("Intelligence Telemetry")
                        for dim, data in telemetry.items():
                            if data:
                                status = ", ".join(f"{k}={v}" for k, v in data.items())
                                print(f"  {dim:20s}  {status}")
                except Exception as e:
                    print(c("red", f"  ✗ Intelligence analysis failed: {e}"))

        # ── Production Cycle ─────────────────────────────────
        elif args.mode == "production":
            if not _HAS_INTELLIGENCE:
                print(c("red", "  ✗ Intelligence layer not available"))
                return
            if not args.keyword:
                print(c("red", "  ✗ --keyword is required for production mode"))
                return
            _header("Production Engine Mode")
            try:
                from seo_intelligence_layer import run_production_cycle
                run_production_cycle(
                    keyword=args.keyword,
                    dry_run=args.dry_run,
                    max_competitors=5,
                    force_fresh_serp=False,
                )
            except Exception as e:
                print(c("red", f"  ✗ Production cycle failed: {e}"))

        # ── Evolution Engine ─────────────────────────────────
        elif args.mode == "evolve":
            if not _HAS_INTELLIGENCE:
                print(c("red", "  ✗ Intelligence layer not available"))
                return
            _header("Evolution Engine Mode")
            try:
                from seo_intelligence_layer import run_evolution_cycle
                run_evolution_cycle(dry_run=args.dry_run)
            except Exception as e:
                print(c("red", f"  ✗ Evolution cycle failed: {e}"))

        # ── Strategic Intelligence ────────────────────────────
        elif args.mode == "strategy":
            if not _HAS_INTELLIGENCE:
                print(c("red", "  ✗ Intelligence layer not available"))
                return
            _header("Strategic Intelligence Mode")
            try:
                from seo_intelligence_layer.strategic_intelligence import run_strategic_cycle
                keywords = [args.keyword] if args.keyword else None
                result = run_strategic_cycle(keywords=keywords, dry_run=args.dry_run)

                # Print summary
                if "error" not in result:
                    print(f"\n  Keywords evaluated: {result['keywords_evaluated']}")
                    print(f"  Investment level: {result.get('investment_level', '?')}")
                    print(f"  System health: {result.get('system_health', {}).get('system_health', '?')}/100")
                    print(f"  Budget used: {result.get('budget_allocation', {}).get('budget_used', 0)} units")
                    investable = sum(1 for e in result.get('evaluations', [])
                                     if e.get('investment_decision') in ('invest_heavy', 'invest_moderate'))
                    attackable = sum(1 for e in result.get('evaluations', [])
                                     if e.get('opportunity_attackable'))
                    print(f"  Investable keywords: {investable}")
                    print(f"  Attackable SERPs: {attackable}")
                else:
                    print(c("yellow", f"  {result['error']}"))
            except Exception as e:
                print(c("red", f"  ✗ Strategic cycle failed: {e}"))
                import traceback
                traceback.print_exc()

        # ── Live Tracking ─────────────────────────────────────
        elif args.mode == "track":
            if not _HAS_INTELLIGENCE:
                print(c("red", "  ✗ Intelligence layer not available"))
                return
            _header("Live SERP Tracker")
            try:
                from seo_intelligence_layer.live_tracker import LiveTracker
                from seo_intelligence_layer.storage import Storage

                storage = Storage()
                tracker = LiveTracker(storage=storage)

                if args.keyword and args.url:
                    # Track one keyword
                    result = tracker.track(args.keyword, args.url, force_fresh=not args.dry_run)
                    if result.get("error"):
                        print(c("red", f"  ✗ {result['error']}"))
                    elif result["found"]:
                        print(c("green", f"  ✓ Position #{result['position']} for '{args.keyword}'"))
                        signal = tracker.compute_learning_signal(args.keyword, args.url)
                        print(f"  Learning signal: {signal['action']} (confidence {signal['confidence']})")
                        print(f"  Reason: {signal['reason']}")
                    else:
                        print(c("yellow", f"  ⚠ URL not found in SERP for '{args.keyword}'"))

                elif args.keyword:
                    # Show trend only
                    trend = tracker.get_trend(args.keyword)
                    if trend["trend"] != "no_data":
                        print(f"  Current position: #{trend['current_position']}")
                        print(f"  Trend: {trend['trend']}")
                        print(f"  Drift 7d: {trend.get('drift_7d', 'N/A')}  Drift 30d: {trend.get('drift_30d', 'N/A')}")
                    else:
                        print(c("yellow", f"  ⚠ No tracking data for '{args.keyword}'"))

                else:
                    # Track all active articles
                    results = tracker.track_all_active()
                    found = sum(1 for r in results if r.get("found"))
                    print(f"  Tracked {len(results)} keywords, {found} found in SERP")
                    for r in results[:5]:
                        status = f"#{r['position']}" if r['found'] else "NOT FOUND"
                        print(f"    {r['keyword'][:35]:35s} → {status}")

            except Exception as e:
                print(c("red", f"  ✗ Tracking failed: {e}"))
                import traceback
                traceback.print_exc()

        elif args.mode == "multi-agent":
            _header(f"Multi-Agent Pipeline  [{args.model}]")
            try:
                from agent_core.multi_agent import BoundedOrchestrator, Researcher, Strategist, Writer, Optimizer, Critic
                agents = {
                    "researcher": Researcher(),
                    "strategist": Strategist(),
                    "writer": Writer(),
                    "optimizer": Optimizer(),
                    "critic": Critic(),
                }
                orch = BoundedOrchestrator(
                    agents=agents,
                    execution_order=["researcher", "strategist", "writer", "optimizer", "critic"],
                    max_rounds=args.months,
                    agent_timeout=15.0,
                )
                result = orch.execute(
                    keyword=args.keyword,
                    niche=args.niche,
                    target_audience="general",
                )
                draft_info = f"{len(result.draft)} chars" if result.draft else "none"
                opt_info = f"{len(result.optimized_draft)} chars" if result.optimized_draft else "none"
                qual_info = f"{result.critique.get('quality_score', 'N/A')}/100" if result.critique else "N/A"
                print(f"\n  Keyword:     {args.keyword}")
                print(f"  Draft:       {draft_info}")
                print(f"  Optimized:   {opt_info}")
                print(f"  Quality:     {qual_info}")
                print(f"  Errors:      {len(result.errors)}")
                print(f"  Rounds:      {result.round}")
                bm = orch.benchmark()
                print(f"  Cost:        ${bm['total_cost']:.4f}")
                print(f"  Latency:     {bm['total_latency_ms']:.1f}ms")
            except Exception as e:
                print(c("red", f"  ✗ Multi-agent pipeline failed: {e}"))
                import traceback
                traceback.print_exc()

        elif args.mode == "prompt-evolve":
            _header(f"Prompt Evolution  [{args.model}]")
            try:
                from agent_core.prompt_evolution import VersionHistory, MutationRecord
                vh = VersionHistory(prompt_id=args.keyword)
                v1 = vh.add("Initial prompt content", metadata={"model": args.model})
                print(f"  Version 1: {v1.fingerprint}")
                v2 = vh.add("Improved prompt content", parent_version=1,
                             mutations=[MutationRecord(operation="replace", location="full",
                                                        old_text="Initial prompt content",
                                                        new_text="Improved prompt content",
                                                        reason="Better clarity")],
                             metadata={"model": args.model})
                print(f"  Version 2: {v2.fingerprint}")
                rollback = vh.rollback(1)
                print(f"  Rollback to v1: version {rollback.version if rollback else 'failed'}")
                print(f"  Total versions: {vh.count}")
                history = vh.to_dict()
                print(f"  History: {len(history['history'])} entries")
            except Exception as e:
                print(c("red", f"  ✗ Prompt evolution failed: {e}"))

        elif args.mode == "learn":
            if not _HAS_LEARNING_LOOP:
                print(c("red", "  ✗ Learning loop not available (install seo/learning_loop.py)"))
                sys.exit(1)
            _header("GSC Learning Loop")
            try:
                run_learning_cycle(
                    keyword=args.keyword,
                    threshold=args.threshold,
                    dry_run=args.dry_run,
                )
            except Exception as e:
                print(c("red", f"  ✗ {e}"))
        elif args.mode == "optimize":
            if not _HAS_LEARNING_LOOP:
                print(c("red", "  ✗ Learning loop not available (install seo/learning_loop.py)"))
                sys.exit(1)
            _header("GSC Full Optimization")
            try:
                run_learning_cycle(
                    threshold=args.threshold,
                    dry_run=args.dry_run,
                )
            except Exception as e:
                print(c("red", f"  ✗ {e}"))

    except PublishBlocked as _pb:
        print(c("red", f"  🛑 {_pb.reason}"))
        sys.exit(1)
    except KeyboardInterrupt:
        print(c("yellow", "\n\n  ⚠  Stopped by user."))
        sys.exit(0)


if __name__ == "__main__":
    main()
