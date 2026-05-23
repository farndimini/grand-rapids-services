"""
content_fingerprint.py — Section-level content fingerprinting & template bleed detection

Extracts structured sections from HTML articles, fingerprints each section,
detects template bleed (identical sentences across pages), and reports
differentiation gaps for programmatic SEO quality control.

Usage:
    from content_fingerprint import fingerprint_article, compare_articles, find_template_bleed
"""

import re
from typing import Any

# ──────────────────────────────────────────────
# SECTION EXTRACTION
# ──────────────────────────────────────────────

def extract_sections(html: str) -> list[dict[str, Any]]:
    """
    Split an HTML article into named sections.
    Returns list of {heading, body, sentences, word_count, fingerprint}.
    """
    sections = []
    # Split by h2 tags
    parts = re.split(r"(<h2[^>]*>.*?</h2>)", html, flags=re.DOTALL | re.IGNORECASE)
    current_heading = "preamble"

    for part in parts:
        part = part.strip()
        if not part:
            continue
        h2_match = re.match(r"<h2[^>]*>(.*?)</h2>", part, re.DOTALL | re.IGNORECASE)
        if h2_match:
            current_heading = re.sub(r"<[^>]+>", "", h2_match.group(1)).strip()
            continue

        # Extract text content
        text = re.sub(r"<[^>]+>", "", part).strip()
        text = re.sub(r"\s+", " ", text)
        if not text:
            continue

        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 15]
        words = text.split()

        sections.append({
            "heading": current_heading,
            "body": text,
            "sentences": sentences,
            "word_count": len(words),
            "fingerprint": _fingerprint_text(text),
        })

    return sections


def _fingerprint_text(text: str, n: int = 5) -> set[str]:
    """Generate an n-gram fingerprint of the text, filtering boilerplate."""
    # Filter out JSON-LD schema blocks (shared boilerplate across all pages)
    text = re.sub(r'<script[^>]*type="application/ld\+json"[^>]*>.*?</script>', "", text, flags=re.DOTALL | re.IGNORECASE)
    # Filter out meta tags
    text = re.sub(r'<meta[^>]*>', "", text, flags=re.IGNORECASE)
    # Filter out link tags
    text = re.sub(r'<link[^>]*>', "", text, flags=re.IGNORECASE)
    # Filter itemprop
    text = re.sub(r'<meta itemprop[^>]*>', "", text, flags=re.IGNORECASE)
    words = text.lower().split()
    if len(words) < n:
        return set([" ".join(words)])
    return set(" ".join(words[i:i+n]) for i in range(len(words) - n + 1))


# ──────────────────────────────────────────────
# SIMILARITY
# ──────────────────────────────────────────────

def jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two sets."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def section_similarity(section_a: dict[str, Any], section_b: dict[str, Any]) -> float:
    """Compare two sections by fingerprint overlap."""
    fp_a = section_a.get("fingerprint", set())
    fp_b = section_b.get("fingerprint", set())
    return jaccard_similarity(fp_a, fp_b)


def article_similarity(html_a: str, html_b: str) -> float:
    """Full-article Jaccard similarity."""
    fp_a = _fingerprint_text(re.sub(r"<[^>]+>", "", html_a))
    fp_b = _fingerprint_text(re.sub(r"<[^>]+>", "", html_b))
    return jaccard_similarity(fp_a, fp_b)


# ──────────────────────────────────────────────
# TEMPLATE BLEED DETECTION
# ──────────────────────────────────────────────

def _strip_html_body(html: str) -> str:
    """Extract body content, removing JSON-LD, meta, link, and script tags."""
    text = re.sub(r'<script[^>]*>.*?</script>', "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<meta[^>]*>', "", text, flags=re.IGNORECASE)
    text = re.sub(r'<link[^>]*>', "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_template_bleed(articles: list[dict[str, str]], min_len: int = 50) -> list[dict[str, Any]]:
    """
    Find exact sentence matches across multiple articles.
    articles: list of {slug, html}
    min_len: minimum sentence length to consider (avoids short boilerplate)
    Returns list of {sentence, count, slugs}
    """
    sentence_map: dict[str, list[str]] = {}

    for a in articles:
        text = _strip_html_body(a["html"])
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > min_len]
        seen = set()
        for s in sentences:
            s_lower = s.lower().strip()
            if s_lower not in seen:
                seen.add(s_lower)
                if s_lower not in sentence_map:
                    sentence_map[s_lower] = []
                sentence_map[s_lower].append(a["slug"])

    # Filter to sentences appearing in 2+ articles
    bleed = []
    for sentence, slugs in sentence_map.items():
        if len(slugs) >= 2:
            bleed.append({
                "sentence": sentence[:120] + "..." if len(sentence) > 120 else sentence,
                "count": len(slugs),
                "slugs": slugs,
            })

    bleed.sort(key=lambda x: x["count"], reverse=True)
    return bleed


# ──────────────────────────────────────────────
# FINGERPRINT REPORT
# ──────────────────────────────────────────────

def fingerprint_article(html: str, slug: str = "") -> dict[str, Any]:
    """
    Generate a full fingerprint report for a single article.
    """
    sections = extract_sections(html)
    text = _strip_html_body(html)

    # Detect repeated section types
    heading_counts: dict[str, int] = {}
    for s in sections:
        h = s["heading"]
        heading_counts[h] = heading_counts.get(h, 0) + 1

    return {
        "slug": slug,
        "total_words": len(text.split()),
        "num_sections": len(sections),
        "sections": [{"heading": s["heading"], "word_count": s["word_count"]} for s in sections],
        "heading_counts": heading_counts,
        "fingerprint": _fingerprint_text(text),
        "section_fingerprints": [s["fingerprint"] for s in sections],
    }


def differentiation_report(articles: list[dict[str, str]], threshold: float = 0.7) -> dict[str, Any]:
    """
    Compare all articles pairwise and report similarity risks.
    articles: list of {slug, html}
    threshold: similarity threshold for warning (0-1)
    """
    n = len(articles)
    pairs: list[dict[str, Any]] = []
    high_sim_pairs: list[dict[str, Any]] = []

    for i in range(n):
        fp_i = _fingerprint_text(_strip_html_body(articles[i]["html"]))
        for j in range(i + 1, n):
            fp_j = _fingerprint_text(_strip_html_body(articles[j]["html"]))
            sim = jaccard_similarity(fp_i, fp_j)
            pairs.append({
                "a": articles[i]["slug"],
                "b": articles[j]["slug"],
                "similarity": round(sim, 3),
            })
            if sim >= threshold:
                high_sim_pairs.append(pairs[-1])

    # Find template bleed
    bleed = find_template_bleed(articles)

    return {
        "total_articles": n,
        "pairs_checked": len(pairs),
        "high_similarity_pairs": len(high_sim_pairs),
        "threshold": threshold,
        "high_sim_pairs": high_sim_pairs,
        "template_bleed_items": len(bleed),
        "template_bleed": bleed[:20],  # top 20
        "avg_similarity": round(sum(p["similarity"] for p in pairs) / len(pairs), 3) if pairs else 0,
    }


# ──────────────────────────────────────────────
# QUALITY EXPANSION RULES
# ──────────────────────────────────────────────

def needs_differentiation(html: str, existing_fingerprints: list[set[str]], threshold: float = 0.7) -> bool:
    """Check if an article is too similar to any existing articles."""
    fp = _fingerprint_text(re.sub(r"<[^>]+>", "", html))
    for efp in existing_fingerprints:
        if jaccard_similarity(fp, efp) >= threshold:
            return True
    return False


def find_problematic_sections(html: str, existing_section_fps: list[list[set[str]]], threshold: float = 0.8) -> list[int]:
    """
    Find which section indices are too similar to existing sections.
    Returns list of section indices (0-based) that need differentiation.
    """
    sections = extract_sections(html)
    problematic = []
    for i, sec in enumerate(sections):
        fp = sec["fingerprint"]
        for efps in existing_section_fps:
            for efp in efps:
                if jaccard_similarity(fp, efp) >= threshold:
                    problematic.append(i)
                    break
            if i in problematic:
                break
    return list(set(problematic))
