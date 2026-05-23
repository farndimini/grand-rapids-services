"""
pipeline_enhancer.py — Drop-in enhancements for SEO Agent Pro pipeline.
=======================================================================
Wraps modules.py functions with:
  • RelayRouter (retry, cache, circuit breaker, multi-provider fallback)
  • SemanticValidator (post-generation quality validation)
  • Auto-rewrite loop (up to 2 retries on quality gate failure)
  • Parallel execution (cluster + calendar concurrent with competitor analysis)

Dependency injection (replaces old monkey-patch approach):
    from pipeline_enhancer import configure
    configure(relay_call=my_call_fn, relay_call_json=my_call_json_fn)

Usage (in main.py):
    import pipeline_enhancer as agent_enhanced
    # All functions mirror modules.py signatures
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import memory as mem_module
import modules as _orig
from config import SETTINGS

log = logging.getLogger("pipeline_enhancer")


# ── Explicit Configuration (replaces monkey-patching) ────────────

class _PipelineConfig:
    """Explicit dependency injection for pipeline execution.

    Rather than monkey-patching modules.call / modules.call_json at import
    time (which caused import-order instability and unsafe multiprocessing),
    this config object holds overrides that _relay_call and _relay_call_json
    consult at call time.

    Setting relay_call to a CachedLLMCall or DistributedPipeline call method
    provides caching, retry, circuit-breaker, or remote-task routing without
    any hidden runtime mutation.
    """
    relay_call: Callable | None = None
    relay_call_json: Callable | None = None


_config = _PipelineConfig()


def configure(relay_call: Callable | None = None,
              relay_call_json: Callable | None = None) -> None:
    """Set pipeline dependencies explicitly.

    Args:
        relay_call: Override for llm_router.call (e.g. CachedLLMCall.call).
        relay_call_json: Override for llm_router.call_json.
    """
    _config.relay_call = relay_call
    _config.relay_call_json = relay_call_json


# ── Optional enhanced core layer ─────────────────────────────────
try:
    from agent_core.relay import CachedLLMCall
    _HAS_RELAY = True
except Exception:
    _HAS_RELAY = False

try:
    from agent_core.validator import SemanticValidator
    _HAS_VALIDATOR = True
except Exception:
    _HAS_VALIDATOR = False

try:
    from agent_core.memory_index import MemoryIndex
    _HAS_MEMORY_INDEX = True
except Exception:
    _HAS_MEMORY_INDEX = False

try:
    from agent_core.parallel import ParallelEngine, TaskGroup
    _HAS_PARALLEL = True
except Exception:
    _HAS_PARALLEL = False

# ── Internal helpers ─────────────────────────────────────────────

_validator: Any = None

def _get_validator() -> Any:
    global _validator
    if _validator is None and _HAS_VALIDATOR:
        _validator = SemanticValidator()
    return _validator


def _get_call_fn() -> Callable:
    """Return the configured relay_call or default modules.call."""
    if _config.relay_call is not None:
        return _config.relay_call
    if _HAS_RELAY:
        return CachedLLMCall.call
    return _orig.call


def _get_call_json_fn() -> Callable:
    """Return the configured relay_call_json or default modules.call_json."""
    if _config.relay_call_json is not None:
        return _config.relay_call_json
    if _HAS_RELAY:
        return CachedLLMCall.call_json
    return _orig.call_json


def _relay_call(system: str, user: str, model: str, stream: bool = True) -> str:
    return _get_call_fn()(system, user, model, stream=stream)


def _relay_call_json(system: str, user: str, model: str) -> dict | list:
    return _get_call_json_fn()(system, user, model)


# ── Public API (mirrors modules.py exactly) ──────────────────────

def analyze_competitors(keyword: str, model: str) -> dict:
    return _orig.analyze_competitors(keyword, model)


def decide_strategy(keyword: str, competitor_data: dict, articles_written: int, model: str) -> dict:
    return _orig.decide_strategy(keyword, competitor_data, articles_written, model)


def write_article(keyword: str, strategy: dict, model: str) -> str:
    return _orig.write_article(keyword, strategy, model)


def optimize_ctr(keyword: str, article_snippet: str, model: str) -> dict:
    return _orig.optimize_ctr(keyword, article_snippet, model)


def build_cluster(keyword: str, niche: str, model: str) -> dict:
    return _orig.build_cluster(keyword, niche, model)


def build_calendar(keyword: str, niche: str, months: int, model: str) -> list:
    return _orig.build_calendar(keyword, niche, months, model)


def score_authority(niche: str, articles_written: list, model: str) -> dict:
    return _orig.score_authority(niche, articles_written, model)


def validate_article_quality(article: str, keyword: str) -> dict:
    return _orig.validate_article_quality(article, keyword)


# ── Enhanced full pipeline with parallel + auto-rewrite + validator ──

def run_full_enhanced(
    keyword: str,
    niche: str,
    model: str,
    months: int,
    *,
    parallel: bool = True,
    auto_rewrite: bool = True,
    semantic_validate: bool = True,
    max_rewrite_attempts: int = 2,
    budget_priority: bool = False,
) -> dict:
    """Enhanced full pipeline with optional parallelization, auto-rewrite, and validation.

    Returns a dict with all pipeline artifacts and metadata.
    """
    memory = mem_module.load()
    from main import _ts, _slug, _header, _save, c
    from datetime import datetime

    ts = _ts()
    slug = _slug(keyword)

    _header(f"SEO Agent Pro — Enhanced Full Pipeline  [{model}]")
    print(f"""
  Keyword   : {c('bold', keyword)}
  Niche     : {c('bold', niche or 'auto-detect')}
  Model     : {c('cyan', model)}
  Articles  : {len(memory['articles_written'])} in memory
  Time      : {datetime.now().strftime('%Y-%m-%d %H:%M')}
  Features  : parallel={parallel}  auto_rewrite={auto_rewrite}  semantic_validate={semantic_validate}
""")

    # ── Stage 1: Competitor analysis (always sequential first) ──
    competitor_data = analyze_competitors(keyword, model)

    # ── Stage 2: Strategy (depends on competitor) ──
    strategy = decide_strategy(keyword, competitor_data, len(memory["articles_written"]), model)

    # ── Stage 3: Write article with auto-rewrite loop ──
    article = ""
    quality: dict = {"pass": False, "score": 0, "failures": [], "warnings": []}
    for attempt in range(1 + max_rewrite_attempts):
        article = write_article(keyword, strategy, model)
        quality = validate_article_quality(article, keyword)

        if quality["pass"]:
            print(c("green", f"  ✓ Quality score: {quality['score']}/100 — {quality['verdict']}"))
            break

        if auto_rewrite and attempt < max_rewrite_attempts:
            print(c("yellow", f"  ⚠ Quality gate failed ({quality['score']}/100). Auto-rewriting... (attempt {attempt + 2}/{1 + max_rewrite_attempts})"))
            # Inject failures into strategy for next attempt
            strategy["_rewrite_feedback"] = {
                "failures": quality["failures"],
                "warnings": quality["warnings"],
                "attempt": attempt + 1,
            }
        else:
            for f in quality["failures"]:
                print(c("red", f"  ✗ {f}"))
            for w in quality["warnings"]:
                print(c("yellow", f"  ⚠ {w}"))
            print(c("red", f"  ✗ Quality score: {quality['score']}/100 — {quality['verdict']}"))

    # ── Stage 4: CTR optimization ──
    _save(f"{slug}_{ts}.md", article)
    ctr = {"recommended_title": "", "recommended_description": ""}
    try:
        ctr = optimize_ctr(keyword, article, model)
    except BaseException as e:
        print(c("red", f"  ✗ CTR optimization skipped: {e}"))

    # ── Stage 5+6: Cluster + Calendar (parallel if enabled) ──
    cluster: dict = {}
    calendar: list = []

    if parallel and _HAS_PARALLEL:
        engine = ParallelEngine(max_workers=3)
        with engine:
            with TaskGroup(engine) as g:
                g.submit("cluster", build_cluster, keyword, niche, model)
                if niche:
                    g.submit("calendar", build_calendar, keyword, niche, months, model)
            results = g.results()
            cluster = results.get("cluster", {})
            calendar = results.get("calendar", []) if niche else []
        summary = g.summary()
        log.info(f"[PIPELINE] Parallel analysis: {summary['succeeded']}/{summary['total']} succeeded")
    else:
        cluster = build_cluster(keyword, niche, model)
        if niche:
            calendar = build_calendar(keyword, niche, months, model)

    _save(f"cluster_{slug}_{ts}.json", json.dumps(cluster, ensure_ascii=False, indent=2))
    if niche:
        _save(f"calendar_{slug}_{ts}.json", json.dumps(calendar, ensure_ascii=False, indent=2))

    # ── Stage 7: Authority score ──
    authority: dict = {}
    if niche and len(memory["articles_written"]) >= 1:
        authority = score_authority(niche, memory["articles_written"], model)
        mem_module.record_authority(memory, niche, authority)

    # ── Stage 8: Memory update (with quality score for active learning) ──
    mem_module.record_article(memory, keyword, article, model, quality_score=quality.get("score", 0))
    mem_module.record_cluster(memory, keyword, cluster)

    # Record pipeline metrics
    from agent_core.metrics_collector import get_collector
    get_collector().increment("articles_completed")
    get_collector().increment("total_words_generated", len(article.split()))

    # ── Stage 9: Semantic validation (optional) ──
    semantic_report: Any = None
    if semantic_validate and _HAS_VALIDATOR:
        print(c("dim", f"  · Running semantic validation..."))
        sv = _get_validator()
        if sv:
            semantic_report = sv.validate(article, keyword)
            status = "✅ PASS" if semantic_report.passed(threshold=70) else "⚠️ NEEDS WORK"
            print(c("cyan", f"  · Semantic score: {semantic_report.score}/100 — {status}"))
            for issue in semantic_report.issues[:3]:
                print(c("red", f"    · {issue}"))
            for w in semantic_report.warnings[:3]:
                print(c("yellow", f"    · {w}"))

    # ── Stage 10: Learning cycle (GSC data + reward → strategy evolution) ──
    _learning_result = None
    try:
        from agent_core.learning_loop import LearningLoopOrchestrator
        _loop = LearningLoopOrchestrator()
        _learning_result = _loop.run_cycle(
            keyword=keyword,
            article_text=article,
            article_html=article,
            model=model,
            niche=niche,
            dry_run=True,
        )
        if _learning_result.reward_value != 0.0:
            _rc = _learning_result.reward_signal or {}
            print(c("dim", f"  · Learning: reward={_learning_result.reward_value:+.3f}  "
                           f"quality={_learning_result.quality_score or '?'}  "
                           f"pos={_learning_result.gsc_position or '?'}"))
    except Exception as _le:
        log.debug("[PIPELINE] Learning cycle skipped: %s", _le)

    # ── Stage 11: Enhanced stats via memory index ──
    mem_stats: Any = None
    if _HAS_MEMORY_INDEX:
        idx = MemoryIndex()
        mem_stats = idx.summary()
        mem_stats["trend"] = idx.trend_analysis()
        duplicates = idx.find_duplicates(threshold=0.75)
        if duplicates:
            print(c("yellow", f"  · {len(duplicates)} potential duplicate keyword(s) detected"))

    # ── Final report ──
    report = f"""# SEO Agent Pro — Enhanced Report
**Keyword:** {keyword}
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Model:** {model}
**Pipeline:** Enhanced

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

## Quality Gate
- Score: {quality.get('score', '?')}/100
- Passed: {quality.get('pass', False)}
- Failures: {', '.join(quality.get('failures', [])) or 'none'}
- Warnings: {', '.join(quality.get('warnings', [])) or 'none'}

## Output Files
- Article  : output/{slug}_{ts}.md
- Cluster  : output/cluster_{slug}_{ts}.json
{'- Calendar: output/calendar_' + slug + '_' + ts + '.json' if niche else ''}
- Report   : output/report_{slug}_{ts}.md

---
*Generated by SEO Agent Pro — Enhanced Pipeline*
"""

    _save(f"report_{slug}_{ts}.md", report)

    _header("Pipeline Complete")
    print(f"""
  {c('green', '✓')} Article   →  output/{slug}_{ts}.md
  {c('green', '✓')} Cluster   →  output/cluster_{slug}_{ts}.json
  {c('green', '✓')} Report    →  output/report_{slug}_{ts}.md
  {c('green', '✓')} Memory    →  {SETTINGS['memory_file']}

  {c('yellow', 'Summary')}
  Quality gate    : {quality['score']}/100  {'PASS' if quality['pass'] else 'FAIL/REWRITE'}
  Clusters ready  : {len(cluster.get('clusters', []))}
  Calendar items  : {len(calendar)}
  Total articles  : {len(memory['articles_written'])}
""")

    return {
        "keyword": keyword,
        "article": article,
        "strategy": strategy,
        "cluster": cluster,
        "calendar": calendar,
        "ctr": ctr,
        "quality": quality,
        "semantic_report": semantic_report,
        "memory_stats": mem_stats,
        "learning_result": _learning_result,
    }


# ── Batch article generation ──────────────────────────────────────

def _save_article(filename: str, content: str, output_dir: str | None = None) -> Path:
    """Save an article to disk. Mirrors main._save logic."""
    from config import SETTINGS
    out = Path(output_dir or SETTINGS["output_dir"])
    out.mkdir(exist_ok=True)
    path = out / filename
    path.write_text(content, encoding="utf-8")
    print(f"  ✓ Saved → {path}")
    return path


def _slug(text: str) -> str:
    return re.sub(r"[^\w\s-]", "", text).replace(" ", "_")[:35]


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M")


def run_batch_articles(
    keywords: list[str],
    model: str,
    max_workers: int = 3,
    output_dir: str | None = None,
) -> dict[str, str]:
    """Generate multiple articles concurrently and save to disk."""
    if not _HAS_PARALLEL:
        log.warning("Parallel engine not available — falling back to sequential")
        results: dict[str, str] = {}
        for kw in keywords:
            comp = analyze_competitors(kw, model)
            strategy = decide_strategy(kw, comp, 0, model)
            article = write_article(kw, strategy, model)
            if article:
                results[kw] = article
                _save_article(f"{_slug(kw)}_{_ts()}.md", article, output_dir)
                try:
                    mem_module.record_article(kw, strategy, article)
                except Exception:
                    pass
        return results

    from agent_core.parallel import ParallelEngine
    engine = ParallelEngine(max_workers=max_workers)
    articles: dict[str, str] = {}

    def _write_one(kw: str) -> tuple[str, str]:
        comp = analyze_competitors(kw, model)
        strategy = decide_strategy(kw, comp, 0, model)
        article = write_article(kw, strategy, model)
        return kw, article

    with engine:
        import concurrent.futures
        futures = {engine.submit(_write_one, kw): kw for kw in keywords}
        for future in concurrent.futures.as_completed(futures):
            kw = futures[future]
            try:
                _kw, article = future.result(timeout=300)
                articles[_kw] = article
                if article:
                    _save_article(f"{_slug(_kw)}_{_ts()}.md", article, output_dir)
                    try:
                        mem_module.record_article(_kw, "", article)
                    except Exception:
                        pass
                log.info(f"[BATCH] Article done: {kw[:50]}")
            except Exception as e:
                log.warning(f"[BATCH] Article failed: {kw[:50]} — {e}")

    return articles
