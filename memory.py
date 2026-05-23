"""
Memory System — Persistent learning across runs (v2)
======================================================
Enhancements:
  • Active pattern learning: extracts winning patterns from high performers
  • Feedback loop injection: successful angles/fonts propagate into future prompts
  • Performance-weighted recall: recent + high-performing articles influence more
  • Keyword style memory: remembers what worked per keyword/niche
  • Failure tracking: avoids repeating failed strategies

Usage:
    import memory as mem_module
    mem = mem_module.load()
    mem_module.record_article(mem, keyword, article, model, quality_score=85)
    patterns = mem_module.get_winning_patterns(mem, niche="tech", top_n=5)
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import threading
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from config import SETTINGS
from llm_router import c

log = logging.getLogger("memory")

# ── Vector retrieval source tracking ─────────────────────────
VECTOR_SOURCE_VECTOR = "vector"
VECTOR_SOURCE_FALLBACK_JSON = "fallback_json"
VECTOR_SOURCE_DISABLED = "disabled"
VECTOR_SOURCE_UNKNOWN = "unknown"

_last_vector_source: str = VECTOR_SOURCE_UNKNOWN
_last_injection_composition: dict | None = None
_last_injection_size_warn: bool = False

_INJECTION_TRUNCATION_LIMIT_CHARS = 4000


def get_vector_retrieval_source() -> str:
    """Return the vector retrieval source used by last injection call.

    Returns one of: "vector", "fallback_json", "disabled", "unknown".
    """
    global _last_vector_source
    return _last_vector_source


def get_injection_composition() -> dict:
    """Return detailed composition of the last-built prompt injection."""
    global _last_injection_composition
    return dict(_last_injection_composition) if _last_injection_composition else {}


def get_injection_size_warning() -> bool:
    """Return whether the last injection exceeded truncation limit."""
    global _last_injection_size_warn
    return _last_injection_size_warn

MEMORY_PATH = Path(SETTINGS["memory_file"])
BACKUP_DIR = MEMORY_PATH.parent / "memory_backups"
_LOCK_PATH = MEMORY_PATH.with_suffix(".lock")


class MemoryLock:
    """Cross-process file lock using O_EXCL lock file + threading.RLock.

    Protects against concurrent writes from parallel threads (within a process)
    and from Celery workers (across processes). Lock file includes PID for
    stale-detection via mtime TTL.
    """
    def __init__(self, lock_path: Path, stale_ttl: float = 30.0):
        self.lock_path = lock_path
        self.stale_ttl = stale_ttl
        self._rlock = threading.RLock()
        self._owned = False
        self._depth = 0

    def acquire(self, timeout: float = 10.0) -> None:
        self._rlock.acquire()
        self._depth += 1
        if self._depth > 1:
            return
        try:
            self._acquire_file(timeout)
        except Exception:
            self._depth -= 1
            self._rlock.release()
            raise

    def _acquire_file(self, timeout: float) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, 'w') as f:
                    f.write(f"{os.getpid()}\n")
                self._owned = True
                return
            except FileExistsError:
                self._try_break_stale()
                time.sleep(0.05)
        raise TimeoutError(f"Cannot acquire lock: {self.lock_path}")

    def _try_break_stale(self) -> None:
        try:
            if time.time() - self.lock_path.stat().st_mtime > self.stale_ttl:
                self.lock_path.unlink(missing_ok=True)
        except OSError as _e:
            log.warning("[MEMORY-LOCK] Stale lock cleanup failed: %s", _e)

    def release(self) -> None:
        self._depth -= 1
        if self._depth == 0 and self._owned:
            try:
                self.lock_path.unlink(missing_ok=True)
            except OSError as _e:
                log.warning("[MEMORY-LOCK] Lock unlink failed: %s", _e)
            self._owned = False
        self._rlock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


_MEMORY_LOCK = MemoryLock(_LOCK_PATH)


def _atomic_write(data: dict, path: Path) -> None:
    """Write JSON to a temp file then atomically rename to target path."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _backup(path: Path) -> None:
    """Copy the current memory file to a timestamped backup if it exists."""
    if not path.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(path, BACKUP_DIR / f"memory_{stamp}.json")


def load() -> dict:
    if MEMORY_PATH.exists():
        try:
            return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            backups = sorted(BACKUP_DIR.glob("memory_*.json")) if BACKUP_DIR.exists() else []
            if backups:
                latest = backups[-1]
                print(c("yellow", f"  ⚠ Memory file corrupted — restoring from {latest.name}"))
                try:
                    return json.loads(latest.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError) as _e:
                    log.warning("[MEMORY] Backup restore failed: %s — returning fresh memory", _e)
            else:
                log.warning("[MEMORY] Memory file corrupted and no backups found — returning fresh memory")

    return {
        "articles_written":      [],
        "clusters":              {},
        "authority_scores":      {},
        "successful_patterns":   [],
        "failed_patterns":       [],  # NEW
        "keyword_styles":        {},  # NEW: per-keyword learned preferences
        "niche_profiles":        {},  # NEW: per-niche aggregate stats
        "keywords_done":         [],
        "total_runs":            0,
        "created_at":            datetime.now().isoformat(),
    }


def save(mem: dict) -> None:
    with _MEMORY_LOCK:
        mem["updated_at"] = datetime.now().isoformat()
        _backup(MEMORY_PATH)
        _atomic_write(mem, MEMORY_PATH)


@contextmanager
def transaction():
    """Load-mutate-save transaction with full locking.

    Acquires the lock, loads current state, yields for modification,
    then persists automatically. Eliminates load→modify→save race.

    Usage:
        with memory.transaction() as mem:
            mem["total_runs"] += 1
    """
    with _MEMORY_LOCK:
        mem = load()
        yield mem
        mem["updated_at"] = datetime.now().isoformat()
        _backup(MEMORY_PATH)
        _atomic_write(mem, MEMORY_PATH)


def record_article(mem: dict | None = None, keyword: str = "", article: str = "",
                   model: str = "local", quality_score: int = 0) -> dict | None:
    """Record article with quality score for pattern learning.

    Args:
        mem: Memory dict. If None, uses transaction() for safe load-modify-save.
        keyword: Target keyword.
        article: Article text.
        model: Model name.
        quality_score: Quality score 0-100.

    Returns:
        Updated memory dict when mem is None (inside transaction), else None.
    """
    if mem is None:
        with transaction() as mem:
            mem["total_runs"] += 1
            if keyword not in mem["keywords_done"]:
                mem["keywords_done"].append(keyword)

            entry = {
                "keyword":    keyword,
                "model":      model,
                "word_count": len(article.split()),
                "date":       datetime.now().isoformat(),
                "quality_score": quality_score,
            }
            mem["articles_written"].append(entry)

            if quality_score >= 75:
                _extract_success_pattern(mem, keyword, article, quality_score)
            elif quality_score < 50:
                _extract_failure_pattern(mem, keyword, article, quality_score)

            _update_keyword_style(mem, keyword, article, quality_score)
            print(c("green", f"  ✓ Memory updated — total articles: {len(mem['articles_written'])}, "
                             f"quality={quality_score}"))
            return mem

    mem["total_runs"] += 1
    if keyword not in mem["keywords_done"]:
        mem["keywords_done"].append(keyword)

    entry = {
        "keyword":    keyword,
        "model":      model,
        "word_count": len(article.split()),
        "date":       datetime.now().isoformat(),
        "quality_score": quality_score,
    }
    mem["articles_written"].append(entry)

    if quality_score >= 75:
        _extract_success_pattern(mem, keyword, article, quality_score)
    elif quality_score < 50:
        _extract_failure_pattern(mem, keyword, article, quality_score)

    _update_keyword_style(mem, keyword, article, quality_score)

    save(mem)
    print(c("green", f"  ✓ Memory updated — total articles: {len(mem['articles_written'])}, "
                     f"quality={quality_score}"))
    return None


def record_cluster(mem: dict | None = None, keyword: str = "", cluster: dict | None = None) -> None:
    if mem is None:
        with transaction() as mem:
            mem["clusters"][keyword] = cluster
        return
    mem["clusters"][keyword] = cluster
    save(mem)


def record_authority(mem: dict | None = None, niche: str = "", score: dict | None = None) -> None:
    if mem is None:
        with transaction() as mem:
            mem["authority_scores"][niche] = {
                "score": score.get("authority_score", 0),
                "date":  datetime.now().isoformat(),
                "data":  score,
            }
            profile = mem.setdefault("niche_profiles", {}).setdefault(niche, {
                "articles_count": 0, "avg_word_count": 0, "avg_quality": 0, "avg_depth": 0,
            })
            profile["articles_count"] = profile.get("articles_count", 0) + 1
        return

    mem["authority_scores"][niche] = {
        "score": score.get("authority_score", 0),
        "date":  datetime.now().isoformat(),
        "data":  score,
    }
    profile = mem.setdefault("niche_profiles", {}).setdefault(niche, {
        "articles_count": 0,
        "avg_word_count": 0,
        "avg_quality": 0,
        "avg_depth": 0,
    })
    profile["articles_count"] = profile.get("articles_count", 0) + 1
    save(mem)


def record_performance(mem: dict | None = None, keyword: str = "", metrics: dict | None = None) -> None:
    """Store post-publish metrics for an article (ranking, CTR, impressions, etc.)."""
    if metrics is None:
        metrics = {}

    if mem is None:
        with transaction() as mem:
            _do_record_performance(mem, keyword, metrics)
        return

    _do_record_performance(mem, keyword, metrics)
    save(mem)


def _do_record_performance(mem: dict, keyword: str, metrics: dict) -> None:
    for article in mem.get("articles_written", []):
        if article["keyword"] == keyword:
            article.setdefault("performance_history", []).append({
                "date": datetime.now().isoformat(),
                "position": metrics.get("position", None),
                "ctr": metrics.get("ctr", None),
                "impressions": metrics.get("impressions", 0),
                "clicks": metrics.get("clicks", 0),
                "dwell_time": metrics.get("dwell_time", None),
                "revision": len(article.get("performance_history", [])) + 1,
            })
            print(c("green", f"  ✓ Performance recorded for \"{keyword}\" — pos {metrics.get('position', '?')}"))
            return
    mem["articles_written"].append({
        "keyword": keyword,
        "model": "local",
        "word_count": 0,
        "date": datetime.now().isoformat(),
        "performance_history": [{
            "date": datetime.now().isoformat(),
            "position": metrics.get("position", None),
            "ctr": metrics.get("ctr", None),
            "impressions": metrics.get("impressions", 0),
            "clicks": metrics.get("clicks", 0),
            "dwell_time": metrics.get("dwell_time", None),
            "revision": 1,
        }],
    })


def get_underperformers(mem: dict, threshold: int = 50) -> list[dict]:
    """Return articles scoring below threshold (need rewrite)."""
    under = []
    for article in mem.get("articles_written", []):
        perf = article.get("performance_history", [])
        if not perf:
            continue
        latest = perf[-1]
        pos = latest.get("position")
        if pos is None:
            continue
        score = 0
        if pos <= 3:
            score = 80
        elif pos <= 10:
            score = 60
        elif pos <= 20:
            score = 30
        else:
            score = 10
        ctr = latest.get("ctr", 100)
        if ctr is not None and ctr < 2:
            score -= 15
        imp = latest.get("impressions", 0)
        clicks = latest.get("clicks", 0)
        if imp > 1000 and clicks < 10:
            score -= 10

        if score < threshold:
            under.append({
                "keyword": article["keyword"],
                "current_score": score,
                "latest_metrics": latest,
                "revisions": len(perf),
            })
    return sorted(under, key=lambda x: x["current_score"])


def get_winning_patterns(mem: dict, niche: str = "", top_n: int = 5) -> list[dict]:
    """Extract successful patterns from high-performing articles.

    Returns list of dicts with 'type', 'value', 'success_count', 'avg_position'.
    """
    patterns = mem.get("successful_patterns", [])
    if niche:
        # Filter by niche (simple keyword matching)
        niche_keywords = set()
        for kw, cluster in mem.get("clusters", {}).items():
            if niche.lower() in str(cluster).lower():
                niche_keywords.add(kw)
        patterns = [p for p in patterns if p.get("keyword") in niche_keywords]
    # Sort by success count then recency
    patterns.sort(key=lambda p: (p.get("success_count", 0), p.get("last_used", "")), reverse=True)
    return patterns[:top_n]


def get_keyword_style(mem: dict, keyword: str) -> dict:
    """Return learned style preferences for a keyword."""
    return mem.get("keyword_styles", {}).get(keyword.lower(), {})


def get_niche_profile(mem: dict, niche: str) -> dict:
    """Return aggregate profile for a niche."""
    return mem.get("niche_profiles", {}).get(niche, {})


_last_prompt_composition: dict | None = None


def get_prompt_injection_composition() -> dict:
    """Return metadata about the last prompt injection block."""
    global _last_prompt_composition
    return dict(_last_prompt_composition) if _last_prompt_composition else {}


def build_prompt_injection(mem: dict, keyword: str, niche: str = "") -> str:
    """Build a prompt injection block based on learned successful patterns.

    This is the ACTIVE FEEDBACK LOOP — memory influences future writing.
    """
    global _last_prompt_composition

    injections = []
    style = get_keyword_style(mem, keyword)
    if style.get("best_opener"):
        injections.append(f"OPENER THAT WORKED: '{style['best_opener']}' — use a similar angle.")
    if style.get("avg_word_count", 0) > 1500:
        injections.append(f"DEPTH TARGET: {int(style['avg_word_count'] * 1.1)}+ words (your past articles for this topic averaged {style['avg_word_count']:.0f}w).")
    if style.get("high_performing_sections"):
        sections = ", ".join(style["high_performing_sections"][:3])
        injections.append(f"HIGH-PERFORMING SECTIONS FOR THIS TOPIC: {sections}.")

    # Niche-level patterns
    profile = get_niche_profile(mem, niche) if niche else {}
    if profile.get("avg_word_count", 0) > 0:
        injections.append(f"NICHE BENCHMARK: {niche} articles typically need {profile['avg_word_count']:.0f} words.")

    # Winning patterns from other articles
    winners = get_winning_patterns(mem, niche=niche, top_n=3)
    if winners:
        injections.append("PATTERNS THAT RANKED WELL:")
        for w in winners:
            injections.append(f"  - {w.get('type', 'pattern')}: {w.get('value', '')} (successes: {w.get('success_count', 0)})")

    # Failure avoidance
    failures = mem.get("failed_patterns", [])[-3:]
    if failures:
        injections.append("AVOID THESE PATTERNS (underperformed previously):")
        for f in failures:
            injections.append(f"  - {f.get('type', 'pattern')}: {f.get('value', '')}")

    _last_prompt_composition = {
        "injection_count": len(injections),
        "total_chars": sum(len(i) for i in injections),
        "has_opener": style.get("best_opener") is not None,
        "has_depth_target": style.get("avg_word_count", 0) > 1500,
        "has_sections": bool(style.get("high_performing_sections")),
        "has_winners": len(winners) > 0,
        "has_failures": len(failures) > 0,
    }

    if not injections:
        return ""
    return "\n═══════════════════════════════════════════════════════════════\n" \
           "LEARNED INSIGHTS FROM PREVIOUS ARTICLES — APPLY THESE:\n" \
           + "\n".join(injections) \
           + "\n═══════════════════════════════════════════════════════════════\n"


# ── Internal pattern extraction ──────────────────────────────

def _extract_success_pattern(mem: dict, keyword: str, article: str, quality_score: int) -> None:
    """Extract and store patterns from high-quality articles."""
    patterns = mem.setdefault("successful_patterns", [])
    # Extract opener style
    first_p = article[:300].lower()
    if first_p.startswith("most"):
        _add_pattern(patterns, "opener", "surprising_claim", keyword)
    elif first_p.startswith("the best"):
        _add_pattern(patterns, "opener", "direct_answer", keyword)
    elif re.search(r'\d+%', first_p):
        _add_pattern(patterns, "opener", "stat_open", keyword)

    # Detect structure patterns
    if re.search(r'<h2>.*?(?:comparison|vs\.?|versus)', article, re.I):
        _add_pattern(patterns, "structure", "comparison_section", keyword)
    if re.search(r'<h2>.*?hidden cost', article, re.I):
        _add_pattern(patterns, "structure", "hidden_costs_section", keyword)
    if re.search(r'<h2>.*?who should (not )?use', article, re.I):
        _add_pattern(patterns, "structure", "audience_qualification", keyword)
    if '<table' in article:
        _add_pattern(patterns, "structure", "comparison_table", keyword)


def _extract_failure_pattern(mem: dict, keyword: str, article: str, quality_score: int) -> None:
    """Extract and store patterns from low-quality articles to avoid."""
    patterns = mem.setdefault("failed_patterns", [])
    text_lower = article.lower()
    if "after two weeks of testing" in text_lower or "after four weeks of testing" in text_lower:
        patterns.append({"type": "opener", "value": "after_X_weeks_testing", "keyword": keyword, "score": quality_score})
    if "in today's world" in text_lower:
        patterns.append({"type": "opener", "value": "in_todays_world", "keyword": keyword, "score": quality_score})
    if text_lower.count(" check official site") > 2:
        patterns.append({"type": "content", "value": "vague_pricing", "keyword": keyword, "score": quality_score})
    # Keep only last 20 failures
    mem["failed_patterns"] = patterns[-20:]


def _add_pattern(patterns: list, ptype: str, value: str, keyword: str) -> None:
    for p in patterns:
        if p.get("type") == ptype and p.get("value") == value:
            p["success_count"] = p.get("success_count", 0) + 1
            p["last_used"] = datetime.now().isoformat()
            p["keywords"] = list(set(p.get("keywords", []) + [keyword]))
            return
    patterns.append({
        "type": ptype,
        "value": value,
        "success_count": 1,
        "last_used": datetime.now().isoformat(),
        "keywords": [keyword],
    })


def _update_keyword_style(mem: dict, keyword: str, article: str, quality_score: int) -> None:
    """Update per-keyword style memory with article attributes."""
    styles = mem.setdefault("keyword_styles", {})
    kw_lower = keyword.lower()
    if kw_lower not in styles:
        styles[kw_lower] = {"article_count": 0, "avg_quality": 0, "avg_word_count": 0, "high_performing_sections": []}

    st = styles[kw_lower]
    count = st["article_count"] + 1
    st["avg_quality"] = (st["avg_quality"] * st["article_count"] + quality_score) / count
    st["avg_word_count"] = (st["avg_word_count"] * st["article_count"] + len(article.split())) / count
    st["article_count"] = count

    # Remember best opener
    first_sentence = article.split(".")[0][:120]
    if quality_score >= 80 and len(first_sentence) > 20:
        st["best_opener"] = first_sentence

    # Remember high-performing sections
    sections = re.findall(r'<h2[^>]*>(.*?)</h2>', article, re.I | re.S)
    if quality_score >= 75 and sections:
        current = set(st.get("high_performing_sections", []))
        current.update([re.sub(r'<[^>]+>', '', s).strip() for s in sections[:3]])
        st["high_performing_sections"] = list(current)[:10]


# ── Strategy Evolution Injection ───────────────────────────

_last_strategy_composition: dict | None = None


def get_strategy_injection_composition() -> dict:
    """Return metadata about the last strategy evolution injection."""
    global _last_strategy_composition
    return dict(_last_strategy_composition) if _last_strategy_composition else {}


def build_strategy_evolution_injection() -> str:
    """Inject best-performing strategy patterns from StrategyEvolution persistence.

    Reads evolution/patterns.json (written by StrategyEvolution.record_outcome())
    and formats the highest-reward openers, structures, CTAs, and headings
    as prompt injection text for the article writer.
    """
    global _last_strategy_composition

    evolution_dir = Path(__file__).resolve().parent / "evolution"
    patterns_file = evolution_dir / "patterns.json"
    if not patterns_file.exists():
        _last_strategy_composition = {"pattern_count": 0, "type_count": 0, "source_file": ""}
        return ""

    try:
        data = json.loads(patterns_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _last_strategy_composition = {"pattern_count": 0, "type_count": 0, "source_file": str(patterns_file),
                                       "error": "corrupt"}
        return ""

    if not data:
        _last_strategy_composition = {"pattern_count": 0, "type_count": 0, "source_file": str(patterns_file),
                                       "error": "empty"}
        return ""

    # Group by pattern_type and sort by avg_reward descending
    by_type: dict[str, list[dict]] = {}
    for p in data:
        by_type.setdefault(p.get("pattern_type", "unknown"), []).append(p)

    lines = []
    type_counts: dict[str, int] = {}
    for ptype, items in by_type.items():
        sorted_items = sorted(items, key=lambda x: x.get("avg_reward", 0), reverse=True)
        top = sorted_items[:3]
        if ptype == "quality_strategy":
            readable_type = "QUALITY BENCHMARKS"
        else:
            readable_type = ptype.replace("_", " ").title()
        vals = []
        for t in top:
            val = t.get("value", "")
            reward = t.get("avg_reward", 0)
            occurrences = t.get("occurrences", 0)
            if val:
                vals.append(f"    - {val} (reward: {reward:+.2f}, used {occurrences}x)")
        if vals:
            lines.append(f"  BEST-PERFORMING {readable_type}:")
            lines.extend(vals)
            type_counts[ptype] = len(vals)

    _last_strategy_composition = {
        "pattern_count": len(data),
        "type_count": len(by_type),
        "source_file": str(patterns_file),
        "types_injected": {k: v for k, v in type_counts.items()},
        "total_chars": sum(len(l) for l in lines),
    }

    if not lines:
        return ""

    return (
        "\n═══════════════════════════════════════════════════════════════\n"
        "STRATEGY EVOLUTION INSIGHTS — PATTERNS WITH HIGHEST REWARD:\n"
        + "\n".join(lines)
        + "\n═══════════════════════════════════════════════════════════════\n"
    )


# ── Vector Memory Injection ──────────────────────────────

def _search_vector_memory(keyword: str, top_k: int = 3) -> tuple[list | None, str]:
    """Search using MemoryAdapter with VectorMemory backend.

    Returns (results_or_None, source_label) where source_label is one of
    VECTOR_SOURCE_VECTOR, VECTOR_SOURCE_FALLBACK_JSON, VECTOR_SOURCE_DISABLED.
    """
    try:
        from agent_core.memory_adapter import MemoryAdapter, HybridMemoryBackend, VectorMemoryBackend
        adapter = MemoryAdapter()
        results = adapter.search(keyword, top_k=top_k, min_quality=75)
        if results:
            # Verify the backend used is actually vector-based, not JSON fallback
            backend = adapter.backend
            if isinstance(backend, HybridMemoryBackend):
                vec_count = backend.vector.count()
            elif isinstance(backend, VectorMemoryBackend):
                vec_count = backend.count()
            else:
                vec_count = 0
            if vec_count > 0:
                return results, VECTOR_SOURCE_VECTOR
            else:
                log.info("[MEMORY] VectorMemory backend empty — falling back to JSON")
    except Exception:
        log.debug("[MEMORY] VectorMemory search unavailable", exc_info=True)
    return None, VECTOR_SOURCE_DISABLED


def _build_injection_lines(similar: list, is_vector: bool) -> tuple[list[str], dict]:
    """Format similar articles into injection lines + composition metadata.

    Returns (lines, composition_dict).
    """
    lines = []
    kw_count = 0
    opener_count = 0
    total_chars = 0
    used_kws = []

    for s in similar:
        if isinstance(s, dict):
            kw = s.get("keyword", "")
            score = s.get("quality_score", 0)
            wc = s.get("word_count", 0)
            if score >= 75:
                lines.append(f"  · \"{kw[:50]}\" — quality {score}/100, {wc} words")
                kw_count += 1
                used_kws.append(kw[:50])
                opener = _get_best_opener_from_entry(s)
                if opener:
                    lines.append(f"    Opener that worked: \"{opener[:80]}\"")
                    opener_count += 1
        else:
            if s.quality_score >= 75:
                wc = len(s.text.split()) if s.text else 0
                lines.append(f"  · \"{s.keyword[:50]}\" — quality {s.quality_score}/100, {wc} words")
                kw_count += 1
                used_kws.append(s.keyword[:50])
                if s.text:
                    first_sentence = s.text.split(".")[0][:120]
                    if first_sentence:
                        lines.append(f"    Opener that worked: \"{first_sentence[:80]}\"")
                        opener_count += 1

    total_chars = sum(len(l) for l in lines) if lines else 0
    composition = {
        "article_count": kw_count,
        "opener_count": opener_count,
        "total_chars": total_chars,
        "keywords": used_kws[:5],
        "is_vector": is_vector,
    }
    return lines, composition


def build_vector_memory_injection(keyword: str, mem: dict | None = None, top_k: int = 3) -> str:
    """Inject patterns from semantically similar past articles.

    Uses MemoryAdapter (with VectorMemory/ChromaDB) for semantic search,
    falling back to JSON keyword-overlap when vector store is unavailable.

    Tracks retrieval source via get_vector_retrieval_source() and
    composition details via get_injection_composition().
    """
    global _last_vector_source, _last_injection_composition, _last_injection_size_warn

    if mem is None:
        mem = load()

    # Phase 1: Try vector semantic search via MemoryAdapter
    vector_results, vec_source = _search_vector_memory(keyword, top_k=top_k)

    # Phase 2: Fall back to JSON keyword-overlap
    if vector_results is not None:
        similar = vector_results
        is_vector = True
        _last_vector_source = VECTOR_SOURCE_VECTOR
    else:
        similar = _find_similar_from_memory(mem, keyword, top_k=top_k)
        is_vector = False
        if similar:
            _last_vector_source = VECTOR_SOURCE_FALLBACK_JSON
        else:
            _last_vector_source = VECTOR_SOURCE_DISABLED

    if not similar:
        _last_injection_composition = {"article_count": 0, "opener_count": 0,
                                        "total_chars": 0, "keywords": [], "is_vector": is_vector}
        _last_injection_size_warn = False
        return ""

    lines, composition = _build_injection_lines(similar, is_vector)
    _last_injection_composition = composition

    if not lines:
        _last_injection_size_warn = False
        return ""

    body = "\n".join(lines)

    # Truncation check
    if len(body) > _INJECTION_TRUNCATION_LIMIT_CHARS:
        log.warning("[MEMORY] Vector memory injection truncated at %d chars (was %d)",
                     _INJECTION_TRUNCATION_LIMIT_CHARS, len(body))
        body = body[:_INJECTION_TRUNCATION_LIMIT_CHARS]
        _last_injection_size_warn = True
    else:
        _last_injection_size_warn = False

    return (
        "\n═══════════════════════════════════════════════════════════════\n"
        "SIMILAR HIGH-PERFORMING ARTICLES — REFERENCE THEIR PATTERNS:\n"
        + body
        + "\n═══════════════════════════════════════════════════════════════\n"
    )


def _find_similar_from_memory(mem: dict, keyword: str, top_k: int = 3) -> list[dict]:
    """Find articles in JSON memory that are similar to the given keyword.

    Uses simple keyword overlap scoring (no vector dependency).
    For full semantic search, MemoryAdapter with VectorMemoryBackend is needed.
    """
    kw_lower = keyword.lower()
    kw_words = set(kw_lower.split())
    scored = []

    for article in mem.get("articles_written", []):
        art_kw = article.get("keyword", "").lower()
        if art_kw == kw_lower:
            continue  # skip exact match (self)

        # Score: word overlap + quality bonus
        art_words = set(art_kw.split())
        if not kw_words or not art_words:
            continue
        overlap = len(kw_words & art_words)
        total = len(kw_words | art_words)
        similarity = overlap / total if total > 0 else 0

        quality_score = article.get("quality_score", 0)
        if similarity > 0 or quality_score >= 75:
            score = similarity * 0.6 + (quality_score / 100.0) * 0.4
            scored.append((score, article))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in scored[:top_k]]


def _get_best_opener_from_entry(entry: dict) -> str:
    """Extract the best opener text from an article entry."""
    perf = entry.get("performance_history", [])
    if perf and perf[-1].get("position") and perf[-1]["position"] <= 10:
        # High-ranking articles: try to extract from any stored text
        text = entry.get("text", entry.get("article", ""))
        if text:
            return text.split(".")[0][:120]
    return entry.get("best_opener", "")


def print_stats(mem: dict) -> None:
    articles = mem.get("articles_written", [])
    clusters = mem.get("clusters", {})
    under = get_underperformers(mem)

    tracked = sum(1 for a in articles if a.get("performance_history"))
    avg_pos = None
    positions = [p.get("position") for a in articles for p in a.get("performance_history", []) if p.get("position")]
    if positions:
        avg_pos = sum(positions) / len(positions)

    avg_quality = None
    qs = [a.get("quality_score", 0) for a in articles if a.get("quality_score", 0) > 0]
    if qs:
        avg_quality = sum(qs) / len(qs)

    print(f"""
  {c('bold', 'Memory Stats')}
  ─────────────────────────────
  Total runs:           {mem.get('total_runs', 0)}
  Articles:             {len(articles)}
  Tracked (rankings):   {tracked}
  Avg position:         {f'{avg_pos:.1f}' if avg_pos else '?'}
  Avg quality:          {f'{avg_quality:.1f}' if avg_quality else '?'}
  Need rewrite:         {len(under)}
  Clusters mapped:      {len(clusters)}
  Niches tracked:       {len(mem.get('authority_scores', {}))}
  Patterns learned:     {len(mem.get('successful_patterns', []))}
  Patterns avoided:     {len(mem.get('failed_patterns', []))}
""")

    if articles:
        print(c("dim", "  Recent articles:"))
        for a in articles[-5:]:
            perf = a.get("performance_history", [])
            pos = perf[-1].get("position", "?") if perf else "?"
            q = a.get("quality_score", "?")
            print(c("dim", f"    · {a['keyword'][:40]:<40}  {a['word_count']:5d}w  pos {str(pos):>3}  q={q}  [{a['model']}]"))
    if under:
        print(c("red", f"  ⚠ {len(under)} article(s) need optimization:"))
        for u in under[:3]:
            print(c("red", f"      {u['keyword'][:40]:<40}  score {u['current_score']}/100"))
