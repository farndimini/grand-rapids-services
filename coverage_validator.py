"""coverage_validator.py — Pre-Generation Outline Coverage Audit

Ensures minimum product count, required sections, and coverage
breadth BEFORE the article is generated. Prevents thin content
and generic FAQ recycling.
"""

from __future__ import annotations
import logging
import re
from typing import Any

log = logging.getLogger("coverage_validator")

# Minimum requirements by intent
COVERAGE_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "COMMERCIAL": {
        "min_products": 8,
        "required_sections": [
            "comparison",
            "pricing",
            "how to choose",
            "faq",
            "verdict",
        ],
        "min_word_count": 2000,
        "suggested_sections": [
            "hidden costs",
            "who should use",
            "pros and cons",
            "alternatives",
        ],
    },
    "INFORMATIONAL": {
        "min_products": 0,
        "required_sections": [
            "introduction",
            "step",
            "faq",
            "summary",
        ],
        "min_word_count": 1500,
        "suggested_sections": [
            "common mistakes",
            "pro tips",
        ],
    },
    "TRANSACTIONAL": {
        "min_products": 5,
        "required_sections": [
            "comparison",
            "pricing",
            "how to get started",
            "faq",
        ],
        "min_word_count": 1500,
        "suggested_sections": [
            "free vs paid",
            "features worth paying for",
        ],
    },
    "NAVIGATIONAL": {
        "min_products": 1,
        "required_sections": [
            "features",
            "pricing",
            "pros and cons",
            "alternatives",
            "faq",
        ],
        "min_word_count": 1200,
        "suggested_sections": [
            "how to install",
            "is it worth it",
        ],
    },
    "CHROME_EXTENSIONS": {
        "min_products": 10,
        "required_sections": [
            "quick overview",
            "comparison table",
            "how to choose",
            "faq",
            "verdict",
        ],
        "min_word_count": 2500,
        "suggested_sections": [
            "hidden downsides",
            "screenshots",
        ],
    },
}

# Fallback for unknown intent
DEFAULT_REQUIREMENTS: dict[str, Any] = {
    "min_products": 5,
    "required_sections": ["introduction", "faq", "verdict"],
    "min_word_count": 1500,
    "suggested_sections": [],
}


def validate_outline_coverage(
    strategy: dict,
    keyword: str,
    intent: str = "COMMERCIAL",
) -> dict:
    """Validate the strategy/outline for coverage completeness BEFORE generation.

    Returns a dict with:
      - passed: bool
      - issues: list of coverage issues found
      - fix_suggestions: list of suggested fixes
      - regenerated_strategy: updated strategy dict with fixes applied (if possible)
    """
    issues: list[dict] = []
    fix_suggestions: list[str] = []

    reqs = COVERAGE_REQUIREMENTS.get(intent, DEFAULT_REQUIREMENTS)
    sections = strategy.get("required_sections", [])
    elements = strategy.get("must_have_elements", [])
    target_length = strategy.get("ideal_length", 0)
    product_count = _estimate_product_count(strategy)

    sections_lower = [s.lower() for s in sections]
    elements_lower = [e.lower() for e in elements]
    combined = sections_lower + elements_lower

    # 1. Check product count
    req_products = reqs["min_products"]
    if product_count < req_products:
        issues.append({
            "type": "insufficient_products",
            "severity": "high",
            "message": f"Only ~{product_count} products, need at least {req_products}",
            "found": product_count,
            "required": req_products,
        })
        fix_suggestions.append(
            f"Expand to at least {req_products} products across budget/mid-range/premium tiers"
        )

    # 2. Check required sections
    for req_section in reqs["required_sections"]:
        if not any(req_section in s for s in combined):
            issues.append({
                "type": "missing_section",
                "severity": "high",
                "message": f"Missing required section: '{req_section}'",
                "section": req_section,
            })
            fix_suggestions.append(f"Add H2 section: '{req_section.title()}'")

    # 3. Check target length
    min_words = reqs["min_word_count"]
    if target_length < min_words:
        issues.append({
            "type": "insufficient_length",
            "severity": "medium",
            "message": f"Target length {target_length} words, need at least {min_words}",
            "found": target_length,
            "required": min_words,
        })
        fix_suggestions.append(f"Increase target length to at least {min_words} words")

    # 4. Check for generic FAQ warning
    if "faq" in combined:
        faq_item = _find_strategy_element(strategy, "faq")
        if faq_item and _is_generic_faq(str(faq_item)):
            issues.append({
                "type": "generic_faq",
                "severity": "medium",
                "message": "FAQ appears generic/recycled — needs specific, keyword-aligned questions",
            })
            fix_suggestions.append(
                "Replace generic FAQ questions with specific ones tied to "
                f"the keyword '{keyword}' and its subtopics"
            )

    # 5. Check for product diversity (budget/mid/premium)
    if product_count >= 3 and not _has_price_tier_diversity(strategy):
        issues.append({
            "type": "missing_price_tiers",
            "severity": "low",
            "message": "Products may lack price tier diversity (budget/mid-range/premium)",
        })
        fix_suggestions.append("Ensure products span budget, mid-range, and premium price tiers")

    passed = len([i for i in issues if i["severity"] == "high"]) == 0

    return {
        "passed": passed,
        "issues": issues,
        "fix_suggestions": fix_suggestions,
        "intent": intent,
        "keyword": keyword,
        "product_count": product_count,
        "target_length": target_length,
        "required_sections_found": sum(
            1 for r in reqs["required_sections"] if any(r in s for s in combined)
        ),
        "required_sections_total": len(reqs["required_sections"]),
    }


def _estimate_product_count(strategy: dict) -> int:
    """Estimate how many products/tools the outline covers."""
    sections = strategy.get("required_sections", [])
    elements = strategy.get("must_have_elements", [])
    all_items = sections + elements

    # Count explicit product names in section titles
    count = 0
    for item in all_items:
        # Numbers like "#1", "#2", "Top 5" indicate products
        nums = re.findall(r'#(\d+)|Top\s*(\d+)|(\d+)\s*(Laptops|Tools|Options|Best)', str(item))
        for n in nums:
            try:
                count += max(int(x) for x in n if x)
            except (ValueError, TypeError):
                pass

    # Also check for explicit product mentions
    product_indicators = ["MacBook", "ThinkPad", "XPS", "Surface", "Spectre",
                          "Gram", "ZenBook", "ROG", "Legion", "IdeaPad",
                          "Pixelbook", "Galaxy Book", "ENVY", "Pavilion",
                          "Precision", "Latitude", "Yoga", "Carbon", "Serval"]
    for item in all_items:
        for indicator in product_indicators:
            if indicator.lower() in str(item).lower():
                count += 1

    # Count the elements that look like product entries
    entry_count = 0
    for elem in elements:
        if elem.lower().startswith(("product", "item", "entry", "laptop", "tool")):
            entry_count += 1

    return max(count, entry_count, 1)


def _find_strategy_element(strategy: dict, name: str) -> Any:
    """Find an element by name in the strategy."""
    for key in ["required_sections", "must_have_elements"]:
        for item in strategy.get(key, []):
            if name.lower() in str(item).lower():
                return item
    return None


def _is_generic_faq(faq_text: str) -> bool:
    """Detect if FAQ content is generic/recycled."""
    generic_phrases = [
        "what is the best",
        "how much does it cost",
        "are there free alternatives",
        "which is easiest to use",
        "how do i choose",
        "is it worth it",
        "what is the difference between",
    ]
    text_lower = faq_text.lower()
    matches = sum(1 for p in generic_phrases if p in text_lower)
    return matches >= 3


def _has_price_tier_diversity(strategy: dict) -> bool:
    """Check if the outline mentions budget/mid/premium."""
    text = str(strategy.get("required_sections", [])) + str(strategy.get("must_have_elements", []))
    text_lower = text.lower()
    tier_count = 0
    for tier in ["budget", "mid-range", "midrange", "premium", "high-end", "low-cost", "affordable"]:
        if tier in text_lower:
            tier_count += 1
    return tier_count >= 2


def auto_fix_strategy(strategy: dict, validation: dict, keyword: str, intent: str) -> dict:
    """Automatically fix strategy gaps where possible."""
    fixed = dict(strategy)
    reqs = COVERAGE_REQUIREMENTS.get(intent, DEFAULT_REQUIREMENTS)

    # Fix length
    if validation["target_length"] < reqs["min_word_count"]:
        fixed["ideal_length"] = reqs["min_word_count"]

    # Add missing sections
    sections = list(fixed.get("required_sections", []))
    elements = list(fixed.get("must_have_elements", []))
    combined_lower = [s.lower() for s in sections] + [e.lower() for e in elements]

    for req_section in reqs["required_sections"]:
        if not any(req_section in s for s in combined_lower):
            sections.append(req_section.title())

    # Add suggested sections
    for sug_section in reqs["suggested_sections"]:
        if not any(sug_section in s for s in combined_lower):
            elements.append(sug_section.title())

    fixed["required_sections"] = sections
    fixed["must_have_elements"] = elements

    # Add product diversity note
    if validation.get("product_count", 0) < reqs["min_products"]:
        note = (
            f"Include at least {reqs['min_products']} products spanning "
            "budget, mid-range, and premium price tiers"
        )
        if "coverage_note" not in fixed:
            fixed["coverage_note"] = note
        else:
            fixed["coverage_note"] += " " + note

    log.info(
        "[CoverageValidator] Auto-fixed strategy for '%s': %d sections, %d words",
        keyword, len(sections), fixed.get("ideal_length", 0)
    )
    return fixed
