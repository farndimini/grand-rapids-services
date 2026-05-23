"""
SEO Agent Pro — Content Gap Engine.

Detects what top-ranking competitors are NOT covering and generates
unique content angles that differentiate articles from the SERP.

Pure functions, no side effects, no external dependencies.
"""

import logging
from collections import Counter
from typing import Optional

log = logging.getLogger("content_gap")

# ── Universal gap angles that apply across most keywords ────

_GAP_ANGLE_TEMPLATES = {
    "hidden_costs": {
        "section_title": "Hidden Costs Most Reviews Don't Mention",
        "description": (
            "Surface the real total cost of ownership — not just the sticker price. "
            "Include: setup fees, mandatory upgrades, usage-based pricing surprises, "
            "enterprise upsells, and what the 'free' tier actually limits."
        ),
        "priority": "high",
    },
    "migration_pain": {
        "section_title": "Migration Reality: What Switching Actually Costs",
        "description": (
            "Be honest about switching costs that competitors downplay. "
            "Include: data export limitations, format incompatibility, "
            "downtime during transition, team retraining time, and "
            "the hidden cost of 'we'll import everything' promises."
        ),
        "priority": "high",
    },
    "onboarding_friction": {
        "section_title": "Onboarding Friction: The First 48 Hours",
        "description": (
            "Describe the real first-time experience most reviews skip. "
            "Include: setup complexity, default configuration problems, "
            "tutorial quality (or lack thereof), and how long until "
            "a new user actually feels productive."
        ),
        "priority": "high",
    },
    "lock_in_risk": {
        "section_title": "Lock-In Risk: How Hard Is It to Leave?",
        "description": (
            "Analyze ecosystem lock-in that makes switching painful later. "
            "Include: proprietary formats, integration dependencies, "
            "data portability, API access, and whether the platform "
            "supports standard export formats."
        ),
        "priority": "high",
    },
    "performance_limits": {
        "section_title": "Performance Limits: Where It Breaks Down",
        "description": (
            "Reveal the breaking points that only emerge under real usage. "
            "Include: speed under load, dataset size limits, concurrent user "
            "limits, browser/OS compatibility issues, and mobile app quality."
        ),
        "priority": "medium",
    },
    "real_frustrations": {
        "section_title": "What Real Users Complain About (That Reviews Ignore)",
        "description": (
            "Surface genuine user frustrations gathered from support forums, "
            "review sites, and social media. Include: update quality regression, "
            "customer support response times, feature request handling, "
            "and bugs that have gone unfixed for months."
        ),
        "priority": "high",
    },
    "advanced_use_cases": {
        "section_title": "Advanced Use Cases Competitors Overlook",
        "description": (
            "Cover power-user scenarios that beginner-focused guides miss. "
            "Include: automation workflows, API integration patterns, "
            "custom scripting, batch operations, and scaling strategies "
            "for enterprise or high-volume users."
        ),
        "priority": "medium",
    },
    "comparison_depth": {
        "section_title": "Beyond Features: What the Comparison Tables Miss",
        "description": (
            "Go deeper than feature-checklist comparisons. "
            "Include: ecosystem maturity, community size, third-party "
            "integration quality, documentation depth, and whether "
            "the roadmap aligns with your use case."
        ),
        "priority": "medium",
    },
    "trust_tradeoffs": {
        "section_title": "Trust Tradeoffs: What You're Really Signing Up For",
        "description": (
            "Be transparent about non-obvious tradeoffs. "
            "Include: data privacy policies, vendor lock-in through "
            "integrations, upgrade pressure, sunset risk for acquired "
            "products, and whether the business model aligns with users."
        ),
        "priority": "medium",
    },
    "expert_shortcuts": {
        "section_title": "Expert Workflows: Shortcuts Only Power Users Know",
        "description": (
            "Share insider knowledge that separates beginners from pros. "
            "Include: keyboard shortcuts, hidden settings, automation tricks, "
            "underused features that solve real problems, and configurations "
            "that take weeks to discover on your own."
        ),
        "priority": "low",
    },
}


def extract_topic_frequency(
    headings: list[str],
    entities: list[str],
) -> dict:
    """Analyze heading and entity frequency across competitors.

    Returns:
        common_topics: headings appearing in 3+ competitors
        overcovered_topics: headings appearing in 5+ competitors (saturated)
        entity_frequency: {entity_name: count}
    """
    heading_counter = Counter(h.strip().lower() for h in headings if len(h.strip()) > 5)
    entity_counter = Counter(e.lower() for e in entities if len(e) > 3)

    total = max(1, len(headings) or 1)

    common_topics = [
        h for h, c in heading_counter.most_common(15)
        if c >= max(2, total * 0.3)
    ]
    overcovered_topics = [
        h for h, c in heading_counter.most_common(10)
        if c >= max(4, total * 0.6)
    ]
    entity_frequency = dict(entity_counter.most_common(20))

    log.info(f"  [GAP]  {len(common_topics)} common topics, {len(overcovered_topics)} over-covered")
    return {
        "common_topics": common_topics,
        "overcovered_topics": overcovered_topics,
        "entity_frequency": entity_frequency,
    }


def detect_missing_angles(
    common_topics: list[str],
    entities: list[str],
    keyword: str,
) -> list[dict]:
    """Detect high-value content angles competitors are NOT covering.

    Returns list of {angle, section_title, description, rationale, priority}
    """
    kw_lower = keyword.lower()
    all_text = " ".join(common_topics).lower()

    missing = []

    for key, template in _GAP_ANGLE_TEMPLATES.items():
        # Skip if competitor already covers something too similar
        if _is_covered_by_competitors(template["section_title"], all_text, kw_lower):
            continue
        missing.append({
            "angle": key,
            "section_title": template["section_title"],
            "description": template["description"],
            "rationale": f"Competitors rarely or never cover '{template['section_title']}'",
            "priority": template["priority"],
        })

    missing.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["priority"]])

    log.info(f"  [GAP]  {len(missing)} missing angles detected")
    return missing


def _is_covered_by_competitors(section_title: str, competitor_text: str, keyword: str) -> bool:
    """Check if competitors already cover a topic (by keyword overlap)."""
    title_lower = section_title.lower()
    # Extract significant words from section title
    significant = [w for w in title_lower.split() if len(w) > 4 and w not in keyword]
    if not significant:
        return False
    # If any significant word appears in competitor headings, consider it covered
    matches = sum(1 for w in significant if w in competitor_text)
    return matches >= len(significant) * 0.5


def generate_gap_opportunities(
    keyword: str,
    competitor_data: dict,
) -> dict:
    """Full gap analysis from competitor analysis data.

    Returns structured gap opportunities for injection into strategy.
    """
    # Extract data from competitor_data (works with both SERP and LLM modes)
    headings = competitor_data.get("common_headings", []) or competitor_data.get("common_sections", [])
    entities = competitor_data.get("entities", [])
    gaps = competitor_data.get("missing_gaps", []) or competitor_data.get("content_gaps", [])

    # Topic frequency
    freq = extract_topic_frequency(headings, entities)

    # Missing angles
    missing_angles = detect_missing_angles(
        freq["common_topics"],
        entities,
        keyword,
    )

    # Undercovered entities — entities that appear in SERP but rarely in articles
    entity_text = " ".join(entities).lower() if entities else ""
    undercovered = [
        e for e in entities[:10]
        if len(e) > 3 and e.lower() not in entity_text
    ][:5]

    # High-opportunity angles — the best gaps to fill
    high_opportunity = [
        {
            "section_title": a["section_title"],
            "description": a["description"],
            "rationale": a["rationale"],
        }
        for a in missing_angles
        if a["priority"] in ("high",)
    ]

    # Uniqueness score (0-100) based on how many gap angles are available
    base_score = 50
    gap_bonus = min(30, len(missing_angles) * 5)
    uniqueness_score = min(100, base_score + gap_bonus)

    # Penalize if most gaps from legacy analysis are generic
    generic_gaps = {"real-world case studies", "budget-friendly options", "step-by-step tutorials"}
    if gaps and all(g.lower() in generic_gaps for g in gaps):
        uniqueness_score = max(30, uniqueness_score - 10)

    result = {
        "common_topics": freq["common_topics"],
        "missing_topics": [a["section_title"] for a in missing_angles],
        "high_opportunity_angles": high_opportunity,
        "all_gap_angles": missing_angles,
        "undercovered_entities": undercovered,
        "uniqueness_score": uniqueness_score,
        "overcovered_topics": freq["overcovered_topics"],
    }

    log.info(f"  [GAP]  Uniqueness score: {uniqueness_score}/100 · {len(high_opportunity)} high-opportunity angles")
    return result


def score_uniqueness(
    required_sections: list[str],
    common_headings: list[str],
) -> dict:
    """Score how unique proposed article sections are vs competitors.

    Returns:
        uniqueness_score: 0-100
        overlap_sections: sections too similar to competitors
        unique_sections: sections not found in competitors
        needs_rewrite: True if similarity is too high
    """
    if not common_headings:
        return {
            "uniqueness_score": 80,
            "overlap_sections": [],
            "unique_sections": required_sections,
            "needs_rewrite": False,
        }

    competitor_lower = [h.lower().strip() for h in common_headings]
    overlap = []
    unique = []

    for section in required_sections:
        s_lower = section.lower().strip()
        # Check for significant word overlap with any competitor heading
        words = set(w for w in s_lower.split() if len(w) > 3)
        is_overlap = False
        for ch in competitor_lower:
            ch_words = set(w for w in ch.split() if len(w) > 3)
            if words and ch_words:
                intersection = words & ch_words
                overlap_ratio = len(intersection) / max(1, len(words))
                if overlap_ratio > 0.6:
                    is_overlap = True
                    break
        if is_overlap:
            overlap.append(section)
        else:
            unique.append(section)

    overlap_count = len(overlap)
    total = len(required_sections) or 1
    overlap_ratio = overlap_count / total

    # Score: more unique sections = higher score
    uniqueness_score = max(0, min(100, int(100 - (overlap_ratio * 70))))

    # Bonus for having clearly unique sections
    if len(unique) >= 2:
        uniqueness_score = min(100, uniqueness_score + 10)
    if len(unique) >= 4:
        uniqueness_score = min(100, uniqueness_score + 10)

    needs_rewrite = uniqueness_score < 40

    if needs_rewrite:
        log.info(f"  [GAP]  ⚠ Uniqueness {uniqueness_score}/100 — below threshold, rewrite advised")

    return {
        "uniqueness_score": uniqueness_score,
        "overlap_sections": overlap,
        "unique_sections": unique,
        "needs_rewrite": needs_rewrite,
    }


def build_mandatory_gap_prompt(gap_opportunities: dict) -> str:
    """Build a prompt fragment that forces the writer to include gap sections.

    Returns a string to append to the article generation prompt.
    """
    high_angles = gap_opportunities.get("high_opportunity_angles", [])
    all_angles = gap_opportunities.get("all_gap_angles", [])
    undercovered = gap_opportunities.get("undercovered_entities", [])

    if not high_angles and not all_angles:
        return ""

    sections = []
    selected = high_angles[:3] if high_angles else all_angles[:3]

    for angle in selected:
        sections.append(f"""
## {angle['section_title']}
{angle['description']}""")

    prompt = f"""
CRITICAL — COMPETITOR GAP SECTIONS (MANDATORY):
The following sections MUST be included because NO competitor covers them.
These are your competitive advantage for ranking.

{chr(10).join(sections)}
"""

    if undercovered:
        entity_list = ", ".join(undercovered[:4])
        prompt += f"""
Include these undercovered entities naturally: {entity_list}.
"""

    prompt += """
Each gap section must:
- Be 200-400 words of original analysis
- Include specific examples or data points
- Avoid generic statements
- Feel like insider knowledge, not Wikipedia
"""

    return prompt
