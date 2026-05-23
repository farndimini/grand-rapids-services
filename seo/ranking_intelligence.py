"""
SERP Ranking Intelligence Layer — predicts ranking probability without paid APIs.

Every function estimates "would Google choose this article for Top 10?"
using proxy signals: content depth, structure quality, brand signals,
intent match, SERP gap exploitation.

No external API calls. Pure algorithmic estimation from SERP features.
"""
from __future__ import annotations

import logging
import re
import time
from urllib.parse import urlparse

from seo.research_engine import search_web, fetch_article

log = logging.getLogger("ranking")

REQUEST_DELAY = 0.5


# ── 1. SERP Feature Reconstruction ───────────────────────────

def build_serp_features(results: list[dict]) -> list[dict]:
    """Extract rich features from each SERP result for authority estimation.

    Each result dict gets enriched with:
      - word_count, h2_count, h3_count, has_faq (from fetched article)
      - domain_type (blog/company/forum/media)
      - content_type (guide/list/review/landing/news)
      - freshness_signal (date found in snippet or title)
    """
    features = []
    for r in results:
        pos = r.get("position", 0)
        url = r.get("url", "")
        title = r.get("title", "")
        snippet = r.get("snippet", "")

        # Domain classification
        domain = urlparse(url).netloc.lower() if url else ""
        domain_type = _classify_domain(domain, title, snippet)

        # Content type from title/snippet patterns
        content_type = _classify_content_type(title, snippet)

        # Freshness signal — year or date in snippet/title
        freshness = _detect_freshness(title, snippet)

        # Try to fetch article for deeper features
        article = fetch_article(url) if url else None
        if article:
            time.sleep(REQUEST_DELAY)

        features.append({
            "position": pos,
            "url": url,
            "domain": domain,
            "domain_type": domain_type,
            "title": title,
            "snippet": snippet,
            "content_type": content_type,
            "freshness": freshness,
            "word_count": article.get("word_count", 0) if article else 0,
            "h2_count": len(article.get("h2s", [])) if article else 0,
            "h3_count": len(article.get("h3s", [])) if article else 0,
            "has_faq": article.get("has_faq", False) if article else False,
            "tables_count": article.get("tables_count", 0) if article else 0,
            "bullet_lists_count": article.get("bullet_lists_count", 0) if article else 0,
        })
    return features


def _classify_domain(domain: str, title: str, snippet: str) -> str:
    """Classify domain type based on URL patterns and content signals."""
    text = (title + " " + snippet).lower()

    # Media/publication
    if any(d in domain for d in ["news", "cnn", "bbc", "reuters", "bloomberg",
                                  "forbes", "wsj", "nytimes", "wired", "theverge",
                                  "techcrunch", "coindesk", "axios"]):
        return "media"
    if any(w in text for w in ["published", "reporter", "exclusive", "breaking"]):
        return "media"

    # Company/product
    if any(d in domain for d in [".com", ".io", ".ai"]) and not any(
        d in domain for d in ["blog.", "forum.", "wiki."]
    ):
        if any(w in text for w in ["pricing", "features", "download", "buy"]):
            return "company"
        # Check if it reads like a product page
        if len(domain.split(".")) == 2 and domain.endswith((".com", ".io", ".ai")):
            return "company"

    # Blog (subdomain or path)
    if "blog." in domain or "/blog/" in urlparse(f"https://{domain}").path:
        return "blog"
    if any(w in text for w in ["blog", "read more", "subscribe"]):
        return "blog"

    # Forum
    if any(d in domain for d in ["reddit", "quora", "stackexchange", "stackoverflow",
                                  "forum", "community."]):
        return "forum"

    # Wiki
    if "wiki" in domain or "wikipedia" in domain:
        return "wiki"

    # Educational
    if domain.endswith((".edu", ".ac.")):
        return "education"

    # Government
    if domain.endswith((".gov", ".mil")):
        return "government"

    return "blog"


def _classify_content_type(title: str, snippet: str) -> str:
    """Classify content type from title/snippet language patterns."""
    text = (title + " " + snippet).lower()

    if any(w in text for w in ["best", "top", "review", "vs ", " versus ", "alternative"]):
        return "list/comparison"
    if any(w in text for w in ["guide", "tutorial", "how to", "step-by-step", "walkthrough"]):
        return "guide"
    if any(w in text for w in ["what is", "what are", "definition", "explain", "meaning"]):
        return "informational"
    if any(w in text for w in ["news", "breaking", "just happened", "announced", "report"]):
        return "news"
    if any(w in text for w in ["pricing", "price", "cost", "buy", "coupon", "deal"]):
        return "landing/product"
    if any(w in text for w in ["why", "analysis", "deep dive", "investigation"]):
        return "analysis/opinion"

    return "blog"


def _detect_freshness(title: str, snippet: str) -> str | None:
    """Detect freshness signal (year or date) from title/snippet."""
    text = title + " " + snippet
    for year in range(2023, 2028):
        if str(year) in text:
            return str(year)
    m = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2},?\s+\d{4}',
                  text, re.IGNORECASE)
    if m:
        return m.group(0)
    m = re.search(r'(updated|published|modified)\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
                  text, re.IGNORECASE)
    if m:
        return m.group(0)
    return None


# ── 2. Authority Proxy Score ──────────────────────────────────

def calculate_authority_score(features: list[dict]) -> list[dict]:
    """Score each SERP URL 0-100 as an authority proxy.

    Signals weighted:
      - SERP position (higher position = Google trusts it more)
      - Word count depth (>2000 = strong, <500 = thin)
      - Structure quality (H2/H3 usage, FAQ, tables)
      - Domain authority proxy (media > company > blog)
      - Freshness signal (recently updated)
    """
    scored = []
    for f in features:
        score = 0

        # Position weight (inverted: pos 1 = +30, pos 10 = +3)
        pos = f.get("position", 5)
        score += max(0, 30 - (pos - 1) * 3)

        # Content depth
        wc = f.get("word_count", 0)
        if wc >= 3000:
            score += 25
        elif wc >= 2000:
            score += 20
        elif wc >= 1000:
            score += 15
        elif wc >= 500:
            score += 10
        elif wc > 0 and wc < 500:
            score -= 10  # thin content penalty

        # Structure quality
        structure_score = 0
        h2 = f.get("h2_count", 0)
        h3 = f.get("h3_count", 0)
        if h2 >= 5:
            structure_score += 10
        elif h2 >= 3:
            structure_score += 6
        elif h2 >= 1:
            structure_score += 3
        if h3 >= 5:
            structure_score += 5
        elif h3 >= 2:
            structure_score += 3
        if f.get("has_faq"):
            structure_score += 5
        if f.get("tables_count", 0) >= 1:
            structure_score += 5
        if f.get("bullet_lists_count", 0) >= 2:
            structure_score += 3
        score += min(structure_score, 25)

        # Domain authority proxy
        dt = f.get("domain_type", "blog")
        domain_scores = {
            "media": 25,
            "government": 25,
            "education": 22,
            "company": 18,
            "wiki": 20,
            "blog": 12,
            "forum": 8,
        }
        score += domain_scores.get(dt, 10)

        # Freshness bonus
        if f.get("freshness"):
            score += 5

        # Brand signal — branded domain or recognizable name
        domain = f.get("domain", "")
        if domain and len(domain.split(".")[0]) <= 8:
            # Short domain = likely branded
            score += 10

        scored.append({
            "url": f["url"],
            "domain": f["domain"],
            "position": pos,
            "authority_score": min(100, score),
            "word_count": wc,
            "structure_score": structure_score,
            "domain_type": dt,
        })

    scored.sort(key=lambda x: x["authority_score"], reverse=True)
    return scored


# ── 3. Intent Clustering Engine ──────────────────────────────

def detect_serp_intent_cluster(keyword: str, titles: list[str], snippets: list[str]) -> dict:
    """Analyze intent distribution across the SERP.

    Returns what percentage of top results fall into each intent category.
    """
    signals = {"informational": 0, "commercial": 0, "transactional": 0, "navigational": 0, "news": 0}
    total = len(titles)

    for title, snippet in zip(titles, snippets):
        text = (title + " " + snippet).lower()

        # Score each intent
        intent_scores = {
            "informational": sum(1 for w in ["what is", "how to", "guide", "tutorial",
                                              "definition", "explain", "overview", "basics"]
                                 if w in text),
            "commercial": sum(1 for w in ["best", "top", "review", "vs", "versus",
                                          "alternative", "compare", "recommended", "rating"]
                              if w in text),
            "transactional": sum(1 for w in ["buy", "price", "pricing", "cost", "coupon",
                                             "deal", "discount", "order", "subscribe"]
                                 if w in text),
            "navigational": sum(1 for w in ["login", "sign in", "download", "official",
                                            "website", "homepage"]
                                if w in text),
            "news": sum(1 for w in ["news", "breaking", "report", "today", "announced",
                                    "launched", "just happened", "update"]
                        if w in text),
        }

        # Assign highest scoring intent
        best_intent = max(intent_scores, key=intent_scores.get)
        if intent_scores[best_intent] > 0:
            signals[best_intent] += 1

    # Convert to percentages
    total_classified = sum(signals.values()) or 1
    distribution = {k: round(v / total_classified * 100) for k, v in signals.items()}
    dominant = max(distribution, key=distribution.get) if distribution else "informational"

    return {
        "distribution": distribution,
        "dominant_serp_intent": dominant,
        "serp_intent_match": dominant == _detect_keyword_intent(keyword),
        "intent_confidence": max(distribution.values()) if distribution else 0,
    }


def _detect_keyword_intent(keyword: str) -> str:
    """Lightweight keyword-level intent detection (matches _detect_search_intent logic)."""
    kw_l = keyword.lower()
    if any(w in kw_l for w in ["best", "top", "review", "alternative", "recommended"]):
        return "commercial"
    if any(w in kw_l for w in ["buy", "price", "cost", "coupon", "deal"]):
        return "transactional"
    if any(w in kw_l for w in ["login", "sign in", "download", "official"]):
        return "navigational"
    if any(w in kw_l for w in ["news", "today", "breaking", "announced", "latest"]):
        return "news"
    if any(w in kw_l for w in ["what is", "how to", "guide", "tutorial", "meaning"]):
        return "informational"
    return "informational"


# ── 4. Ranking Probability Model ──────────────────────────────

def estimate_ranking_probability(
    keyword: str,
    serp_features: list[dict],
    authority_scores: list[dict],
    intent_cluster: dict,
    serp_analysis: dict | None = None,
) -> dict:
    """Estimate probability of ranking in Top 3 / Top 10 for the keyword.

    Factors:
      - Content quality (word count depth vs SERP average)
      - Intent match (keyword + SERP intent alignment)
      - Authority fit (how our content compares to top URLs)
      - SERP gap exploitation (uniqueness vs competitors)
      - Competition strength (average authority of Top 10)
    """
    # Content quality: how deep must we go?
    avg_wc = 0
    wcs = [f.get("word_count", 0) for f in serp_features if f.get("word_count", 0) > 0]
    if wcs:
        avg_wc = sum(wcs) / len(wcs)
    median_wc = sorted(wcs)[len(wcs) // 2] if wcs else 1500
    target_wc = max(1500, int(median_wc * 1.2))  # 20% deeper than median

    # Authority fit: what's the average authority of Top 5?
    top5_scores = [a["authority_score"] for a in authority_scores if a["position"] <= 5]
    avg_top5_authority = sum(top5_scores) / len(top5_scores) if top5_scores else 30

    # Competition strength
    all_scores = [a["authority_score"] for a in authority_scores]
    avg_authority = sum(all_scores) / len(all_scores) if all_scores else 25
    max_authority = max(all_scores) if all_scores else 50

    # Content types present in SERP
    content_types = {}
    for f in serp_features:
        ct = f.get("content_type", "blog")
        content_types[ct] = content_types.get(ct, 0) + 1
    dominant_type = max(content_types, key=content_types.get) if content_types else "blog"

    # Extract gaps from serp_analysis for SERP gap exploitation score
    gaps = serp_analysis.get("content_gaps", []) if serp_analysis else []
    serp_gap_score = min(len(gaps) * 10, 40)

    # Domain diversity: how many domains in top 10 are from same site?
    domains = [a["domain"] for a in authority_scores]
    domain_recurrence = len(domains) - len(set(domains))

    # ── Score components ──
    components = {}

    # Content quality score (0-25)
    if avg_wc > 0:
        depth_ratio = min(target_wc / avg_wc, 2.0)
        components["content_depth"] = min(20, int(depth_ratio * 10))
    else:
        components["content_depth"] = 15  # default if no data

    # Intent match score (0-20)
    intent_match = intent_cluster.get("serp_intent_match", False)
    components["intent_match"] = 15 if intent_match else 5
    if intent_cluster.get("intent_confidence", 0) >= 60:
        components["intent_match"] += 5

    # Authority feasibility (0-25)
    # Can our article compete with the Top 5 authority?
    if avg_top5_authority <= 30:
        components["authority_feasibility"] = 25  # low bar
    elif avg_top5_authority <= 50:
        components["authority_feasibility"] = 18  # moderate
    elif avg_top5_authority <= 70:
        components["authority_feasibility"] = 10  # tough
    else:
        components["authority_feasibility"] = 5  # very tough

    # SERP gap exploitation (0-15)
    components["gap_exploitation"] = min(15, serp_gap_score)

    # Competition weakness (0-15)
    # High domain recurrence = low diversity = easier to break in
    if domain_recurrence >= 2:
        components["competition_weakness"] = 15
    elif domain_recurrence >= 1:
        components["competition_weakness"] = 10
    else:
        components["competition_weakness"] = 5

    total_score = sum(components.values())
    total_score = min(100, max(0, total_score))

    # Probability bands
    if total_score >= 75:
        top3_prob = 25
        top10_prob = 65
    elif total_score >= 60:
        top3_prob = 15
        top10_prob = 50
    elif total_score >= 45:
        top3_prob = 8
        top10_prob = 35
    elif total_score >= 30:
        top3_prob = 3
        top10_prob = 18
    else:
        top3_prob = 1
        top10_prob = 8

    no_rank_prob = 100 - top10_prob

    # Weaknesses
    weaknesses = []
    if components.get("authority_feasibility", 0) < 15:
        weaknesses.append("Authority gap too high — Top 10 domains have strong signals")
    if components.get("content_depth", 0) < 12 and avg_wc > 0:
        weaknesses.append(f"Content must be deeper — target {target_wc} words vs SERP average {int(avg_wc)}")
    if not intent_match:
        weaknesses.append("Intent mismatch between keyword and SERP majority")
    if components.get("gap_exploitation", 0) < 8:
        weaknesses.append("Few SERP gaps to exploit — differentiation will be harder")
    if max_authority > 70:
        weaknesses.append("Strong incumbent domains in Top 10 — requires exceptional quality to outrank")
    if component := components.get("competition_weakness", 0) >= 10:
        weaknesses.append("High domain diversity — SERP is competitive with many unique sites")

    return {
        "ranking_score": total_score,
        "top_3_probability": top3_prob,
        "top_10_probability": top10_prob,
        "no_rank_probability": no_rank_prob,
        "target_word_count": target_wc,
        "dominant_content_type": dominant_type,
        "components": components,
        "weaknesses": weaknesses[:4],  # top 4 weaknesses
        "serp_average_authority": int(avg_authority),
        "serp_max_authority": max_authority,
    }


# ── 5. Full Report ────────────────────────────────────────────

def build_ranking_report(keyword: str, serp_analysis: dict, results: list | None = None) -> dict:
    """Build the complete ranking intelligence report for a keyword.

    Args:
        keyword: The search keyword
        serp_analysis: The analysis dict from research_engine.build_serp_analysis()
        results: Optional raw search results (if available, avoids refetch)

    Returns:
        dict with all ranking intelligence data
    """
    # Get search results if not provided
    if not results:
        results = search_web(keyword, max_results=10)

    # 1. Extract SERP features
    features = build_serp_features(results)

    # 2. Calculate authority scores
    authority_scores = calculate_authority_score(features)

    # 3. Intent cluster
    titles = [r.get("title", "") for r in results]
    snippets = [r.get("snippet", "") for r in results]
    intent_cluster = detect_serp_intent_cluster(keyword, titles, snippets)

    # 4. Ranking probability
    ranking_prob = estimate_ranking_probability(
        keyword, features, authority_scores, intent_cluster, serp_analysis,
    )

    # 5. Build SERP feature summary from serp_analysis
    serp_summary = {
        "average_word_count": serp_analysis.get("average_word_count", 0),
        "common_headings": serp_analysis.get("common_headings", [])[:8],
        "content_gaps": serp_analysis.get("content_gaps", [])[:5],
        "dominant_search_intent": serp_analysis.get("dominant_search_intent", ""),
        "competitors_analyzed": serp_analysis.get("_competitors_analyzed", 0),
    }

    # 6. Top domains by authority
    top_domains = []
    for a in authority_scores[:5]:
        top_domains.append({
            "domain": a["domain"],
            "authority_score": a["authority_score"],
            "position": a["position"],
            "word_count": a["word_count"],
        })

    return {
        "keyword": keyword,
        "serp_summary": serp_summary,
        "intent_cluster": intent_cluster,
        "authority_scores": authority_scores[:10],
        "top_domains_by_authority": top_domains,
        "ranking_probability": ranking_prob,
        "serp_features_count": len(features),
    }
