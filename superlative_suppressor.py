"""superlative_suppressor.py — Unsupported Superlative Detection & Downgrade

Scans generated content for unsupported superlatives and absolute claims,
then downgrades them to defensible language. Reduces hallucination rate,
spam score, and AI detection risk.
"""

from __future__ import annotations
import logging
import re
from typing import Callable

log = logging.getLogger("superlative_suppressor")

# Tier 1 — Highest risk superlatives (downgrade always unless cited)
HIGH_RISK_SUPERLATIVES: dict[str, str] = {
    r"\bthe\s+best\b": "a top",
    r"\bthe\s+ultimate\b": "a leading",
    r"\bthe\s+perfect\b": "a strong",
    r"\bunmatched\b": "very competitive",
    r"\bunbeatable\b": "excellent",
    r"\bpeerless\b": "outstanding",
    r"\bincomparable\b": "impressive",
    r"\bthe\s+finest\b": "a premier",
    r"\bsecond\s+to\s+none\b": "among the best",
    r"\bno\s+other\b": "few other",
}

# Tier 2 — Medium risk (downgrade if no nearby citation)
MEDIUM_RISK_SUPERLATIVES: dict[str, str] = {
    r"\bgame-changing\b": "impactful",
    r"\bgroundbreaking\b": "notable",
    r"\brevolutionary\b": "significant",
    r"\bcutting-edge\b": "modern",
    r"\bstate-of-the-art\b": "well-designed",
    r"\bindustry-leading\b": "high-quality",
    r"\bworld-class\b": "high-quality",
    r"\baward-winning\b": "well-regarded",
}

# Tier 3 — Absolute quantifiers (downgrade always unless evidence-bound)
ABSOLUTE_QUANTIFIERS: dict[str, str] = {
    r"\balways\b": "typically",
    r"\bnever\b": "rarely",
    r"\bevery\b": "most",
    r"\ball\b(?=\s+(users|developers|programmers|people|customers))": "many",
    r"\bnobody\b": "few",
    r"\beveryone\b": "many users",
    r"\bno\s+one\b": "few",
    r"\bperfect\b(?!\s+(choice|option|for|if|when))": "strong",
    r"\bguaranteed?\b": "highly likely",
    r"\b100%[^a-z]": "very high ",
}

CITATION_NEARBY_RX = re.compile(
    r'<a\s+href|<cite>|\[VERIFY\]|\[SOURCE\]|\(https?://|according to|"source',
    re.IGNORECASE,
)


def suppress_superlatives(html: str, keyword: str = "") -> str:
    """Scan HTML and downgrade unsupported superlatives.

    Strategy:
      - Tier 1 (high risk): downgrade always, unconditional
      - Tier 2 (medium risk): downgrade if no citation within context window
      - Tier 3 (absolute quantifiers): downgrade always
    """
    original = html

    # Tier 1 — always downgrade
    for pattern, replacement in HIGH_RISK_SUPERLATIVES.items():
        html = re.sub(pattern, replacement, html, flags=re.IGNORECASE)

    # Tier 2 — downgrade if no citation nearby
    for pattern, replacement in MEDIUM_RISK_SUPERLATIVES.items():
        html = _conditional_replace(html, pattern, replacement, citation_required=True)

    # Tier 3 — absolute quantifiers, always downgrade
    for pattern, replacement in ABSOLUTE_QUANTIFIERS.items():
        html = re.sub(pattern, replacement, html, flags=re.IGNORECASE)

    # Clean up doubled spaces from replacements
    html = re.sub(r'  +', ' ', html)

    changes = _count_changes(original, html)
    if changes > 0:
        log.info("[SuperlativeSuppressor] Downgraded %d superlatives for '%s'", changes, keyword)

    return html


def _conditional_replace(
    text: str,
    pattern: str,
    replacement: str,
    citation_required: bool = True,
) -> str:
    """Replace match only if no citation is found nearby."""
    def replacer(m: re.Match) -> str:
        if citation_required:
            # Check 200 chars before and after for citations
            start = max(0, m.start() - 200)
            end = min(len(text), m.end() + 200)
            window = text[start:end]
            if CITATION_NEARBY_RX.search(window):
                return m.group(0)  # keep original — has citation support
        return replacement
    return re.sub(pattern, replacer, text, flags=re.IGNORECASE)


def _count_changes(original: str, modified: str) -> int:
    """Count how many replacements were made (rough estimate)."""
    if original == modified:
        return 0
    # Simple heuristic: count different character positions
    changes = 0
    for i in range(min(len(original), len(modified))):
        if original[i] != modified[i]:
            changes += 1
    return changes


def scan_superlatives(html: str) -> dict:
    """Analyze an article and return a report of all superlatives found.

    Does NOT modify the article — only reports.
    """
    results: list[dict] = []
    total = 0
    unsupported = 0

    for tier, patterns in [
        ("high", HIGH_RISK_SUPERLATIVES),
        ("medium", MEDIUM_RISK_SUPERLATIVES),
        ("absolute", ABSOLUTE_QUANTIFIERS),
    ]:
        for pattern, _ in patterns.items():
            for m in re.finditer(pattern, html, re.IGNORECASE):
                total += 1
                start = max(0, m.start() - 100)
                end = min(len(html), m.end() + 100)
                has_citation = bool(CITATION_NEARBY_RX.search(html[start:end]))
                if not has_citation:
                    unsupported += 1
                results.append({
                    "term": m.group(0),
                    "position": m.start(),
                    "tier": tier,
                    "has_citation": has_citation,
                    "context": html[max(0, m.start() - 30):m.end() + 30].strip(),
                })

    return {
        "total_superlatives": total,
        "unsupported": unsupported,
        "support_rate": round((total - unsupported) / max(1, total) * 100, 1),
        "details": results[:20],  # limit detail output
    }


def generate_suppression_report(report: dict) -> str:
    """Format superlative scan as a CLI-friendly report."""
    lines = [
        "╔══════════════════════════════════════════════════════════",
        "║  SUPERLATIVE SUPPRESSION REPORT",
        "╚══════════════════════════════════════════════════════════",
        f"  Total superlatives: {report['total_superlatives']}",
        f"  Unsupported:        {report['unsupported']}",
        f"  Support rate:       {report['support_rate']}%",
    ]
    if report["details"]:
        lines.append("  Sample:")
        for d in report["details"][:5]:
            lines.append(f"    [{d['tier']}] '{d['term']}' — cited={d['has_citation']}")
    return "\n".join(lines)
