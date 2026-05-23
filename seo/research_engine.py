"""
SEO Agent Pro — Real SERP Intelligence Engine.

Replaces LLM-guessed competitor analysis with live web data.
Zero paid APIs. Pure DuckDuckGo + trafilatura + BeautifulSoup.

Architecture:
  1. search_web(keyword)        → DuckDuckGo top-10 results
  2. fetch_article(url)         → trafilatura + BS4 extraction
  3. extract_competitor_data()  → structural analysis
  4. build_serp_analysis()      → aggregate → structured output

Cache: cache/serp/<keyword_md5>.json
"""

import hashlib
import json
import logging
import os
import re
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

# ── Optional dependencies (graceful degradation) ────────────

_HAS_DUCKDUCKGO = False
_HAS_TRAFILATURA = False
try:
    from ddgs import DDGS
    _HAS_DUCKDUCKGO = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        _HAS_DUCKDUCKGO = True
    except ImportError:
        pass

try:
    import trafilatura
    _HAS_TRAFILATURA = True
except ImportError:
    pass

# ── Logging ─────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("research_engine")


# ── Config ──────────────────────────────────────────────────

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "serp"
CACHE_TTL_HOURS = 24  # fresh cache within this window
REQUEST_DELAY = 1.0   # polite crawl delay between fetches
MAX_RETRIES = 2
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# Domains to exclude from competitor analysis (low-quality SERP results)
EXCLUDED_DOMAINS = {
    "youtube.com", "music.youtube.com", "pinterest.com", "pinterest.ca",
    "reddit.com", "facebook.com", "twitter.com", "x.com", "instagram.com",
    "tiktok.com", "linkedin.com", "amazon.com", "amazon.co.uk",
    "ebay.com", "walmart.com", "bestbuy.com",
}

# ── Helpers ─────────────────────────────────────────────────


def _cache_key(keyword: str) -> str:
    return hashlib.md5(keyword.lower().strip().encode()).hexdigest()


def _cache_path(keyword: str) -> Path:
    return CACHE_DIR / f"{_cache_key(keyword)}.json"


def _cache_hit(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
        if datetime.now() - cached_at < timedelta(hours=CACHE_TTL_HOURS):
            log.info(f"  [CACHE HIT]  {path.stem}")
            return data
        else:
            log.info(f"  [CACHE STALE] {path.stem}")
            return None
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _cache_write(keyword: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data["_cached_at"] = datetime.now().isoformat()
    data["_keyword"] = keyword
    path = _cache_path(keyword)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"  [CACHE WRITE] {path.stem}")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40]


# ── 1. SERP Search ──────────────────────────────────────────


def search_web(keyword: str, max_results: int = 10) -> list[dict]:
    """Search DuckDuckGo, return top-N organic results.

    Each result: {title, url, snippet, position}
    Falls back to existing urllib approach if duckduckgo_search unavailable.
    """
    log.info(f"  [SEARCH]  \"{keyword}\" — top {max_results}")

    if not _HAS_DUCKDUCKGO:
        log.info("  [SEARCH]  duckduckgo_search not installed, using fallback")
        return _search_fallback(keyword, max_results)

    try:
        results = []
        with DDGS() as ddgs:
            for i, r in enumerate(ddgs.text(keyword, max_results=max_results)):
                if r.get("title") and r.get("href"):
                    results.append({
                        "title": r["title"],
                        "url": r["href"],
                        "snippet": r.get("body", ""),
                        "position": i + 1,
                    })
        log.info(f"  [SEARCH]  → {len(results)} results")
        return results
    except Exception as e:
        log.info(f"  [SEARCH]  duckduckgo_search failed: {e}")
        return _search_fallback(keyword, max_results)


def _search_fallback(keyword: str, max_results: int = 10) -> list[dict]:
    """Fallback: use urllib to scrape DuckDuckGo HTML."""
    import urllib.parse
    import urllib.request

    encoded = urllib.parse.quote(keyword)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    results = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        for i, a in enumerate(soup.select("a.result__a")):
            if len(results) >= max_results:
                break
            href = a.get("href", "")
            title = a.get_text(strip=True)
            snippet_tag = a.find_next("a", class_="result__snippet")
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
            if title and href:
                results.append({
                    "title": title,
                    "url": href,
                    "snippet": snippet,
                    "position": i + 1,
                })
        log.info(f"  [SEARCH]  fallback → {len(results)} results")
    except Exception as e:
        log.info(f"  [SEARCH]  fallback failed: {e}")
    return results


# ── 2. Article Fetch ────────────────────────────────────────


def fetch_article(url: str) -> Optional[dict]:
    """Download + extract structured article content.

    Uses trafilatura for main extraction, BS4 for structural signals.
    Returns dict with: title, h1, h2s, h3s, text, word_count,
    tables, bullet_lists, has_faq, internal_links, external_links
    """
    log.info(f"  [CRAWL]  {url[:80]}...")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                log.info(f"  [CRAWL]  empty response (attempt {attempt})")
                time.sleep(REQUEST_DELAY)
                continue

            text = trafilatura.extract(
                downloaded,
                include_formatting=True,
                include_links=True,
                include_images=False,
                output_format="txt",
            )
            article_text = text or ""

            # BS4 for structural analysis
            soup = BeautifulSoup(downloaded, "lxml")

            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""

            h1_tags = soup.find_all("h1")
            h1 = h1_tags[0].get_text(strip=True) if h1_tags else ""

            h2s = [h.get_text(strip=True) for h in soup.find_all("h2") if h.get_text(strip=True)]
            h3s = [h.get_text(strip=True) for h in soup.find_all("h3") if h.get_text(strip=True)]

            tables = soup.find_all("table")
            tables_count = len(tables)

            bullets = soup.find_all(["ul", "ol"])
            bullet_lists_count = len(bullets)

            has_faq = bool(
                re.search(r"(?i)\bfaq\b|frequently asked|questions and answers", article_text)
            )

            # Count links
            internal_links = 0
            external_links = 0
            domain = re.sub(r"https?://(www\.)?", "", url).split("/")[0] if url else ""
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if href.startswith("#") or href.startswith("javascript:"):
                    continue
                if domain and (domain in href or href.startswith("/")):
                    internal_links += 1
                elif href.startswith("http"):
                    external_links += 1

            word_count = len(article_text.split()) if article_text else 0

            log.info(f"  [CRAWL]  ✓ {word_count} words, {len(h2s)} H2s, {tables_count} tables")
            return {
                "title": title,
                "h1": h1,
                "h2s": h2s,
                "h3s": h3s,
                "text": article_text[:10000],  # cap for memory
                "word_count": word_count,
                "tables_count": tables_count,
                "bullet_lists_count": bullet_lists_count,
                "has_faq": has_faq,
                "internal_links": internal_links,
                "external_links": external_links,
            }

        except Exception as e:
            log.info(f"  [CRAWL]  error (attempt {attempt}): {e}")
            time.sleep(REQUEST_DELAY)

    log.info(f"  [CRAWL]  ✗ failed after {MAX_RETRIES} attempts")
    return None


# ── 3. Competitor Data Extraction ───────────────────────────


def extract_competitor_data(content: dict) -> dict:
    """Analyze extracted article structure for patterns.

    Returns: heading_patterns, recurring_entities, keyword_frequency,
    avg_paragraph_size, cta_patterns, faq_patterns, content_depth, formatting_style
    """
    log.info("  [EXTRACT]  analyzing structure")

    text = content.get("text", "")
    h2s = content.get("h2s", [])
    h3s = content.get("h3s", [])

    # Heading patterns
    heading_patterns = list(dict.fromkeys(h2s + h3s))[:15]

    # Recurring entities: capitalized phrases
    entities = []
    seen = set()
    for m in re.finditer(r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})", text):
        name = m.group(1).strip()
        lower = name.lower()
        if len(name) > 3 and lower not in seen:
            seen.add(lower)
            entities.append(name)
    recurring_entities = entities[:15]

    # Keyword frequency
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    word_freq = Counter(words).most_common(20)
    keyword_frequency = [{"word": w, "count": c} for w, c in word_freq]

    # Avg paragraph size
    paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 20]
    avg_paragraph_size = int(sum(len(p.split()) for p in paras) / max(1, len(paras)))

    # CTA patterns
    cta_signals = [
        "sign up", "get started", "try free", "download", "subscribe",
        "buy now", "start free trial", "claim", "join", "register",
    ]
    cta_patterns = [s for s in cta_signals if s in text.lower()]

    # FAQ patterns
    faq_patterns = []
    if content.get("has_faq"):
        faq_patterns.append("FAQ section present")
    if re.search(r"(?i)(what|how|why|when|where|which|does|can|is|are)\s+.*\?", text):
        faq_patterns.append("Q&A format detected")

    # Content depth
    content_depth = "shallow"
    if content.get("word_count", 0) > 2000:
        content_depth = "comprehensive"
    elif content.get("word_count", 0) > 1000:
        content_depth = "moderate"
    if content.get("tables_count", 0) > 0:
        content_depth += " + tables"
    if content.get("has_faq"):
        content_depth += " + FAQ"

    # Formatting style
    formatting_signals = []
    if content.get("bullet_lists_count", 0) > 3:
        formatting_signals.append("heavy bullet lists")
    if content.get("tables_count", 0) > 0:
        formatting_signals.append("tables")
    if content.get("has_faq"):
        formatting_signals.append("FAQ")
    formatting_style = ", ".join(formatting_signals) if formatting_signals else "standard prose"

    result = {
        "heading_patterns": heading_patterns,
        "recurring_entities": recurring_entities,
        "keyword_frequency": keyword_frequency[:10],
        "avg_paragraph_size": avg_paragraph_size,
        "cta_patterns": cta_patterns,
        "faq_patterns": faq_patterns,
        "content_depth": content_depth,
        "formatting_style": formatting_style,
    }

    log.info(f"  [EXTRACT]  ✓ {len(heading_patterns)} headings, {len(recurring_entities)} entities")
    return result


# ── 4. Aggregated SERP Analysis ─────────────────────────────


def build_serp_analysis(keyword: str) -> dict:
    """Aggregate all competitor data into a structured SERP analysis.

    This is the main entry point. Returns a dict matching the
    expected format from modules.analyze_competitors().
    """
    log.info(f"  [SERP]  Starting real competitor analysis for: \"{keyword}\"")

    # Check cache first
    cache_path = _cache_path(keyword)
    cached = _cache_hit(cache_path)
    if cached and "analysis" in cached:
        log.info("  [CACHE HIT]  Using cached SERP analysis")
        return cached["analysis"]

    log.info("  [CACHE MISS]  Performing live SERP analysis")

    # Step 1: Search
    results = search_web(keyword)
    if not results:
        log.info("  [SERP]  No search results — returning empty analysis")
        return _empty_analysis()

    # Step 1b: Filter out low-quality domains (YouTube, Pinterest, social, shopping)
    import urllib.parse as _urlparse
    _filtered = []
    for r in results:
        try:
            _domain = _urlparse.urlparse(r.get("url", "")).netloc.lower()
            if _domain.startswith("www."):
                _domain = _domain[4:]
            if _domain.startswith("m."):
                _domain = _domain[2:]
            if not any(excl in _domain for excl in EXCLUDED_DOMAINS):
                _filtered.append(r)
        except Exception:
            _filtered.append(r)
    if _filtered:
        results = _filtered
    log.info(f"  [SERP]  {len(results)} results after domain filtering")

    # Step 2: Fetch articles
    articles = []
    for r in results[:5]:  # top 5 for speed
        article = fetch_article(r["url"])
        if article:
            articles.append(article)
        time.sleep(REQUEST_DELAY)

    # Step 3: Extract competitor data from each
    all_competitor_data = []
    for a in articles:
        data = extract_competitor_data(a)
        if data:
            all_competitor_data.append(data)

    # Step 4: Aggregate
    analysis = _aggregate(keyword, results, articles, all_competitor_data)

    # Cache
    _cache_write(keyword, {"analysis": analysis})

    return analysis


def _aggregate(
    keyword: str,
    results: list,
    articles: list,
    comp_data: list,
) -> dict:
    """Merge all competitor signals into final analysis dict.

    Output shape matches modules.analyze_competitors() return type.
    """
    # ── Average word count ──
    word_counts = [a.get("word_count", 0) for a in articles if a]
    avg_wc = int(sum(word_counts) / max(1, len(word_counts))) if word_counts else 2000

    # ── Common headings ──
    all_h2s = []
    for a in articles:
        if a:
            all_h2s.extend(a.get("h2s", []))
    heading_counter = Counter(h.strip() for h in all_h2s if len(h.strip()) > 5)
    common_headings = [h for h, _ in heading_counter.most_common(10)]

    if not common_headings:
        common_headings = ["Introduction", "Benefits", "Features", "Comparison", "FAQ", "Conclusion"]

    # ── Recurring entities ──
    entity_counter = Counter()
    for cd in comp_data:
        for e in cd.get("recurring_entities", []):
            entity_counter[e] += 1
    top_entities = [e for e, _ in entity_counter.most_common(15)]

    # ── FAQ patterns ──
    faq_patterns = []
    for cd in comp_data:
        faq_patterns.extend(cd.get("faq_patterns", []))
    faq_patterns = list(dict.fromkeys(faq_patterns))[:5]

    # ── Detect gaps ──
    content_gaps = _detect_gaps(common_headings, keyword)

    # ── Dominant intent from SERP titles/snippets ──
    serp_titles = [r.get("title", "") for r in results]
    serp_snippets = [r.get("snippet", "") for r in results]
    dominant_intent = _detect_intent(keyword, serp_titles, serp_snippets)

    # ── Competitor titles ──
    competitor_titles = [r.get("title", "")[:80] for r in results[:5]]

    # ── Top URLs ──
    top_urls = [r.get("url", "") for r in results[:5]]

    # ── Formatting patterns ──
    formatting_patterns = list(
        dict.fromkeys(
            cd.get("formatting_style", "standard prose") for cd in comp_data
        )
    )[:5]

    # ── CTA patterns ──
    cta_patterns = list(
        dict.fromkeys(
            cta for cd in comp_data for cta in cd.get("cta_patterns", [])
        )
    )[:5]

    # ── Weaknesses (derived from common missing patterns) ──
    weaknesses = [
        "Generic content without specific data",
        "Missing practical examples",
        "Weak FAQ sections",
    ]
    if any("heavy bullet lists" in cd.get("formatting_style", "") for cd in comp_data):
        weaknesses.append("Over-reliance on listicles without depth")

    # ── Why they rank ──
    why_rank = "Topical relevance, comprehensive coverage, and backlink authority"

    # ── SEO patterns ──
    seo_patterns = ["Structured headings", "Keyword in title/H1"]
    if any(a and a.get("has_faq") for a in articles):
        seo_patterns.append("FAQ schema")
    if any(a and a.get("tables_count", 0) > 0 for a in articles):
        seo_patterns.append("Comparison tables")

    # ── Avg paragraph size ──
    para_sizes = [cd.get("avg_paragraph_size", 0) for cd in comp_data if cd.get("avg_paragraph_size", 0) > 0]
    avg_para = int(sum(para_sizes) / max(1, len(para_sizes))) if para_sizes else 40

    # ── Build final output ──
    analysis = {
        "average_word_count": avg_wc,
        "common_headings": common_headings,
        "entities": top_entities,
        "faq_patterns": faq_patterns,
        "content_gaps": content_gaps,
        "dominant_search_intent": dominant_intent,
        "competitor_titles": competitor_titles,
        "top_urls": top_urls,
        "formatting_patterns": formatting_patterns,
        "cta_patterns": cta_patterns,
        # Legacy keys for backward compatibility with modules.py
        "common_sections": common_headings,
        "missing_gaps": content_gaps,
        "content_length_avg": f"{avg_wc - 400}-{avg_wc + 400} words",
        "seo_patterns": seo_patterns,
        "weaknesses": weaknesses,
        "why_they_rank": why_rank,
        # Metadata
        "_serp_source": "live",
        "_competitors_analyzed": len(articles),
        "_avg_paragraph_size": avg_para,
    }

    log.info(f"  [SERP]  ✓ Analysis complete — {len(articles)} competitors, {avg_wc} avg words")
    return analysis


def _detect_gaps(common_headings: list, keyword: str) -> list:
    """Identify topics competitors are NOT covering."""
    gaps = []
    all_text = " ".join(common_headings).lower()

    gap_signals = [
        ("real-world case studies", "case stud", "real-world", "real world"),
        ("budget-friendly options", "budget", "affordable", "cheap", "free"),
        ("step-by-step tutorials", "step-by-step", "step by step", "tutorial"),
        ("beginner-friendly guide", "beginner", "getting started"),
        ("common mistakes to avoid", "mistake", "pitfall", "common error"),
        ("detailed comparison with alternatives", "vs ", " versus ", "comparison", "alternative"),
        ("pricing breakdown", "price", "pricing", "cost"),
        ("pros and cons", "pros", "cons", "advantage", "disadvantage"),
        ("expert tips and best practices", "expert tip", "best practice", "pro tip"),
        ("FAQs", "faq", "frequently asked", "question"),
    ]
    for gap_label, *signals in gap_signals:
        if not any(s in all_text for s in signals):
            gaps.append(gap_label)

    return gaps[:6]


def _detect_intent(keyword: str, titles: list, snippets: list) -> str:
    """Detect dominant search intent from SERP signals."""
    kw_l = keyword.lower()
    text = " ".join(titles + snippets).lower()

    # Commercial signals
    if any(w in kw_l for w in ["best", "top", "review", "alternative", "vs ", "versus", "compare"]):
        return "commercial"
    # Transactional signals
    if any(w in kw_l for w in ["buy", "price", "deal", "discount", "coupon", "order"]):
        return "transactional"
    # News signals
    if any(w in kw_l for w in ["news", "today", "breaking", "update", "announced"]):
        return "news"
    # Educational signals
    if any(w in kw_l for w in ["guide", "tutorial", "how to", "learn", "beginner", "step by step"]):
        return "educational"
    # Informational signals
    if any(w in kw_l for w in ["what is", "what are", "why", "meaning", "definition", "explain"]):
        return "informational"
    # Trend signals
    if any(w in kw_l for w in ["future", "trend", "prediction", "forecast", "emerging"]):
        return "trend_analysis"

    # SERP-level signals
    if any(w in text for w in ["price", "buy", "deal", "discount"]):
        return "transactional"
    if any(w in text for w in ["vs", "versus", "comparison", "best", "review"]):
        return "commercial"

    return "commercial"


def _empty_analysis() -> dict:
    """Return safe fallback when real SERP analysis fails."""
    return {
        "average_word_count": 2000,
        "common_headings": ["Introduction", "Key Features", "Benefits", "Comparison", "FAQ", "Conclusion"],
        "entities": [],
        "faq_patterns": [],
        "content_gaps": ["Real-world case studies", "Budget-friendly options", "Step-by-step tutorials"],
        "dominant_search_intent": "commercial",
        "competitor_titles": [],
        "top_urls": [],
        "formatting_patterns": ["standard prose"],
        "cta_patterns": [],
        "common_sections": ["Introduction", "Key Features", "Benefits", "Comparison", "FAQ", "Conclusion"],
        "missing_gaps": ["Real-world case studies", "Budget-friendly options", "Step-by-step tutorials"],
        "content_length_avg": "1800-2200 words",
        "seo_patterns": ["Structured guides", "Bullet-point lists", "Expert quotes"],
        "weaknesses": ["Generic content without specific data", "Missing practical examples"],
        "why_they_rank": "Topical relevance and backlink authority",
        "_serp_source": "empty_fallback",
        "_competitors_analyzed": 0,
    }
