"""temporal_grounding.py — Temporal Awareness Constraints Injector

Injects hard temporal boundaries into generation prompts to prevent
outdated hardware, software, or pricing references.
"""

from __future__ import annotations
from datetime import datetime
import logging
import re

log = logging.getLogger("temporal_grounding")

CURRENT_YEAR = 2026

# Products/technologies that should NOT appear unlabeled in 2026 content
FORBIDDEN_GENERATIONS: dict[str, list[str]] = {
    "cpu": [
        "Intel Core i9-13900K", "Intel 12th Gen", "Intel 13th Gen",
        "AMD Ryzen 7000 series", "AMD Ryzen 5000 series",
        "Intel Core i7-12700", "Intel Core i5-12400",
        "AMD Ryzen 9 5900X", "AMD Ryzen 7 5800X",
    ],
    "gpu": [
        "NVIDIA RTX 30-series", "NVIDIA RTX 3080", "NVIDIA RTX 3090",
        "NVIDIA GTX 16-series", "AMD RX 6000 series",
        "NVIDIA RTX 3060", "NVIDIA RTX 3070",
    ],
    "laptop": [
        "MacBook Pro M1", "MacBook Air M1", "MacBook Pro 2020",
        "Dell XPS 13 9310", "ThinkPad X1 Carbon Gen 9",
    ],
    "os": [
        "macOS Monterey", "macOS Ventura", "Windows 10",
        "iPadOS 15",
    ],
    "mobile": [
        "iPhone 13", "iPhone 14", "Samsung Galaxy S22",
        "Google Pixel 6", "Google Pixel 7",
    ],
}

# Minimum recency: products must be released within this many months
MAX_AGE_MONTHS = 18

# Override map: specific keyword contexts allow exceptions
EXCEPTION_MAP: dict[str, list[str]] = {
    "budget": ["Intel 13th Gen", "AMD Ryzen 7000 series", "RTX 3060"],
    "refurbished": ["Intel 12th Gen", "MacBook Pro 2020"],
    "used": ["MacBook Air M1", "Dell XPS 13 9310"],
    "enterprise": ["Windows 10", "ThinkPad X1 Carbon Gen 9"],
}


def build_temporal_constraint_block(
    keyword: str = "",
    niche: str = "",
    extra_forbidden: list[str] | None = None,
    extra_allowed: list[str] | None = None,
) -> str:
    """Build a prompt injection block with hard temporal constraints."""
    now = datetime.now()
    current_year = now.year

    # Keyword-based exception check
    kw_lower = keyword.lower()
    active_exceptions: set[str] = set()
    for trigger, items in EXCEPTION_MAP.items():
        if trigger in kw_lower:
            active_exceptions.update(x.lower() for x in items)

    # Build forbidden list, minus exceptions
    all_forbidden: list[str] = []
    for category, items in FORBIDDEN_GENERATIONS.items():
        for item in items:
            if item.lower() not in active_exceptions:
                all_forbidden.append(item)

    if extra_forbidden:
        all_forbidden.extend(extra_forbidden)

    # Build allowed list
    all_allowed: list[str] = []
    if extra_allowed:
        all_allowed.extend(extra_allowed)
    if active_exceptions:
        all_allowed.extend(active_exceptions)

    # Detect niche-specific temporal sensitivity
    niche_rules = ""
    niche_lower = niche.lower() if niche else ""
    if "tech" in niche_lower or "hardware" in niche_lower or "laptop" in niche_lower:
        niche_rules = (
            "- Products older than 18 months must be explicitly labeled 'previous generation'\n"
            "- Do NOT present last-generation hardware as current recommendations\n"
            "- If recommending a previous-gen product, state why (budget/enterprise legacy)"
        )
    elif "finance" in niche_lower or "crypto" in niche_lower:
        niche_rules = (
            "- Financial data older than 3 months is likely stale\n"
            "- Price predictions must include date context\n"
            "- Do NOT reference expired regulations or tax codes"
        )
    elif "health" in niche_lower or "medical" in niche_lower:
        niche_rules = (
            "- Medical studies older than 2 years must note their age\n"
            "- Do NOT reference withdrawn or superseded drug approvals\n"
            "- Treatment guidelines change annually — check recency"
        )

    block = f"""═══════════════════════════════════════════════════════════════
TEMPORAL GROUNDING — HARD CONSTRAINTS
═══════════════════════════════════════════════════════════════
- Current year: {current_year}
- You are writing content for {current_year} publication
- Maximum product age: {MAX_AGE_MONTHS} months (products released before {(current_year - 1) if MAX_AGE_MONTHS >= 12 else current_year} may be outdated)
- Do NOT mention any product from these outdated generations without explicit 'previous generation' labeling:
  {', '.join(all_forbidden[:12])}{'...' if len(all_forbidden) > 12 else ''}
"""
    if all_allowed:
        block += f"- Exceptions (allowed if contextually appropriate): {', '.join(all_allowed)}\n"
    if niche_rules:
        block += f"\nNICHE-SPECIFIC TEMPORAL RULES:\n{niche_rules}\n"

    block += (
        "PENALTY: Any unlabeled outdated reference will cause article REJECTION.\n"
        "═══════════════════════════════════════════════════════════════\n"
    )
    return block


def validate_temporal_compliance(html: str, keyword: str = "") -> list[dict]:
    """Scan generated HTML for forbidden generation references.

    Returns list of violations found.
    """
    violations: list[dict] = []
    kw_lower = keyword.lower()

    # Determine exceptions
    active_exceptions: set[str] = set()
    for trigger, items in EXCEPTION_MAP.items():
        if trigger in kw_lower:
            active_exceptions.update(x.lower() for x in items)

    html_lower = html.lower()
    for category, items in FORBIDDEN_GENERATIONS.items():
        for item in items:
            if item.lower() in active_exceptions:
                continue
            # Check if the forbidden item appears in HTML
            if item.lower() in html_lower:
                # Check if it's properly labeled as previous generation
                context_lines = _extract_context(html, item)
                has_qualifier = any(
                    phrase in ctx.lower()
                    for ctx in context_lines
                    for phrase in ["previous gen", "older gen", "last gen", "outdated", "legacy", "budget"]
                )
                violations.append({
                    "type": "outdated_reference",
                    "item": item,
                    "category": category,
                    "qualified": has_qualifier,
                    "context": context_lines[0] if context_lines else "",
                    "severity": "low" if has_qualifier else "high",
                })
    return violations


def _extract_context(html: str, item: str, window: int = 100) -> list[str]:
    """Extract surrounding text around an item mention for context analysis."""
    idx = html.lower().find(item.lower())
    if idx == -1:
        return []
    start = max(0, idx - window)
    end = min(len(html), idx + len(item) + window)
    return [html[start:end].strip()]


def format_violation_report(violations: list[dict]) -> str:
    """Format temporal violations into a readable report block."""
    if not violations:
        return ""
    high = [v for v in violations if v["severity"] == "high"]
    low = [v for v in violations if v["severity"] == "low"]
    lines = [
        "╔══════════════════════════════════════════════════════════",
        "║  TEMPORAL COMPLIANCE REPORT",
        "╚══════════════════════════════════════════════════════════",
    ]
    if high:
        lines.append(f"  ✗ {len(high)} HIGH severity violations (unlabeled outdated references):")
        for v in high:
            lines.append(f"    - {v['item']} [{v['category']}]")
    if low:
        lines.append(f"  ~ {len(low)} LOW severity violations (qualified as older):")
        for v in low[:5]:
            lines.append(f"    - {v['item']}")
    if not violations:
        lines.append("  ✓ All references temporally compliant")
    return "\n".join(lines)
