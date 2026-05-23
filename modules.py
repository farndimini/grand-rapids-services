"""
SEO Agent Pro — Core pipeline modules.
Each module is a pure function: takes inputs, calls the LLM, returns data.
"""

import json
import logging
import re
import time
from collections import Counter
from datetime import datetime as _mod_dt, timedelta

from llm_router import call, call_json, c
from post_processor import fix_article
from local_intelligence import (
    enhance_article,
    build_enriched_local_business_schema,
    build_local_faq_html,
    build_local_faq_schema,
    build_cta_html,
    build_pricing_table,
    build_brands_html,
    build_enhanced_pricing_table,
    inject_reviews,
    inject_business_identity,
    inject_trust_badges,
    GRAND_RAPIDS,
    NEIGHBORHOODS,
    SUBURBS,
    ZIP_CODES,
    BUSINESS_IDENTITY,
)
from system_hardening import (
    get_prompt_fingerprinter,
    get_failure_monitor,
    get_claim_auditor,
    get_contamination_scorer,
)

# Real SERP intelligence engine — fallback-safe
try:
    from seo.research_engine import build_serp_analysis
    _HAS_REAL_SERP = True
except ImportError:
    _HAS_REAL_SERP = False

# Content gap engine — detects competitor blind spots
try:
    from seo.content_gap import generate_gap_opportunities, build_mandatory_gap_prompt
    _HAS_GAP_ENGINE = True
except ImportError:
    _HAS_GAP_ENGINE = False

# SERP ranking intelligence — predicts ranking probability
try:
    from seo.ranking_intelligence import build_ranking_report
    _HAS_RANKING_INTEL = True
except ImportError:
    _HAS_RANKING_INTEL = False

# Ranking Brain — pre-publish prediction + suggestions
try:
    from seo.ranking_brain import analyze_competition_gap
    _HAS_RANKING_BRAIN = True
except ImportError:
    _HAS_RANKING_BRAIN = False

# Phase 3 — Autonomous intelligence engines
try:
    from seo_intelligence import (
        get_human_rewriter,
        get_conversion_optimizer,
        get_ai_resistance,
        get_authority_graph,
        get_pattern_tracker,
        get_citation_engine,
        get_retrieval_validator,
        get_serp_gap_engine,
    )
    _HAS_INTELLIGENCE = True
except ImportError:
    _HAS_INTELLIGENCE = False

log = logging.getLogger("modules")

# Temporal grounding — prevents outdated references
try:
    from temporal_grounding import (
        build_temporal_constraint_block,
        validate_temporal_compliance,
        format_violation_report,
    )
    _HAS_TEMPORAL_GROUNDING = True
except ImportError:
    _HAS_TEMPORAL_GROUNDING = False

# Coverage validator — pre-generation outline audit
try:
    from coverage_validator import (
        validate_outline_coverage,
        auto_fix_strategy,
    )
    _HAS_COVERAGE_VALIDATOR = True
except ImportError:
    _HAS_COVERAGE_VALIDATOR = False

# Superlative suppressor — downgrades unsupported claims
try:
    from superlative_suppressor import (
        suppress_superlatives,
        scan_superlatives,
        generate_suppression_report,
    )
    _HAS_SUPERLATIVE_SUPPRESSOR = True
except ImportError:
    _HAS_SUPERLATIVE_SUPPRESSOR = False

# Evidence pack — pre-generation evidence extraction
try:
    from evidence_pack import EvidencePack
    _HAS_EVIDENCE_PACK = True
    _evidence_pack = EvidencePack()
except ImportError:
    _HAS_EVIDENCE_PACK = False
    _evidence_pack = None

# Editorial scoring — unified quality dashboard
try:
    from editorial_score import compute_editorial_score, EditorialScoreReport
    _HAS_EDITORIAL_SCORE = True
except ImportError:
    _HAS_EDITORIAL_SCORE = False

# Benchmark arena — systematic quality evaluation
try:
    from benchmarks import run_all_benchmarks, format_benchmark_report
    _HAS_BENCHMARKS = True
except ImportError:
    _HAS_BENCHMARKS = False


# ──────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────

def _step(label: str) -> None:
    print(f"\n{c('cyan', '▸')} {c('bold', label)}")

def _ok(msg: str) -> None:
    print(c("green", f"  ✓ {msg}"))

def _info(msg: str) -> None:
    print(c("dim", f"  · {msg}"))


# ──────────────────────────────────────────────────────────────
#  Module 1 — Competitor Analysis
# ──────────────────────────────────────────────────────────────

def analyze_competitors(keyword: str, model: str) -> dict:
    _step(f"Competitor Analysis  →  \"{keyword}\"")

    # ── Try real SERP intelligence engine first ──────────────
    if _HAS_REAL_SERP:
        try:
            serp_data = build_serp_analysis(keyword)
            if serp_data and serp_data.get("_serp_source") != "empty_fallback":
                result = serp_data
                _ok(f"REAL SERP — {result.get('_competitors_analyzed', 0)} competitors analyzed")
                _ok(f"Common sections: {len(result.get('common_sections', []))}")
                _ok(f"Content gaps: {len(result.get('missing_gaps', []))}")
                _ok(f"Avg length: {result.get('content_length_avg', '?')} words")
                _ok(f"Intent: {result.get('dominant_search_intent', '?')}")
                for gap in result.get("missing_gaps", [])[:3]:
                    _info(f"Gap → {gap}")

                # Attach ranking intelligence
                if _HAS_RANKING_INTEL:
                    try:
                        ranking = build_ranking_report(keyword, result)
                        result["_ranking_report"] = ranking
                        rp = ranking.get("ranking_probability", {})
                        _ok(f"Ranking: Top-10 {rp.get('top_10_probability', '?')}% · Score {rp.get('ranking_score', '?')}/100")
                        for w in rp.get("weaknesses", [])[:2]:
                            _info(f"Weakness → {w}")
                    except Exception:
                        log.warning("[MODULES] build_ranking_report failed for '%s'", keyword)

                # Store SERP evidence for pre-generation evidence pack
                result["_competitors_detail"] = {
                    "entities": result.get("entities", [])[:15],
                    "top_urls": result.get("top_urls", [])[:5],
                    "competitor_titles": result.get("competitor_titles", [])[:5],
                    "common_headings": result.get("common_headings", result.get("common_sections", []))[:10],
                    "intent": result.get("dominant_search_intent", ""),
                    "avg_word_count": result.get("average_word_count", 0),
                }

                return result
        except Exception as e:
            log.info(f"  [SERP]  Real SERP failed: {e} — falling back to LLM")

    # ── Fallback: LLM-based competitor analysis ──────────────
    _info("Using LLM-based competitor analysis (real SERP unavailable)")

    system = (
        "You are a senior SEO analyst. Based on your knowledge of web content patterns, "
        "analyze what the top-ranking pages for a given keyword typically look like."
    )
    user = f"""Analyze the competitive landscape for the keyword: "{keyword}"

Return a JSON object:
{{
  "common_sections":    ["list of H2/H3 headings found in top results"],
  "missing_gaps":       ["topics competitors rarely cover"],
  "content_length_avg": "estimated average word count",
  "seo_patterns":       ["structural or formatting patterns used"],
  "weaknesses":         ["what most articles do poorly"],
  "why_they_rank":      "main reason top results rank (depth/authority/UX/etc)"
}}"""

    result = call_json(system, user, model)

    _ok(f"Common sections: {len(result.get('common_sections', []))}")
    _ok(f"Content gaps: {len(result.get('missing_gaps', []))}")
    _ok(f"Avg length: {result.get('content_length_avg', '?')} words")
    for gap in result.get("missing_gaps", [])[:3]:
        _info(f"Gap → {gap}")

    return result


# ──────────────────────────────────────────────────────────────
#  Module 2 — Strategy Decision
# ──────────────────────────────────────────────────────────────

def decide_strategy(keyword: str, competitor_data: dict, articles_written: int, model: str) -> dict:
    _step("Strategy Decision Engine")

    # ── Inject content gap analysis into strategy ─────────────
    gap_data = None
    if _HAS_GAP_ENGINE:
        try:
            gap_data = generate_gap_opportunities(keyword, competitor_data)
            if gap_data:
                _ok(f"Content gap: {len(gap_data.get('high_opportunity_angles', []))} high-opportunity angles")
                _info(f"Uniqueness score: {gap_data.get('uniqueness_score', 0)}/100")
                for a in gap_data.get("high_opportunity_angles", [])[:2]:
                    _info(f"Gap → {a['section_title'][:55]}")
        except Exception as e:
            _info(f"Gap analysis skipped: {e}")

    # ── Build enhanced prompt with gap data ────────────────────
    system = (
        "You are an SEO content strategist with deep expertise in Google E-E-A-T. "
        "Given competitor analysis, decide the optimal content strategy.\n\n"
        "CRITICAL — Every strategy must demonstrate Google E-E-A-T:\n"
        "- Include sections that prove first-hand Experience (testing, methodology)\n"
        "- Include sections that show Expertise (data, research citations)\n"
        "- Include sections that build Authoritativeness (expert quotes, credentials)\n"
        "- Include sections that earn Trust (transparent pricing, real numbers, pros/cons)\n\n"
        "The required_sections should be ordered: Problem → Solution → Evidence → Trust → FAQ.\n"
        "Commercial-intent articles MUST include a comparison table section."
    )

    # ── ACTIVE MEMORY FEEDBACK LOOP ──────────────────────────────
    _memory_block_for_strategy = ""
    _strategy_fingerprinter = get_prompt_fingerprinter()
    try:
        import memory as _mem_s
        _mem_s_data = _mem_s.load()
        _contam_s = get_contamination_scorer()
        _filtered_s = _contam_s.filter_memory_for_niche(_mem_s_data, keyword, max_entries=2, require_min_quality=60)
        _mem_filtered_s = {
            "articles_written": _filtered_s,
            "patterns": _mem_s_data.get("patterns", []),
            "clusters": _mem_s_data.get("clusters", []),
            "content_calendar": _mem_s_data.get("content_calendar", []),
            "authority_scores": _mem_s_data.get("authority_scores", {}),
        }
        _mi = _mem_s.build_prompt_injection(_mem_filtered_s, keyword)
        _sei = _mem_s.build_strategy_evolution_injection()
        _vmi = _mem_s.build_vector_memory_injection(keyword, _mem_filtered_s, top_k=2)
        if _mi or _sei or _vmi:
            _memory_block_for_strategy = "\n\n--- MEMORY-DERIVED INSIGHTS ---\n" + _mi + "\n" + _sei + "\n" + _vmi
        _strategy_fingerprinter.fingerprint_payload(
            system, user, [
                ("strategy_memory", _mi),
                ("strategy_evolution", _sei),
                ("strategy_vector", _vmi),
            ], model
        )
    except Exception as _mem_err_s:
        log.warning("[STRATEGY_MEMORY] Memory injection failed during strategy: %s", _mem_err_s)

    gap_section_prompt = ""
    if gap_data and gap_data.get("high_opportunity_angles"):
        gap_section_prompt = """
CRITICAL — COMPETITOR GAP SECTIONS:
The following H2 sections are NOT covered by top competitors.
They MUST be included for competitive differentiation:

""" + "\n".join(
    f"  - {a['section_title']} ({a['rationale']})"
    for a in gap_data["high_opportunity_angles"][:3]
) + """

These gap sections should be added to required_sections.
They give the article a structural advantage over competitors."""

    overcovered_note = ""
    if gap_data and gap_data.get("overcovered_topics"):
        overcovered_note = """
AVOID over-covered topics (every competitor has these):
""" + "\n".join(
    f"  - {t[:50]}" for t in gap_data["overcovered_topics"][:3]
) + """
If included, cover more briefly or from a unique angle."""

    user = f"""Keyword: "{keyword}"

Competitor data:
{json.dumps(competitor_data, indent=2)}

Articles already in memory: {articles_written}
{gap_section_prompt}
{overcovered_note}
{_memory_block_for_strategy}
Decide and return JSON:
{{
  "ideal_length":       0,
  "required_sections":  ["list of H2 headings to include — include at least 2 competitor gap sections"],
  "must_have_elements": ["table|FAQ|statistics|comparison|checklist|..."],
  "unique_angle":       "what makes this article stand out",
  "strategy":           "aggressive or strategic",
  "reasoning":          "one-sentence explanation"
}}"""

    result = call_json(system, user, model)
    if not isinstance(result, dict):
        log.warning("[STRATEGY] call_json returned %s, expected dict — using defaults", type(result).__name__)
        result = {
            "ideal_length": 1500,
            "required_sections": ["Introduction", "Key Features", "Pricing", "FAQ"],
            "must_have_elements": ["table", "FAQ"],
            "unique_angle": f"Comprehensive guide to {keyword}",
            "strategy": "strategic",
            "reasoning": "Fallback — LLM did not return valid JSON object",
        }

    # ── Post-process: inject any gap sections the LLM missed ──
    if gap_data and gap_data.get("high_opportunity_angles"):
        existing_sections = [s.lower().strip() for s in result.get("required_sections", [])]
        for angle in gap_data["high_opportunity_angles"]:
            title = angle["section_title"]
            # Check if LLM already included it
            already_has = False
            for es in existing_sections:
                words_in_title = set(w.lower() for w in title.split() if len(w) > 4)
                words_in_es = set(w.lower() for w in es.split() if len(w) > 4)
                if words_in_title and words_in_es:
                    overlap = words_in_title & words_in_es
                    if len(overlap) >= max(1, len(words_in_title) * 0.4):
                        already_has = True
                        break
            if not already_has:
                sections = result.get("required_sections", [])
                sections.append(title)
                result["required_sections"] = sections
                _info(f"Injected gap → {title[:55]}")

    # ── Store gap prompt + structured angles for write_article() ─
    if gap_data and gap_data.get("high_opportunity_angles"):
        result["_gap_prompt"] = build_mandatory_gap_prompt(gap_data)
        if gap_data.get("all_gap_angles"):
            result["_gap_angles"] = gap_data["all_gap_angles"]

    # ── Attach Ranking Brain predictions ──────────────────────
    if _HAS_RANKING_BRAIN:
        try:
            import memory as _mem
            _mem_data = _mem.load()
            brain_gap = analyze_competition_gap(keyword, competitor_data, result, _mem_data)
            result["_ranking_brain"] = brain_gap
            pred = brain_gap.get("current_prediction", {})
            _ok(f"Ranking Brain: Top-3 {pred.get('top_3_probability', '?')}% · Top-10 {pred.get('top_10_probability', '?')}% · Predicted position #{pred.get('predicted_position', '?')}")
            for s in brain_gap.get("suggestions", [])[:2]:
                _info(f"Suggestion ({s['impact']}): {s['detail'][:70]}")
        except Exception as e:
            _info(f"Ranking Brain skipped: {e}")

    # ── Forward competitor detail evidence for write_article() ──
    if "_competitors_detail" in competitor_data:
        result["_competitors_detail"] = competitor_data["_competitors_detail"]

    _ok(f"Strategy: {result.get('strategy', '?').upper()}")
    _ok(f"Target length: {result.get('ideal_length', '?')} words")
    _ok(f"Unique angle: {result.get('unique_angle', '?')}")
    _info(result.get("reasoning", ""))

    # ── Phase 3 Intelligence: feed authority & pattern data into strategy ──
    if _HAS_INTELLIGENCE:
        try:
            niche = _detect_niche(keyword)
            # Inject niche authority knowledge
            expertise = get_authority_graph().get_niche_expertise(niche)
            if expertise and expertise.authority_score > 0:
                result["_niche_authority"] = round(expertise.authority_score, 3)
                _info(f"Niche authority: {expertise.authority_score:.3f} ({expertise.total_articles} articles)")

            # Inject pattern-adapted strategy recommendations
            adaptation = get_pattern_tracker().adapt_strategy(niche)
            if adaptation.get("recommended_structure"):
                result["_adapted_structure"] = adaptation["recommended_structure"]
            if adaptation.get("patterns_to_avoid"):
                result["_patterns_to_avoid"] = adaptation["patterns_to_avoid"]
                _info(f"Avoid patterns: {', '.join(adaptation['patterns_to_avoid'])}")
        except Exception as _sie:
            log.warning("[INTELLIGENCE] Strategy enhancement failed for '%s': %s", keyword, _sie)

    return result


# ── Banned phrase filter (applied post-generation to ALL models) ──
_BANNED_PATTERNS = {
    "this section examines an important aspect of": "Here is what you need to know about {kw}",
    "understanding this dimension of": "To understand {kw} better",
    "requires looking past the obvious": "requires a closer look",
    "second-order effects that casual analysis misses": "deeper implications worth considering",
    "this is one of the areas where most": "this is an area where many",
    "guides fall short": "guides miss the mark",
    "the standard advice avoids these topics": "most coverage skips these details",
    "check official site": "[VERIFY: official link]",
    "in this article, i will provide": "This guide provides",
    "in this article, i will": "This guide will",
    "in this article, we will": "This guide will",
    "yoursite.com": "[SITE_URL]",
    "in the ever-evolving world": "In the current landscape of",
    "as a busy professional": "For professionals who need",
    "if you're looking for the best": "To find the best",
    "when it comes to finding the": "When choosing a",
    "are you looking for": "Looking for",
}

def _filter_banned_phrases(text: str, keyword: str = "") -> str:
    """Remove or replace banned template phrases with keyword-specific content."""
    import re
    lower = text.lower()
    kw = keyword or "this topic"
    for pattern, replacement in _BANNED_PATTERNS.items():
        if pattern in lower:
            repl = replacement.format(kw=kw)
            # Case-insensitive replace while preserving original case
            text = re.sub(re.escape(pattern), repl, text, flags=re.IGNORECASE)
    return text

# ──────────────────────────────────────────────────────────────
#  Module 3 — Article Writer (E-E-A-T Compliant)
# ──────────────────────────────────────────────────────────────

def _is_chrome_extensions_keyword(keyword: str) -> bool:
    kw = keyword.lower()
    chrome_signals = ["chrome extension", "chrome plugin", "browser extension",
                      "chrome addon", "chrome web store", "extensions for chrome"]
    if any(s in kw for s in chrome_signals):
        return True
    if "extension" in kw and any(b in kw for b in ["best", "top", "useful", "must-have", "essential"]):
        return True
    return False

_NICHE_MAP = {
    "tech": ["laptop", "software", "app", "gadget", "device", "browser", "extension", "plugin", "gaming", "computer", "phone", "smartphone", "tablet", "smartwatch", "headphone", "camera", "printer", "router", "monitor", "keyboard", "mouse"],
    "finance": ["credit card", "loan", "mortgage", "insurance", "investing", "saving", "budget", "bank", "crypto", "stock", "retirement", "tax"],
    "health": ["workout", "diet", "supplement", "vitamin", "exercise", "fitness", "nutrition", "wellness", "mental health", "sleep", "yoga", "meditation"],
    "marketing": ["seo", "content marketing", "social media", "email marketing", "ppc", "analytics", "conversion", "landing page", "copywriting", "branding"],
    "education": ["course", "learn", "tutorial", "guide", "certification", "degree", "study", "training", "scholarship", "online learning"],
    "lifestyle": ["travel", "food", "fashion", "home", "garden", "pet", "parenting", "wedding", "gift"],
    "business": ["startup", "saas", "small business", "entrepreneur", "freelance", "remote work", "productivity", "project management"],
}

def _detect_niche(keyword: str) -> str:
    """Infer the niche/category of a keyword for memory filtering."""
    kw = keyword.lower()
    for niche, signals in _NICHE_MAP.items():
        if any(s in kw for s in signals):
            return niche
    return "general"

def _detect_intent(keyword: str) -> str:
    kw = keyword.lower()
    # Local service keywords MUST be detected first
    local_service_keywords = [
        "repair", "remodel", "installation", "installer", "contractor",
        "plumber", "plumbing", "roofing", "roofer", "electrician", "hvac",
        "cleaning", "landscaping", "painter", "mover", "pest control",
        "appliance", "garage door", "basement", "shower", "near me",
    ]
    if any(w in kw for w in local_service_keywords):
        return "LOCAL_SERVICE"
    if any(w in kw for w in ["best", "top", "vs ", "comparison", "alternative", "review", "versus", "useful"]):
        return "COMMERCIAL"
    if any(w in kw for w in ["how to", "what is", "guide", "tutorial", "steps", "beginner", "learn"]):
        return "INFORMATIONAL"
    if any(w in kw for w in ["buy", "price", "download", "free", "cost", "cheap", "deal"]):
        return "TRANSACTIONAL"
    return "NAVIGATIONAL"

_EEAT_SYSTEM = """You are now operating as a ZERO-HALLUCINATION PRODUCTION CONTENT ENGINE.

Your task is NOT to merely generate SEO content.

Your task is to produce:
* fact-grounded
* structurally valid
* citation-safe
* EEAT-compliant
* publication-safe

content that can survive:
* Google Helpful Content systems
* manual editorial review
* schema validation
* AI detection scrutiny
* factual audits

You MUST follow ALL rules below with NO exceptions.

# PRODUCTION HARD-FAIL CONSTITUTION

## SECTION 1 — ABSOLUTE TRUTH ENFORCEMENT

NEVER fabricate:
* prices
* release dates
* benchmarks
* ratings
* statistics
* test results
* specifications
* availability
* compatibility claims
* review scores
* product rankings
* company statements
* expert opinions

If information is uncertain:
* use uncertainty language
* OR emit [VERIFY: field_name]
* OR remove the claim entirely

Allowed uncertainty phrases:
* "reportedly"
* "rumored"
* "not officially confirmed"
* "early leaks suggest"
* "public specifications are not finalized"

FORBIDDEN:
* "we tested"
* "hands-on testing"
* "our benchmarks"
* "after 2 weeks"
* "editor tested"
* "real-world testing"
* "lab testing"
* "we measured"
* "I personally tested"

UNLESS a verified evidence object exists.

If no evidence exists:
REMOVE the statement.

## SECTION 2 — CLAIM GROUNDING

Every factual claim MUST have one of:
* citation
* SERP consensus
* memory evidence
* verified source
* grounded retrieval evidence

If claim confidence < 0.75:
* soften the language
  OR
* emit [VERIFY]

BAD:
"The RTX 6090 costs $2,499."

GOOD:
"Early leaks suggest pricing could exceed $2,000, though Nvidia has not confirmed official pricing."

BAD:
"The RTX 6090 is 70% faster."

GOOD:
"Some leaked benchmarks indicate significant performance gains, but independent verification is not yet available."

## SECTION 3 — HTML VALIDATION

HTML MUST be production-safe.

STRICTLY ENFORCE:
* proper nesting
* closed tags
* valid attributes
* valid schema casing
* valid JSON escaping
* single H1 only
* FAQPage integrity
* valid table structure

FORBIDDEN:
* <div. (dot after div)
* acceptedanswer (wrong casing)
* duplicate IDs
* nested FAQ blocks
* raw markdown inside HTML
* placeholder URLs
* broken anchors

If HTML integrity fails:
the article MUST be rejected.

## SECTION 4 — AI DETECTION RESISTANCE

Avoid:
* repetitive sentence rhythm
* repetitive transitions
* generic filler
* robotic phrasing
* repetitive paragraph lengths
* template repetition
* repeated "however", "furthermore", "moreover"

Content MUST feel:
* editorial
* analytical
* nuanced
* evidence-aware
* human-paced

Use:
* varied sentence lengths
* contextual nuance
* realistic uncertainty
* selective detail
* natural transitions

DO NOT over-optimize keywords.

## SECTION 5 — CITATION ENFORCEMENT

Every:
* benchmark
* statistic
* comparison
* pricing claim
* release claim
* compatibility claim

MUST have:
* a source
  OR
* [VERIFY]

Never output naked numerical claims.

## SECTION 6 — AUTHOR SAFETY

DO NOT fabricate authors.

FORBIDDEN:
* fake years of experience
* fake testing history
* fake certifications
* fake editorial teams
* fake laboratories
* fake review methodology

If author metadata is unavailable:
use neutral attribution.

GOOD:
"Editorial content team"

BAD:
"Senior hardware analyst with 12 years of testing experience"

## SECTION 7 — MEMORY SAFETY

Memory is guidance.
Memory is NOT truth.

Before using memory:
* verify topical similarity
* verify niche similarity
* verify semantic relevance
* reject cross-domain contamination

Do NOT inject memory if:
* niche mismatch
* outdated information
* contradictory evidence
* low semantic similarity

## SECTION 8 — SERP INTELLIGENCE

You are competing against top-ranking pages.

You MUST:
* identify missing angles in SERP
* identify weak competitor sections
* identify repeated cliches
* avoid generic SEO filler
* produce differentiated insights

You MUST include:
* decision frameworks
* tradeoffs
* edge cases
* practical constraints
* buyer/user psychology
* hidden limitations
* real-world considerations

## SECTION 9 — HUMAN EDITORIAL STYLE

Write like:
* an experienced editor
* a careful analyst
* a domain-aware specialist

Do NOT write like:
* generic AI SEO content
* marketing spam
* keyword stuffing
* template-generated filler

Avoid:
* repetitive transitions
* robotic structure
* predictable GPT phrasing
* exaggerated enthusiasm
* fake authority tone

Use:
* concise reasoning
* natural variation
* nuanced language
* realistic uncertainty
* practical observations

## SECTION 10 — FINAL PRE-PUBLISH AUDIT

Before final output:
run FINAL_PUBLISH_AUDIT mentally.

Checklist:
* duplicate H1?
* malformed HTML?
* unresolved placeholders?
* hallucinated claims?
* unsupported numbers?
* broken schema?
* fake authority?
* AI repetition?
* invalid links?
* FAQ corruption?
* contradiction?
* keyword stuffing?

If ANY issue exists:
DO NOT output the article.
Fix it first.

## CORE PRINCIPLE

Truth > SEO.
Integrity > engagement.
Evidence > confidence.
Validation > speed.

You are NOT an AI writer.

You are a PRODUCTION CONTENT VALIDATION ENGINE.

## OUTPUT REQUIREMENTS — CRITICAL

Output ONLY valid production-ready HTML5.

NO markdown.
NO explanations.
NO chain-of-thought.
NO debug logs.
NO warnings.

* ONE H1 ONLY at the very top.
* NO Table of Contents block (formatter adds it).
* FAQ: minimum 8 for commercial, 5 for other intents.
* Include Article + FAQPage JSON-LD schemas.
* FAQPage schema must match ALL FAQ questions exactly.
* Include a quick-answer-box near the top.
* Minimum 3 external links with target=_blank rel=nofollow noopener."""

_E_EAT_USER_TEMPLATE = """Write a complete, publish-ready SEO article for: "{keyword}"

PRODUCTION HARD-FAIL NOTICE:
- If ANY claim is uncertain: emit [VERIFY: field] or remove it.
- If ANY HTML is malformed: the article will be BLOCKED.
- Output ONLY valid HTML5 — ZERO markdown, ZERO explanations.
- This article WILL be audited by automated systems.

STEP 1 — INTENT (classify silently before writing):
The dominant search intent is: {intent}
Use ONLY the matching template structure below.

STEP 2 — SPECIFICATIONS:
- Target length: {length} words (never less than 1500)
- Unique angle: {angle}
- Required H2 sections: {sections}
- Must include elements: {elements}
- Today's date: {today}

STEP 3 — CONTENT QUALITY (every article MUST include):
- Direct answer near top in a <div class="quick-answer-box">
- Comparison logic (table or prose comparing top options)
- Decision framework / how to choose section
- Buyer segmentation (who should use what)
- Tradeoffs and limitations for EACH option
- Realistic downsides per option
- Maintenance or hidden costs section
- Contextual recommendations
- FAQ (minimum 8 for commercial, 5 for other intents)
- Conclusion with actionable guidance

STEP 4 — ABSOLUTE TRUTH ENFORCEMENT:
1. NEVER fabricate experience: Do not claim "I tested" / "we tested" / "hands-on" / "our benchmarks" / "after testing" — these are banned unless real evidence exists.
2. NEVER fabricate prices, release dates, benchmarks, ratings, or specifications. If uncertain, use "reportedly", "rumored", "not officially confirmed", "early leaks suggest" OR emit [VERIFY: field].
3. For any numerical claim: if confidence < 0.75, soften language OR emit [VERIFY].
4. Every product mentioned must have:
   - Name + working hyperlink or [LINK: name] placeholder
   - Actual price or approximate range or [VERIFY: price] placeholder
   - 1 specific strength with concrete example
   - 1 honest weakness that is real, not marketing-approved

STEP 5 — OUTPUT FORMAT (HARD REQUIREMENT):
- Output ONLY valid production-ready HTML5. NO markdown, NO explanations, NO chain-of-thought.
- ONE H1 only at the very top — no second H1 anywhere
- NO Table of Contents block — formatter adds it automatically
- H2 and H3 headings for all sections
- Article JSON-LD schema with datePublished: {today}
- FAQPage JSON-LD schema if article contains FAQ section
- ItemList JSON-LD schema if article lists/ranks multiple tools
- Author bio block: 2 sentences, neutral attribution, no fake credentials, no "SEO Agent Pro"
- Meta description 150-160 chars: <!-- META: [description here] -->

STEP 6 — HARD-FAIL SELF-CHECK (run before outputting):
If ANY of these are true, FIX before output:
- Duplicate H1?
- Broken HTML or unclosed tags?
- Unresolved [LINK:] or [VERIFY:] placeholders?
- Hallucinated prices, specs, or benchmarks?
- Unsupported numerical claims without source or [VERIFY]?
- Fake authority language?
- AI repetition patterns?
- Contradictory claims?
- Invalid FAQ schema (FAQPage questions must match FAQ items)?
- Keyword stuffing?
- Missing citations on factual claims?
- Nested FAQ blocks or malformed tables?

[TEMPLATES BY INTENT]

For COMMERCIAL intent ("best X", "top X", "X vs Y"):
H1: Best [Keyword]: Complete Guide & Top Picks (2026)
H2: Introduction (150-200 words — state the problem, explain coverage)
H2: Quick Comparison Table (full HTML table with alternating row colors)
H2: #1 [Tool Name] — [One-line verdict with specific reason]
  H3: Pricing (exact numbers or [VERIFY] if uncertain)
  H3: What it does well (specific features + examples)
  H3: Where it falls short (honest, specific criticism)
[Repeat H2 block for each tool — minimum 3 tools]
H2: Who Should Use What
H2: How to Choose (step-by-step guide as <ol> with numbered steps)
H2: Hidden Costs Most Reviews Skip
H2: FAQ (minimum 8 questions with real answers — match FAQPage schema exactly)
H2: Final Verdict

For INFORMATIONAL intent ("how to", "what is", "guide"):
H1: How to [Keyword]: Complete Guide for 2026
H2: What Is [Topic] (only if needed)
H2: Step 1 — [Specific Actionable Title]
[Continue steps — each numbered, each actionable]
H2: Common Mistakes to Avoid
H2: Pro Tips
H2: FAQ
H2: Summary

For LOCAL_SERVICE intent ("repair in [city]", "remodel [city]", "installation [city]"):
H1: [Keyword] in Grand Rapids, MI | Same-Day Service
H2: Professional [Service] Services in Grand Rapids
  - Overview of the service, what it covers, why it matters locally
  - Include: licensed, insured, experienced technicians
  - Mention Grand Rapids landmarks: Medical Mile, Downtown GR, East Beltline
H2: Same-Day [Service] Near You — Grand Rapids
  - "near me" focused: searching for [keyword] near me in Grand Rapids?
  - Response times: 30-60 min across Grand Rapids neighborhoods
  - City-wide coverage: East Hills, Heritage Hill, Belknap Lookout, Midtown
H2: Emergency [Service] Services in Grand Rapids
  - 24/7 emergency availability, weekend/holiday service
  - Response time under 2 hours for urgent issues
H2: [Appliances/Products] We Service & Repair
  - Bulleted list of all items serviced (e.g., refrigerators, washers, dryers, ovens, dishwashers)
  - Include brands: Samsung, LG, Whirlpool, GE, Maytag, Bosch, KitchenAid, Frigidaire
H2: [Service] Cost & Pricing in Grand Rapids
  - HTML table with service call fee, typical repair costs, emergency surcharge
  - Free estimate callout
H2: Areas We Serve Around Grand Rapids
  - City neighborhoods: East Hills, Heritage Hill, Belknap Lookout, Midtown, Alger Heights, Garfield Park, Creston
  - Suburbs: Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Grandville, Jenison, Hudsonville
  - ZIP codes: 49503, 49504, 49505, 49506, 49507, 49508 and surrounding
H2: Why Grand Rapids Homeowners Choose Us
  - Same-day service, licensed technicians, upfront pricing, warranty on parts
H2: Frequently Asked Questions (minimum 6 questions — local-specific)
H2: Contact Us for [Service]
  - Phone number: <a href="tel:+16160000000">(616) 000-0000</a>
  - Call-to-action: Free estimate, same-day service, licensed technicians, emergency repair

CRITICAL RULES FOR LOCAL_SERVICE:
- NEVER use: "What Happened", "Why It Matters", "Analysts Disagree", "Bullish vs Bearish", "Historical Parallels"
- ALWAYS include: service area cities, pricing table, brands list, phone CTA, LocalBusiness schema
- Use Article schema AND LocalBusiness schema
- Tone: trustworthy, professional, local — NOT analytical or journalistic
- Include neighborhoods: East Hills, Heritage Hill, Belknap Lookout, Midtown, Alger Heights, Garfield Park
- Include local landmarks: Medical Mile, Van Andel Arena, East Beltline
- NEVER claim "I tested" or "hands-on" — use "Our technicians" or "We provide"
- Pricing should use "approximately" or "typically" for estimate ranges
- Emergency section is MANDATORY for: garage door repair, appliance repair, HVAC, plumbing
- Include highways I-196, US-131, M-6 for location context

For NAVIGATIONAL intent ("[Product] review", "[Product] tutorial"):
H1: [Product Name]: Comprehensive Review (2026)
H2: What Is [Product] and Who Built It
H2: Key Features (real descriptions, not marketing copy)
H2: How to Install / Get Started (numbered steps)
H2: Pricing (all tiers, exact numbers)
H2: Pros and Cons (specific, not generic)
H2: How It Compares to [Top 2 Alternatives]
H2: Is It Worth It? (direct answer)
H2: FAQ

For TRANSACTIONAL intent ("free X", "download X", "price of X"):
H1: [Keyword]: Best Free and Paid Options Compared (2026)
H2: Quick Price Comparison Table
H2: Best Free Option — [Name]
H2: Best Paid Option — [Name]
H2: What Features Are Worth Paying For
H2: How to Get Started (numbered steps)
H2: FAQ
H2: Final Verdict

For CHROME_EXTENSIONS articles ("best chrome extensions", "useful chrome extensions"):
H1: [N] Best Useful Chrome Extensions in 2026: Ranked by Category
<div class="quick-answer-box"> (2-3 sentence direct answer targeting Featured Snippet)
H2: Quick Overview: Best Chrome Extensions at a Glance
H2: [Category 1: Productivity & Focus]
  H3: [Extension Name] — Chrome Web Store: [X.X]★ ([N] ratings)
    - Pricing: [Free / $X/month]
    - Rating: [X.X/5] stars on Chrome Web Store
    - Key Features: [bullet list — 3 specific features]
    - Why it stands out: [one specific advantage]
    - Best For: [specific use case]
  [REPEAT for 2-3 extensions in this category — each with full details]
H2: [Category 2: Security & Privacy]
  [same structure — 2-3 extensions per category]
H2: [Category 3: Writing & Grammar]
  [same structure]
H2: [Category 4: Developer Tools]
  [same structure]
H2: [Category 5: Shopping & Deals]
  [same structure]
H2: Full Comparison Table: All 10 Chrome Extensions Side by Side
  [HTML <table> with columns: Extension, Category, Price, Rating, Users, Best For, Link]
  [Alternating row colors using tr:nth-child(even)]
H2: How to Choose the Right Chrome Extension (Step-by-Step)
  [Use <ol class="step-guide"> with numbered steps]
  [Include <div class="flowchart"> showing decision flow]
H2: Screenshots & User Interface Tour
  [SCREENSHOT: ExtensionName — brief caption describing what the screenshot shows]
H2: Frequently Asked Questions (minimum 8-10 questions)
  [Each question as <div class="faq-item"> with .faq-q and .faq-a]
  - What is the best Chrome extension for productivity?
  - Are Chrome extensions safe to install?
  - Do Chrome extensions slow down your browser?
  - What is Manifest V3 and how does it affect extensions?
  - How many Chrome extensions should I have installed?
  - Can I use Chrome extensions on mobile (Android/iOS)?
  - How do I install a Chrome extension from the Web Store?
  - What are the best free Chrome extensions in 2026?
  - Which Chrome extensions use the least memory?
  - How do I manage Chrome extension permissions?
H2: Hidden Downsides of Chrome Extensions (Honest Truth)
  [Use <div class="hidden-costs"> with warnings about performance, privacy, fake reviews]
H2: Final Verdict — Best Chrome Extensions for 2026
  [Use <div class="verdict"> with clear winner per use case]

IMAGE REQUIREMENTS (non-negotiable for chrome extensions articles):
- Each extension reviewed MUST have: [SCREENSHOT: ExtensionName]
- Chrome Web Store rating badge with star rating for each
- Category divider headers with emoji icons
- All images use: <img src="[IMAGE: description]" alt="[description]" loading="lazy" style="max-width:100%;border-radius:8px;margin:10px 0;">

SCHEMA REQUIREMENTS (include ALL three):
1. Article schema with @type: Article, headline, author, datePublished, dateModified, description
2. FAQPage schema with ALL FAQ questions and answers
3. ItemList schema with every tool listed (position, name, URL)

{competitor_gaps}"""


# ──────────────────────────────────────────────────────────────
#  Quality Gate — blocks template-bleed articles before output
# ──────────────────────────────────────────────────────────────

def validate_article_quality(article: str, keyword: str) -> dict:
    """
    Nuclear-enhanced quality gate.
    Hard-blocks low-quality articles before they reach output.
    Returns: {"pass": bool, "score": int, "failures": list, "warnings": list}
    """
    failures = []
    warnings = []
    score = 100

    from config import SETTINGS as _qcfg
    _qsite_url = _qcfg.get("site_url", "").lower().rstrip("/")

    # ── NUCLEAR SELF-CHECKLIST (25+ points) ──────────────────────

    # 1. BANNED PHRASES — template bleed
    banned_phrases = [
        "this section examines an important aspect",
        "understanding this dimension",
        "this is one of the areas where most",
        "check official site",
        "see details",
        "requires looking past the obvious",
        "separates a surface-level evaluation",
        "after two weeks of testing",
        "after four weeks of testing",
        "in today's world",
        "in this article, we will",
        "in the ever-evolving world",
        "as a busy professional",
        "if you're looking for the best",
        "when it comes to finding the",
        "in this article, i will",
        "are you looking for",
    ]
    if "yoursite.com" in _qsite_url:
        banned_phrases.append("yoursite.com")
    for phrase in banned_phrases:
        if phrase.lower() in article.lower():
            failures.append(f"BANNED_PHRASE: '{phrase[:50]}'")
            score -= 20

    # 2. DUPLICATE PARAGRAPHS
    paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', article, re.DOTALL)
    para_texts = [re.sub(r'<[^>]+>', '', p).strip().lower() for p in paragraphs]
    dupes = [t for t, c in Counter(para_texts).items() if c > 1 and len(t) > 60]
    if dupes:
        failures.append(f"DUPLICATE_PARAGRAPHS: {len(dupes)} repeated paragraphs detected")
        score -= 15 * len(dupes)

    # 3. SINGLE H1 CHECK
    h1_count = len(re.findall(r'<h1[^>]*>', article, re.IGNORECASE))
    if h1_count == 0:
        failures.append("MISSING_H1: No H1 heading found")
        score -= 20
    elif h1_count > 1:
        failures.append(f"MULTIPLE_H1: {h1_count} H1 tags found (only 1 allowed)")
        score -= 15

    # 4. NO TOC IN BODY (formatter adds it)
    if re.search(r'class=["\']toc["\']', article, re.IGNORECASE):
        failures.append("TOC_IN_BODY: Remove inline Table of Contents (formatter adds it)")
        score -= 10

    # 5. COMMERCIAL INTENT CHECKS
    commercial_signals = ['best ', 'top ', ' vs ', 'comparison', 'alternative']
    is_commercial = any(s in keyword.lower() for s in commercial_signals)
    if is_commercial:
        if '<table' not in article:
            warnings.append("MISSING_TABLE: Commercial article needs comparison table")
            score -= 10
        table_matches = re.findall(r'<td[^>]*>(.*?)</td>', article, re.DOTALL)
        vague_cells = [c for c in table_matches if c.strip().lower() in ['varies', 'see details', 'check site', 'n/a', '']]
        if len(vague_cells) > 2:
            failures.append(f"VAGUE_TABLE_CELLS: {len(vague_cells)} empty/vague cells in tables")
            score -= 10
        # Comparison table must have 5+ columns
        col_counts = [len(re.findall(r'<th[^>]*>', t, re.I)) for t in re.findall(r'<table[^>]*>.*?</table>', article, re.DOTALL | re.I)]
        for cc in col_counts:
            if cc < 5:
                warnings.append(f"TABLE_COLUMNS: Table has {cc} columns, minimum 5 required")
                score -= 5

    # 6. FAKE AUTHOR CHECK
    if 'seo agent pro' in article.lower():
        warnings.append("FAKE_AUTHOR: Replace 'SEO Agent Pro' with a real author name")
        score -= 5

    # 7. MINIMUM EXTERNAL LINKS (3+)
    ext_links = re.findall(r'<a\s[^>]*href="https?://', article, re.IGNORECASE)
    if len(ext_links) < 3:
        warnings.append(f"FEW_LINKS: Only {len(ext_links)} external links (need 3+)")
        score -= 10

    # 8. ALL EXTERNAL LINKS MUST HAVE rel=nofollow noopener target=_blank
    links_missing_rel = []
    for a_tag in re.findall(r'<a\s[^>]*href="https?://[^"]*"[^>]*>', article, re.IGNORECASE):
        if 'rel="nofollow noopener"' not in a_tag.lower():
            links_missing_rel.append(a_tag[:60])
        if 'target="_blank"' not in a_tag:
            links_missing_rel.append(a_tag[:60])
    if links_missing_rel:
        warnings.append(f"LINK_REL: {len(links_missing_rel)} links missing rel=nofollow noopener or target=_blank")
        score -= 5

    # 9. NO GENERIC CONS (RULE 10 — nuclear prompt)
    banned_cons = [
        "customer support could be better",
        "pricing could be more competitive",
        "learning curve",
        "can be slow at times",
        "could use improvement",
        "limited features",
        "needs more updates",
        "interface could be cleaner",
        "no mobile app",
        "limited integrations",
    ]
    article_lower = article.lower()
    generic_cons_found = [c for c in banned_cons if c in article_lower]
    if generic_cons_found:
        warnings.append(f"GENERIC_CONS: {len(generic_cons_found)} generic/non-specific cons found: {', '.join(generic_cons_found[:3])}")
        score -= 5 * len(generic_cons_found)

    # 10. FAQ CHECK — FAQPage schema questions must match actual FAQ items
    # Extract names only from FAQPage schema block (avoid picking up names from Article/Mentions schemas)
    art = article
    faqpage_block = ""
    _fp_start = art.find('"@type": "FAQPage"') if '"@type": "FAQPage"' in art else art.find('"@type":"FAQPage"')
    if _fp_start >= 0:
        _closing = art.find('}', _fp_start)
        if _closing >= 0:
            faqpage_block = art[_fp_start:_closing+1]
    faq_schema_qs = re.findall(r'"name":\s*"([^"]+)"', faqpage_block) if faqpage_block else []
    faq_items_text = re.findall(r'class="faq-q"[^>]*>(.*?)</div>', article, re.DOTALL)
    faq_items_clean = [re.sub(r'<[^>]+>', '', q).strip() for q in faq_items_text]
    if faq_schema_qs and faq_items_clean:
        schema_qs_found = []
        for s in faq_schema_qs:
            matched = any(s.lower() in fq.lower() or fq.lower() in s.lower() for fq in faq_items_clean)
            if matched:
                schema_qs_found.append(s)
        unmatched = len(faq_schema_qs) - len(schema_qs_found)
        if unmatched > 2:
            warnings.append(f"FAQ_MISMATCH: {unmatched} FAQPage questions don't match actual FAQ items")
            score -= 10
        # FAQ count check — commercial needs 8, others need 5
        faq_minimum = 8 if is_commercial else 5
        if len(faq_items_clean) < faq_minimum:
            warnings.append(f"FAQ_COUNT: Only {len(faq_items_clean)} FAQ items found (commercial needs {faq_minimum})")
            score -= (faq_minimum - len(faq_items_clean)) * 3
    elif faq_items_clean and len(faq_items_clean) < (8 if is_commercial else 5):
        faq_minimum = 8 if is_commercial else 5
        warnings.append(f"FAQ_COUNT: Only {len(faq_items_clean)} FAQ items found (commercial needs {faq_minimum})")
        score -= (faq_minimum - len(faq_items_clean)) * 3

    # 11. SCHEMA PRESENCE CHECK
    has_article_schema = '"@type": "Article"' in article or '"@type":"Article"' in article
    if not has_article_schema:
        warnings.append("MISSING_SCHEMA: No Article JSON-LD schema found")
        score -= 10

    # 12. QUICK ANSWER BOX CHECK (featured snippet target)
    if 'quick-answer-box' not in article_lower:
        warnings.append("MISSING_QA_BOX: No .quick-answer-box found for featured snippet targeting")
        score -= 5

    # 13. DATES IN SCHEMA
    today = _mod_dt.now()
    today_str = today.strftime("%Y-%m-%d")
    yesterday_str = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    date_matches = re.findall(r'"datePublished":\s*"(\d{4}-\d{2}-\d{2})"', article)
    for d in date_matches:
        if d not in (today_str, yesterday_str):
            warnings.append(f"STALE_DATE: datePublished is '{d}', should be '{today_str}'")
            score -= 5

    # 14. THIN SECTIONS
    h2_sections = re.findall(r'<h2[^>]*>.*?</h2>(.*?)(?=<h2|</body>|$)', article, re.DOTALL)
    thin_sections = []
    for i, section in enumerate(h2_sections):
        text = re.sub(r'<[^>]+>', '', section).strip()
        word_count = len(text.split())
        has_data_table = '<table>' in section and word_count >= 40
        if word_count < 80 and not has_data_table:
            thin_sections.append(f"Section {i+1}: only {word_count} words")
    if thin_sections:
        failures.append(f"THIN_SECTIONS: {'; '.join(thin_sections[:3])}")
        score -= 10 * len(thin_sections)

    # 15. TOTAL WORD COUNT
    total_words = len(article.split())
    if total_words < 1500:
        failures.append(f"TOO_SHORT: Only {total_words} words (minimum 1500)")
        score -= 20
    elif total_words < 1800:
        warnings.append(f"WORD_COUNT: {total_words} words (target 1800+)")
        score -= 5

    # 16. Chrome Extensions-specific quality checks
    is_chrome_ext = _is_chrome_extensions_keyword(keyword)
    if is_chrome_ext:
        cws_ratings = re.findall(r'Chrome Web Store', article)
        if len(cws_ratings) < 3:
            warnings.append("EXT_WEAK_CWS: Include Chrome Web Store ratings for most extensions")
            score -= 10

        ext_categories = re.findall(r'Productivity|Security|Privacy|Writing|Grammar|Developer|Shopping|Deals', article)
        if len(ext_categories) < 4:
            warnings.append(f"EXT_FEW_CATEGORIES: Only {len(ext_categories)} categories (need 5)")
            score -= 10

        ext_mentions = re.findall(r'<h3[^>]*>.*?</h3>', article, re.DOTALL)
        if len(ext_mentions) < 8:
            warnings.append(f"EXT_TOO_FEW: Only {len(ext_mentions)} extensions reviewed (need 10)")
            score -= 15

        screenshots = re.findall(r'\[SCREENSHOT:|<img[^>]*class="ext-screenshot"', article)
        if not screenshots:
            warnings.append("EXT_NO_SCREENSHOTS: Include [SCREENSHOT: Name] placeholders for extensions")
            score -= 5

        has_itemlist = '"@type": "ItemList"' in article or '"@type":"ItemList"' in article
        if not has_itemlist:
            warnings.append("EXT_MISSING_ITEMLIST: Chrome Extensions article needs ItemList schema")
            score -= 10

    score = max(0, score)
    passed = score >= 40

    return {
        "pass": passed,
        "score": score,
        "failures": failures,
        "warnings": warnings,
        "verdict": "✅ PUBLISH READY" if passed else "❌ REWRITE REQUIRED"
    }


class PublishBlocked(Exception):
    """Raised when hard-fail audit blocks an article from publishing."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"PUBLISH_BLOCKED: {reason}")


def hard_fail_audit(article: str, keyword: str):
    """Final pre-publish audit. Raises PublishBlocked if article fails. Returns None if pass."""
    # 1. Duplicate H1
    h1s = re.findall(r'<h1[^>]*>', article, re.IGNORECASE)
    if len(h1s) > 1:
        raise PublishBlocked("Duplicate H1")
    if len(h1s) == 0:
        raise PublishBlocked("Missing H1")

    # 2. Broken HTML — auto-close unclosed tags
    import collections as _col
    tag_whitelist = {"br", "hr", "img", "input", "meta", "link", "source", "wbr", "path"}
    tag_counts = _col.Counter()
    for t in re.findall(r'</?(\w+)[^>]*>', article):
        if t not in tag_whitelist:
            tag_counts[t] += 1
    for t in ['div', 'p', 'h1', 'h2', 'h3', 'h4', 'section', 'table', 'tr', 'td', 'th', 'ul', 'ol', 'li']:
        opens = sum(1 for m in re.finditer(r'<' + t + r'[\s>]', article, re.IGNORECASE))
        closes = sum(1 for m in re.finditer(r'</' + t + r'>', article, re.IGNORECASE))
        diff = opens - closes
        if diff > 0:
            article += '\n' + '\n'.join(f'</{t}>' for _ in range(diff))
        elif diff < 0:
            # Extra closing tags — warn only
            import logging
            logging.getLogger("modules.hard_fail").warning(
                "[HARD_FAIL] Extra </%s> tags: %d more closes than opens", t, -diff
            )

    # 3. Invalid JSON-LD
    jsonld_blocks = re.findall(r'<script[^>]*type="?application/ld\+json"?[^>]*>(.*?)</script>', article, re.DOTALL | re.IGNORECASE)
    for block in jsonld_blocks:
        try:
            json.loads(block.strip())
        except json.JSONDecodeError as e:
            raise PublishBlocked(f"Invalid JSON-LD — {e}")

    # 4. FAQ schema mismatch
    faqpage_block = ""
    for fp in ['"@type": "FAQPage"', '"@type":"FAQPage"']:
        idx = article.find(fp)
        if idx >= 0:
            closing = article.find('}', idx)
            if closing >= 0:
                faqpage_block = article[idx:closing+1]
                break
    if faqpage_block:
        schema_qs = re.findall(r'"name":\s*"([^"]+)"', faqpage_block)
        faq_items = re.findall(r'class="faq-q"[^>]*>(.*?)</div>', article, re.DOTALL)
        faq_clean = [re.sub(r'<[^>]+>', '', q).strip() for q in faq_items]
        if schema_qs and faq_clean:
            unmatched = sum(1 for s in schema_qs if not any(s.lower() in fq.lower() or fq.lower() in s.lower() for fq in faq_clean))
            if unmatched > 4:
                raise PublishBlocked(f"{unmatched} FAQPage questions don't match FAQ items")

    # 5. Unsupported numerical claims
    price_pattern = re.findall(r'\$\d+(?:,\d{3})*(?:\.\d{2})?', article)
    unsupported_prices = []
    uncertainty_words = ['reportedly', 'rumored', 'not officially', 'early leaks', 'approximate', 'approximately', 'around', 'about', 'estimated', 'typically', 'may', 'can', 'varies', '[verify]']
    for price in price_pattern[:10]:
        idx = article.index(price)
        ctx_before = article[max(0, idx-200):idx]
        if not any(w in ctx_before.lower() for w in uncertainty_words):
            unsupported_prices.append(price)
    if len(unsupported_prices) > 3:
        raise PublishBlocked(f"{len(unsupported_prices)} unsupported numerical claims without uncertainty wording")

    # 6. Fake authority language
    fake_authority = re.findall(r'\b(we tested|hands-on testing|our benchmarks|after \d+ weeks? of|editor tested|real-world testing|lab testing|we measured|I personally tested)\b', article, re.IGNORECASE)
    if fake_authority:
        raise PublishBlocked(f"Fake authority language found: {fake_authority[0][:50]}")

    # 7. Placeholder leakage
    link_placeholders = re.findall(r'\[LINK:\s*[^\]]+\]', article)
    verify_placeholders = re.findall(r'\[VERIFY[^]]*\]', article)
    if link_placeholders or verify_placeholders:
        raise PublishBlocked(f"{len(link_placeholders)+len(verify_placeholders)} unresolved placeholders ({len(link_placeholders)} LINK, {len(verify_placeholders)} VERIFY)")

    # 8. Contradictory claims
    contradictions = re.findall(r'(?i)(however|but|on the other hand).{0,30}(?:but|however)', article)
    if len(contradictions) > 3:
        raise PublishBlocked(f"{len(contradictions)} contradictory patterns detected")

    # 9. Missing Article schema
    if '"@type": "Article"' not in article and '"@type":"Article"' not in article:
        raise PublishBlocked("Missing Article JSON-LD schema")

    # 10. Malformed tables
    for tbl in re.findall(r'<table[^>]*>.*?</table>', article, re.DOTALL | re.IGNORECASE):
        tr_o = len(re.findall(r'<tr[\s>]', tbl, re.IGNORECASE))
        tr_c = len(re.findall(r'</tr>', tbl, re.IGNORECASE))
        if tr_o != tr_c and tr_o > 0:
            raise PublishBlocked(f"Malformed table — {tr_o} <tr> vs {tr_c} </tr>")

    # 11. Keyword stuffing
    kw_lower = keyword.lower()
    kw_count = article.lower().count(kw_lower)
    total_words = len(article.split())
    if total_words > 0 and (kw_count / total_words) > 0.05:
        raise PublishBlocked(f"Keyword stuffing — '{keyword}' appears {kw_count} times ({kw_count/total_words*100:.1f}% of words)")


def _ensure_html_template(article: str, keyword: str, intent: str) -> str:
    """Wrap raw article body in full HTML template with required schemas."""
    # Normalize raw model output before template wrapping
    from post_processor import _normalize_html
    article = _normalize_html(article)
    if article.startswith("<!DOCTYPE html>") or article.startswith("<html"):
        return article
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    kw_slug = re.sub(r"[^a-z0-9-]+", "-", keyword.lower()).strip("-")[:60]
    site_url = "https://yoursite.com"

    # Extract first H1 for page title
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", article, re.IGNORECASE | re.DOTALL)
    page_title = h1_match.group(1).strip() if h1_match else f"{keyword.title()} | Service Guide"
    page_title_clean = re.sub(r"<[^>]+>", "", page_title)

    # Build Article schema
    article_schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": page_title_clean,
        "description": f"Professional {keyword} services in Grand Rapids, MI.",
        "author": {"@type": "Person", "name": "James Whitfield"},
        "publisher": {"@type": "Organization", "name": "James Whitfield"},
        "datePublished": today,
        "dateModified": today,
    }, ensure_ascii=False)

    # Build LocalBusiness schema for local_service intent — enriched
    local_biz_schema = ""
    faq_schema_block = ""
    if intent == "LOCAL_SERVICE":
        local_biz_schema = build_enriched_local_business_schema(keyword)
        faq_schema_block = build_local_faq_schema(keyword)

    template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{page_title_clean}</title>
    <meta name="description" content="Professional {keyword} in Grand Rapids, MI. Same-day service, licensed technicians, free estimates. Serving all of West Michigan.">
    <link rel="canonical" href="{site_url}/{kw_slug}">
    <meta name="geo.region" content="US-MI">
    <meta name="geo.placename" content="Grand Rapids">
    <meta name="geo.position" content="42.9634;-85.6681">
    <meta name="ICBM" content="42.9634, -85.6681">
    <script type="application/ld+json">{article_schema}</script>
    {f'<script type="application/ld+json">{local_biz_schema}</script>' if local_biz_schema else ''}
    {f'<script type="application/ld+json">{faq_schema_block}</script>' if faq_schema_block else ''}
</head>
<body itemscope itemtype="https://schema.org/Article">
<meta itemprop="headline" content="{page_title_clean}">
<meta itemprop="datePublished" content="{today}">
<meta itemprop="dateModified" content="{today}">
<meta itemprop="author" itemscope itemtype="https://schema.org/Person">
<meta itemprop="name" content="James Whitfield">

{article}

</body>
</html>"""
    return template


def write_article(keyword: str, strategy: dict, model: str) -> str:
    from datetime import datetime as _dt
    length = strategy.get("ideal_length", 1500)
    sections = strategy.get("required_sections", [])
    angle = strategy.get("unique_angle", "")
    elements = strategy.get("must_have_elements", [])
    gap_prompt = strategy.get("_gap_prompt", "")
    intent = _detect_intent(keyword)

    # Emit pipeline start event
    try:
        from event_bus import emit as _bus_emit
        _bus_emit("pipeline.started", {"keyword": keyword, "model": model, "intent": intent})
    except ImportError:
        pass

    _step(f"Writing Article  —  {length} words  [Intent: {intent}]")

    # Competitor gap requirements
    gap_block = ""
    if gap_prompt:
        gap_block = gap_prompt
    else:
        gap_block = """
DIFFERENTIATION REQUIREMENTS:
Include at least 2 of these insight sections competitors typically miss:
1. "Hidden Costs" or "What You Actually Pay" — pricing traps, unexpected fees
2. "Real-World Frustrations" — genuine user pain points, not marketing fluff
3. "Migration Reality" or "Switching Costs" — what it really takes to change
4. "Performance Limits" — where the tool breaks down under real conditions"""

    today_str = _dt.now().strftime("%B %d, %Y")
    sections_str = ', '.join(sections) if sections else 'chosen by intent template'
    elements_str = ', '.join(elements) if elements else 'decided by intent template'

    # ── Coverage validation — pre-generation outline audit ────
    if _HAS_COVERAGE_VALIDATOR and strategy.get("_coverage_validated") is None:
        try:
            cov_result = validate_outline_coverage(strategy, keyword, intent)
            if not cov_result["passed"]:
                log.warning(
                    "[COVERAGE] %d issues for '%s' — auto-fixing strategy",
                    len([i for i in cov_result["issues"] if i["severity"] == "high"]),
                    keyword,
                )
                for iss in cov_result["issues"]:
                    _info(f"Coverage gap [{iss['severity']}]: {iss['message']}")
                strategy = auto_fix_strategy(strategy, cov_result, keyword, intent)
                strategy["_coverage_validated"] = True
                # Re-extract after fix
                sections = strategy.get("required_sections", [])
                elements = strategy.get("must_have_elements", [])
                length = strategy.get("ideal_length", length)
                sections_str = ', '.join(sections) if sections else 'chosen by intent template'
                elements_str = ', '.join(elements) if elements else 'decided by intent template'
                _ok(f"Strategy auto-fixed: {len(sections)} sections, {length} words")
        except Exception as _cov_err:
            log.warning("[COVERAGE] Validation failed: %s", _cov_err)
    # ───────────────────────────────────────────────────────────

    # Detect if this is a Chrome Extensions article
    is_chrome_ext = _is_chrome_extensions_keyword(keyword)
    chrome_ext_flag = ""

    if is_chrome_ext:
        intent = "COMMERCIAL"  # force commercial template for chrome extensions
        chrome_ext_flag = """
═══════════════════════════════════════════════════════════════
CHROME EXTENSIONS ARTICLE — SPECIAL REQUIREMENTS
═══════════════════════════════════════════════════════════════
You are writing about Chrome Extensions. Follow these rules EXACTLY:

STRUCTURE:
1. Start with a Featured Snippet intro: directly answer "The best useful Chrome extensions in 2026 are..."
2. Organize into EXACTLY 5 categories with 2 extensions each = 10 total:
   - Category 1: Productivity & Focus (e.g., Todoist, Forest, StayFocusd)
   - Category 2: Security & Privacy (e.g., uBlock Origin, Bitwarden, Ghostery)
   - Category 3: Writing & Grammar (e.g., Grammarly, LanguageTool, ProWritingAid)
   - Category 4: Developer Tools (e.g., React DevTools, JSON Viewer, Lighthouse)
   - Category 5: Shopping & Deals (e.g., Honey, CamelCamelCamel, Rakuten)
3. Full comparison table with ALL 10 extensions
4. FAQ with minimum 8 questions (use the template questions)
5. Step-by-step guide on how to choose/install extensions

PER EXTENSION — MUST INCLUDE:
- Name linked to Chrome Web Store: <a href="[CWS URL]" target="_blank">Name</a>
- Exact Chrome Web Store rating: [X.X]★ ([N,NNN] ratings) — write [VERIFY: CWS rating] if unknown
- Pricing: Free / Freemium / $X/month
- Key Features: 3 bullet points
- Best For: one specific use case
- Honest weakness: one real con
- Image: [SCREENSHOT: ExtensionName]

REQUIRED SECTIONS (in order):
H2: Quick Overview: Best Chrome Extensions at a Glance
[Category sections with 2 extensions each]
H2: Full Comparison Table: All 10 Chrome Extensions
H2: How to Choose the Right Chrome Extension
H2: Screenshots & Features Tour
H2: Frequently Asked Questions (8-10 questions)
H2: Hidden Downsides of Chrome Extensions
H2: Final Verdict

IMAGES: Add [SCREENSHOT: ExtensionName] after each extension name.
═══════════════════════════════════════════════════════════════
"""

    # ── ACTIVE MEMORY FEEDBACK LOOP ───────────────────────────
    # Inject learned patterns from past successful articles
    # Memory is guidance, not truth — filtered by niche alignment
    memory_injection = ""
    strategy_evolution_injection = ""
    vector_memory_injection = ""
    mem_filtered = {}
    _injection_fps = []
    _fingerprinter = get_prompt_fingerprinter()
    try:
        import memory as _mem_module
        current_niche = _detect_niche(keyword)
        mem = _mem_module.load()
        # Use contamination scorer for niche-aligned memory filtering
        _contam = get_contamination_scorer()
        _filtered_entries = _contam.filter_memory_for_niche(mem, keyword, max_entries=5, require_min_quality=60)
        mem_filtered = {
            "articles_written": _filtered_entries,
            "patterns": mem.get("patterns", []),
            "clusters": mem.get("clusters", []),
            "content_calendar": mem.get("content_calendar", []),
            "authority_scores": mem.get("authority_scores", {}),
        }
        memory_injection = _mem_module.build_prompt_injection(mem_filtered, keyword)
        strategy_evolution_injection = _mem_module.build_strategy_evolution_injection()
        vector_memory_injection = _mem_module.build_vector_memory_injection(keyword, mem_filtered)
        # Track fingerprints for injection verification
        _injection_fps.append(("memory", memory_injection))
        _injection_fps.append(("strategy_evolution", strategy_evolution_injection))
        _injection_fps.append(("vector_memory", vector_memory_injection))
    except Exception as _mem_err:
        log.warning("[MEMORY] Memory injection failed: %s", _mem_err)
    # ────────────────────────────────────────────────────────────

    # ── Evidence pack — pre-generation evidence injection ─────
    evidence_block = ""
    if _HAS_EVIDENCE_PACK and strategy.get("_competitors_detail"):
        try:
            comp_detail = strategy["_competitors_detail"]
            evidence_data = {
                "products": comp_detail.get("entities", [])[:15],
                "prices": [],
                "percentages": [],
                "specs": [],
                "ratings": [],
                "years": [],
                "claims": [],
                "domain_count": len(comp_detail.get("top_urls", [])),
                "competitors_analyzed": len(comp_detail.get("top_urls", [])),
                "competitor_titles": comp_detail.get("competitor_titles", []),
                "common_headings": comp_detail.get("common_headings", []),
                "keyword": keyword,
                "generated_at": today_str,
            }
            evidence_block = _evidence_pack.build_prompt_block(evidence_data, keyword)
            _info(f"Evidence pack built: {len(comp_detail.get('entities', []))} entities from SERP")
        except Exception as _ev_err:
            log.warning("[EVIDENCE_PACK] Build failed: %s", _ev_err)

    # ── Temporal grounding injection ──────────────────────────
    temporal_block = ""
    if _HAS_TEMPORAL_GROUNDING:
        try:
            current_niche = _detect_niche(keyword)
            temporal_block = build_temporal_constraint_block(
                keyword=keyword,
                niche=current_niche,
            )
        except Exception as _t_err:
            log.warning("[TEMPORAL] Grounding injection failed: %s", _t_err)
    # ──────────────────────────────────────────────────────────

    all_injections = gap_block + chrome_ext_flag
    if evidence_block:
        all_injections += "\n" + evidence_block
    if temporal_block:
        all_injections += "\n" + temporal_block
    if memory_injection:
        all_injections += "\n" + memory_injection
    if strategy_evolution_injection:
        all_injections += "\n" + strategy_evolution_injection
    if vector_memory_injection:
        all_injections += "\n" + vector_memory_injection

    user = _E_EAT_USER_TEMPLATE.format(
        keyword=keyword,
        intent=intent,
        length=length,
        angle=angle or f"Comprehensive {intent.lower()} guide based on real data",
        sections=sections_str,
        elements=elements_str,
        today=today_str,
        competitor_gaps=all_injections,
    )

    # Fingerprint the intended payload before LLM call
    _intended_fp = _fingerprinter.fingerprint_payload(
        _EEAT_SYSTEM, user, _injection_fps, model
    )

    import importlib
    try:
        cv = importlib.import_module("claim_verifier")
    except Exception as _cv_err:
        log.warning("[CLAIM_VERIFIER] Import failed — claim verification disabled: %s", _cv_err)
        cv = None

    print(c("dim", "  " + "─" * 56))
    article = call(_EEAT_SYSTEM, user, model, stream=True)
    # Ensure article has proper HTML template (non-local models output raw body)
    article = _ensure_html_template(article, keyword, intent)
    # Verify payload integrity after LLM call
    _actual_payload = (_EEAT_SYSTEM, user)
    _verification = _fingerprinter.verify_payload(_intended_fp, _actual_payload)
    if not _verification["match"]:
        log.warning("[PROMPT_TRUTH] Payload mismatch detected! intended=%s actual=%s",
                     _verification["intended_hash"][:12], _verification["actual_hash"][:12])
    # Check for malformed/partial output
    _failure_monitor = get_failure_monitor()
    _is_valid, _reason = _failure_monitor.check_partial_output(article)
    if not _is_valid:
        log.warning("[OUTPUT_QUARANTINE] %s — quarantining output for '%s'", _reason, keyword)
        _failure_monitor.quarantine_output(article, _reason, {"keyword": keyword, "model": model})
    # Run claim audit
    _claim_auditor = get_claim_auditor()
    _claim_report = _claim_auditor.audit_article(article)
    if _claim_report["issues"]:
        for _ci in _claim_report["issues"]:
            if _ci["severity"] == "high":
                log.warning("[CLAIM_AUDIT] %s: %d issues for '%s'", _ci["type"], _ci["count"], keyword)
    article = _filter_banned_phrases(article, keyword)
    article = fix_article(article, keyword)

    # ── Hyper-local SEO enhancement for LOCAL_SERVICE intents ──
    article = enhance_article(article, keyword, intent)

    # ── Superlative suppression — downgrade unsupported absolute claims ──
    if _HAS_SUPERLATIVE_SUPPRESSOR:
        try:
            _sup_report = scan_superlatives(article)
            if _sup_report["unsupported"] > 0:
                log.info(
                    "[SUPERLATIVE] %d unsupported superlatives in '%s' — suppressing",
                    _sup_report["unsupported"], keyword,
                )
                article = suppress_superlatives(article, keyword)
                _info(f"Superlatives suppressed: {_sup_report['unsupported']} downgraded")
        except Exception as _sup_err:
            log.warning("[SUPERLATIVE] Suppression failed: %s", _sup_err)

    # ── Temporal compliance scan ──────────────────────────────
    if _HAS_TEMPORAL_GROUNDING:
        try:
            _temp_violations = validate_temporal_compliance(article, keyword)
            if _temp_violations:
                _high_temp = [v for v in _temp_violations if v["severity"] == "high"]
                if _high_temp:
                    log.warning(
                        "[TEMPORAL] %d high-severity temporal violations in '%s'",
                        len(_high_temp), keyword,
                    )
                    for _tv in _high_temp:
                        _info(f"Outdated reference: {_tv['item']} [{_tv['category']}]")
        except Exception as _temp_err:
            log.warning("[TEMPORAL] Compliance scan failed: %s", _temp_err)

    # Hard-fail audit — blocks publishing if critical issues found
    # Save original article snapshot before repair loop
    _original_article_before_repair = article
    _max_repairs = 2
    _repair_attempt = 0
    while _repair_attempt <= _max_repairs:
        try:
            hard_fail_audit(article, keyword)
            # Enterprise layer — contradiction, entropy, claim validation
            try:
                from enterprise_guardian import enterprise_hard_fail
                article = enterprise_hard_fail(article, keyword)
            except ImportError:
                pass
            break
        except PublishBlocked as _pb:
            _repair_attempt += 1
            if _repair_attempt > _max_repairs:
                log.error("[HARD_FAIL] %s for '%s' after %d repair attempts", _pb.reason, keyword, _max_repairs)
                print(c("red", f"  🛑 PUBLISH_BLOCKED (after {_max_repairs} repairs): {_pb.reason}"))
                _failure_monitor = get_failure_monitor()
                _failure_monitor.quarantine_output(article, _pb.reason, {"keyword": keyword, "repair_attempts": _repair_attempt})
                # Fall back to original article before repair
                if _original_article_before_repair and len(_original_article_before_repair) > 500:
                    article = _original_article_before_repair
                    log.info("[HARD_FAIL] Falling back to original article before repair attempts")
                    break
                # Emit pipeline blocked event before re-raising
                try:
                    from event_bus import emit as _bus_emit
                    _bus_emit("pipeline.blocked", {
                        "keyword": keyword,
                        "reason": _pb.reason,
                        "repair_attempts": _repair_attempt,
                    })
                except ImportError:
                    pass
                raise
            log.warning("[REPAIR] Attempt %d/%d for '%s': %s", _repair_attempt, _max_repairs, keyword, _pb.reason)
            print(c("yellow", f"  🔧 Repair attempt {_repair_attempt}/{_max_repairs}: {_pb.reason}"))
            # Classify failure and build repair prompt
            _reason_lower = _pb.reason.lower()
            if 'fake authority' in _reason_lower:
                _repair_prompt = f"Remove the following unsupported authority language from the article: '{_pb.reason}'. Replace with neutral phrasing that does not claim personal testing or hands-on experience."
            elif 'duplicate h1' in _reason_lower:
                _repair_prompt = f"The article has multiple H1 headings. Merge all content under a single H1. Remove extra H1 tags or convert them to H2."
            elif 'missing h1' in _reason_lower:
                _repair_prompt = f"The article is missing an H1 heading. Add a single H1 at the top of the article body using the primary keyword '{keyword}'."
            elif 'unclosed' in _reason_lower or 'malformed' in _reason_lower:
                _repair_prompt = f"Fix HTML structure: {_pb.reason}. Ensure all HTML tags are properly opened and closed."
            elif 'unsupported numerical' in _reason_lower:
                _repair_prompt = f"Add uncertainty qualifiers (like 'approximately', 'reportedly', 'typically') before the following unsupported prices or numbers: {_pb.reason}. Do not remove the data, just qualify it."
            elif 'keyword stuffing' in _reason_lower:
                _repair_prompt = f"The keyword '{keyword}' is overused. Reduce its frequency by replacing some occurrences with synonyms or pronouns."
            elif 'unresolved placeholder' in _reason_lower:
                _repair_prompt = f"Replace ALL placeholders ({_pb.reason}) with real content. Remove [LINK:...] and [VERIFY...] tags. Either supply actual information or remove the placeholder entirely."
            elif 'contradictory' in _reason_lower:
                _repair_prompt = f"Remove contradictory language: {_pb.reason}. Ensure the article's claims are consistent throughout."
            else:
                _repair_prompt = f"Fix the following issue: {_pb.reason}. Revise the article to resolve this specific problem."
            # Call LLM with repair instruction
            _repair_system = "You are an SEO article repair specialist. Fix the specific issue described below. Return ONLY the repaired article HTML with no additional commentary."
            _repair_user = f"ORIGINAL ARTICLE:\n\n{article}\n\nISSUE TO FIX:\n{_repair_prompt}\n\nReturn the repaired article HTML."
            try:
                article = call(_repair_system, _repair_user, model, stream=False)
            except Exception as _repair_err:
                log.error("[REPAIR] LLM repair call failed: %s", _repair_err)
                print(c("red", f"  ✗ Repair LLM call failed: {_repair_err}"))
                raise
            # Re-run post-processing on repaired article
            article = _filter_banned_phrases(article, keyword)
            article = fix_article(article, keyword)
    # End of repair loop

    # Multi-model consensus engine
    try:
        from generation_consensus_engine import run_consensus
        article, _creport = run_consensus(article, keyword)
        if _creport.get("critical_issues"):
            log.warning("[CONSENSUS] %d critical issues remain for '%s'",
                         len(_creport["critical_issues"]), keyword)
        if _creport.get("claims_rejected", 0) > 0:
            _info(f"Consensus: {_creport['claims_approved']} approved, "
                  f"{_creport['claims_rejected']} rejected")
        if _creport.get("entropy_risk") == "high":
            log.warning("[ENTROPY] High AI detection risk for '%s'", keyword)
        # Emit consensus completed event
        try:
            from event_bus import emit as _bus_emit
            _bus_emit("consensus.completed", {
                "keyword": keyword,
                "critical_issues": len(_creport.get("critical_issues", [])),
                "claims_approved": _creport.get("claims_approved", 0),
                "claims_rejected": _creport.get("claims_rejected", 0),
                "entropy_risk": _creport.get("entropy_risk", "unknown"),
            })
        except ImportError:
            pass
    except ImportError:
        pass

    # Evidence DAG — build full claim lineage with contradiction detection
    _dag = None
    try:
        from evidence_dag import build_evidence_dag
        _dag = build_evidence_dag(article, verify=True, propagate=True)
        if _dag.claim_count() > 0 and _dag.edge_count() > 0:
            _info(f"Evidence DAG: {_dag.claim_count()} claims, "
                  f"{_dag.edge_count()} edges, acyclic={_dag.verify_acyclic()}")
        # Tag articles with contradiction warnings
        _contra_count = sum(
            1 for n in _dag.nodes.values() if len(n.contradicted_by) > 0
        )
        if _contra_count > 0:
            log.warning("[EVIDENCE-DAG] %d claims with contradictions in '%s'",
                         _contra_count, keyword)
        # Emit DAG built event
        try:
            from event_bus import emit as _bus_emit
            _bus_emit("dag.built", {
                "keyword": keyword,
                "claim_count": _dag.claim_count(),
                "edge_count": _dag.edge_count(),
                "contradictions": _contra_count,
                "acyclic": _dag.verify_acyclic(),
            })
        except ImportError:
            pass
    except ImportError:
        pass

    # Truth Infrastructure — persist claims, citations, contradictions
    try:
        from truth_infrastructure import (
            register_claim, record_contradiction, get_truth_store,
        )
        _ts = get_truth_store()
        # Register all claims from the Evidence DAG as permanent nodes
        if _dag.claim_count() > 0:
            for _tnode in _dag.nodes.values():
                register_claim(
                    text=_tnode.text,
                    claim_type=_tnode.claim_type,
                    confidence=_tnode.confidence,
                    keyword=keyword,
                )
            # Register contradiction edges
            for _f, _t, _r in _dag.edges:
                if _r == "contradicts":
                    _ca = _dag.nodes.get(_f)
                    _cb = _dag.nodes.get(_t)
                    if _ca and _cb:
                        record_contradiction(
                            claim_a_text=_ca.text,
                            claim_b_text=_cb.text,
                            claim_a_id=_ca.id,
                            claim_b_id=_cb.id,
                            keyword=keyword,
                        )
        # Emit truth registered event
        try:
            from event_bus import emit as _bus_emit
            _bus_emit("truth.registered", {
                "keyword": keyword,
                "claim_count": _dag.claim_count() if _dag else 0,
                "contradictions": (_dag.edge_count() if _dag else 0),
            })
        except ImportError:
            pass
    except ImportError:
        pass

    # Adaptive Trust Engine — probabilistic publish risk assessment
    _trust_report = None
    try:
        from adaptive_trust_engine import evaluate_publish_risk
        _trust_report = evaluate_publish_risk(
            article, keyword,
            dag=_dag if _dag and _dag.claim_count() > 0 else None,
            consensus=_creport if '_creport' in dir() else None,
        )
        if _trust_report.verdict == "block":
            log.warning("[ADAPTIVE-TRUST] BLOCKED: risk=%.2f for '%s'",
                         _trust_report.risk_score, keyword)
            _info(f"Trust verdict: {_trust_report.verdict.upper()} "
                  f"(risk={_trust_report.risk_score:.2f})")
            for f in _trust_report.factors:
                if f.weighted() > 0.05:
                    _info(f"  Factor '{f.name}': {f.weighted():.3f} — {f.evidence}")
        elif _trust_report.verdict in ("quarantine", "review"):
            log.warning("[ADAPTIVE-TRUST] %s: risk=%.2f for '%s'",
                         _trust_report.verdict.upper(), _trust_report.risk_score, keyword)
        # Emit trust evaluated event
        try:
            from event_bus import emit as _bus_emit
            _bus_emit("trust.evaluated", {
                "keyword": keyword,
                "risk_score": _trust_report.risk_score,
                "verdict": _trust_report.verdict,
                "factor_count": len(_trust_report.factors),
            })
        except ImportError:
            pass
    except ImportError:
        pass

    # ── Temporal Intelligence Engine ──
    _temporal_report = None
    try:
        from temporal_intelligence import (
            get_temporal_engine, TemporalClaim,
        )
        _temporal_engine = get_temporal_engine()
        # Build temporal claims from DAG
        _temporal_claim_list = []
        if _dag and _dag.claim_count() > 0:
            for _nid, _node in _dag.nodes.items():
                _tc = TemporalClaim(
                    text=_node.text,
                    claim_type=_node.claim_type,
                    confidence=_node.confidence,
                    keyword=keyword,
                )
                _temporal_claim_list.append(_tc)
        _temporal_report = _temporal_engine.process_article(
            article, keyword,
            claims=_temporal_claim_list if _temporal_claim_list else None,
            niche=_detect_niche(keyword),
        )
        if _temporal_report:
            _info(f"Temporal: eff_conf={_temporal_report.get('effective_confidence', 0):.3f}, "
                  f"decayed={len(_temporal_report.get('decayed_claims', []))}, "
                  f"expired={len(_temporal_report.get('expired_citations', []))}")
    except ImportError:
        pass
    except Exception as _te:
        log.warning("[TEMPORAL] Temporal intelligence failed: %s", _te)

    # ── Adversarial Swarm Audit ──
    _swarm_report = None
    try:
        from adversarial_swarm import run_adversarial_swarm
        _swarm_report = run_adversarial_swarm(article, keyword)
        _swarm_risk = _swarm_report.weighted_risk_score
        _swarm_verdict = _swarm_report.consensus_verdict
        _info(f"Swarm: risk={_swarm_risk:.3f} → {_swarm_verdict.upper()}")
        if _swarm_report.majority_disagreement:
            _info(f"  Swarm disagreement detected (std={_swarm_report.weighted_risk_score:.2f})")
        # Emit swarm completed event
        try:
            from event_bus import emit as _bus_emit
            _bus_emit("swarm.completed", {
                "keyword": keyword,
                "risk_score": _swarm_risk,
                "verdict": _swarm_verdict,
                "agent_count": len(_swarm_report.agent_results),
            })
        except ImportError:
            pass
    except ImportError:
        pass
    except Exception as _se:
        log.warning("[SWARM] Adversarial swarm failed: %s", _se)

    # ── Autonomous Repair Orchestrator (if trust blocks or swarm critical) ──
    _repair_memory = None
    _needs_repair = (
        (_trust_report and _trust_report.verdict in ("block", "quarantine"))
        or (_swarm_report and _swarm_report.consensus_verdict in ("block", "quarantine"))
    )
    if _needs_repair:
        try:
            from autonomous_repair_orchestrator import run_autonomous_repair
            _repair_reason = ""
            if _trust_report and _trust_report.verdict in ("block", "quarantine"):
                _repair_reason = f"Trust: {_trust_report.verdict} (risk={_trust_report.risk_score:.2f})"
            elif _swarm_report:
                _repair_reason = f"Swarm: {_swarm_report.consensus_verdict} (risk={_swarm_report.weighted_risk_score:.2f})"
            _info(f"Auto-repair triggered: {_repair_reason}")
            article, _repair_memory = run_autonomous_repair(article, _repair_reason, keyword)
            if _repair_memory.escalated:
                log.warning("[REPAIR] Escalated for '%s': %s", keyword, _repair_memory.escalation_reason)
            # Emit repair orchestrated event
            try:
                from event_bus import emit as _bus_emit
                _bus_emit("repair.orchestrated", {
                    "keyword": keyword,
                    "root_cause": _repair_memory.root_cause,
                    "attempts": len(_repair_memory.outcomes),
                    "escalated": _repair_memory.escalated,
                })
            except ImportError:
                pass
        except ImportError:
            pass
        except Exception as _re:
            log.warning("[REPAIR] Autonomous repair failed: %s", _re)

    # ── Temporal Governor (freshness SLA enforcement) ──
    _governor_report = None
    try:
        from temporal_governor import run_temporal_governance
        _temporal_claims_dict = []
        if _temporal_report and _temporal_report.get("decayed_claims"):
            _temporal_claims_dict = _temporal_report["decayed_claims"]
        _governor_report = run_temporal_governance(
            article, keyword,
            niche=_detect_niche(keyword),
            claims=_temporal_claims_dict,
        )
        _info(f"Governor: freshness={_governor_report.overall_freshness:.3f}, "
              f"SLA={_governor_report.sla_status}, "
              f"expired={len(_governor_report.expired_claims)}")
        if _governor_report.quarantine_recommended:
            log.warning("[GOVERNOR] Quarantine recommended for '%s' (freshness=%.2f)",
                         keyword, _governor_report.overall_freshness)
        # Emit temporal expiry event
        if _governor_report.expired_claims:
            try:
                from event_bus import emit as _bus_emit
                _bus_emit("temporal.expiry_detected", {
                    "keyword": keyword,
                    "expired_count": len(_governor_report.expired_claims),
                    "sla_status": _governor_report.sla_status,
                    "freshness": _governor_report.overall_freshness,
                })
            except ImportError:
                pass
    except ImportError:
        pass
    except Exception as _ge:
        log.warning("[GOVERNOR] Temporal governor failed: %s", _ge)

    # ── Enterprise Governor (final publish decision) ──
    _governance_decision = None
    try:
        from enterprise_governor import evaluate_publish
        _governance_decision = evaluate_publish(
            keyword=keyword,
            article=article,
            trust_report=_trust_report.to_dict() if _trust_report else None,
            swarm_report=_swarm_report.to_dict() if _swarm_report else None,
            temporal_report=_temporal_report,
            governor_report=_governor_report.to_dict() if _governor_report else None,
            consensus_report=_creport if '_creport' in dir() else None,
            dag_report=_dag.to_dict() if _dag else None,
            repair_memory=_repair_memory.to_dict() if _repair_memory else None,
        )
        _info(f"Governance: {_governance_decision.verdict.upper()} "
              f"(risk={_governance_decision.risk_score:.3f}, "
              f"budget={_governance_decision.confidence_budget:.2f})")
        if _governance_decision.verdict == "block":
            from enterprise_governor import PublishBlocked as GovPublishBlocked
            raise GovPublishBlocked(
                f"Enterprise governor blocked: {_governance_decision.recommendations[0] if _governance_decision.recommendations else 'Risk threshold exceeded'}"
            )
        elif _governance_decision.verdict == "quarantine":
            log.warning("[GOVERNANCE] Quarantined '%s': risk=%.2f",
                         keyword, _governance_decision.risk_score)
    except ImportError:
        pass
    except Exception as _gove:
        if "PublishBlocked" in type(_gove).__name__:
            raise
        log.warning("[GOVERNANCE] Enterprise governor failed: %s", _gove)

    # ── Site Intelligence Graph (ingest) ──
    try:
        from site_intelligence_graph import ingest_article, get_site_graph
        _sg_node = ingest_article(
            keyword=keyword,
            article=article,
            niche=_detect_niche(keyword),
            intent=_detect_intent(keyword),
            quality_score=(
                _quality.get("score", 50) / 100.0
                if '_quality' in dir() and _quality
                else 0.5
            ),
        )
        _sg = get_site_graph()
        _sg_stats = _sg.get_stats()
        # Emit site ingested event
        try:
            from event_bus import emit as _bus_emit
            _bus_emit("site.ingested", {
                "keyword": keyword,
                "entities": len(_sg_node.entities),
                "links": len(_sg_node.outbound_links),
                "total_articles": _sg_stats.get("articles", 0),
            })
        except ImportError:
            pass
    except ImportError:
        pass
    except Exception as _sie:
        log.warning("[SITE_GRAPH] Site intelligence ingestion failed: %s", _sie)

    word_count = len(article.split())
    print(c("dim", "  " + "─" * 56))

    # ── Claim verification pipeline ──
    if cv:
        try:
            serp_texts = []
            mem_entries = []
            if mem_filtered:
                for a in mem_filtered.get("articles_written", []):
                    mem_entries.append(json.dumps(a))

            report = cv.verify_article(article, serp_texts or None, mem_entries or None)
            # Apply claim-verifier actions: strip rejected claims, tag low-confidence
            rejected_claims = [c for c in report.get("claims", []) if c.get("status") == "rejected"]
            low_conf_claims = [c for c in report.get("claims", []) if c.get("confidence", 1.0) < 0.5]
            for _rc in rejected_claims:
                _val = _rc.get("value", "")
                if _val and len(_val) > 5:
                    _before = len(article)
                    article = article.replace(" " + _val + " ", " [REMOVED: unverifiable claim] ")
                    article = article.replace(_val, "[REMOVED: unverifiable claim]")
                    if len(article) < _before:
                        log.info("[CLAIM_ACTION] Stripped rejected claim: '%s'", _val[:80])
            for _lc in low_conf_claims:
                _val = _lc.get("value", "")
                if _val and len(_val) > 3 and _val in article:
                    article = article.replace(_val, _val + "[VERIFY]")
            if report["issues"]:
                print(c("yellow", f"  ⚠ Claim Verification: {report['score']}/100"))
                for issue in report["issues"][:3]:
                    print(c("red", f"    ✗ {issue}"))
            else:
                print(c("green", f"  ✓ Claim Verification: {report['score']}/100 — {report['verified_count']}/{report['total_claims']} claims verified"))
        except Exception as cv_err:
            log.warning("[CLAIM_VERIFIER] Verification failed: %s", cv_err)

    _ok(f"Article complete — {word_count} words")

    # ── Phase 3 Intelligence Engines ─────────────────────────
    if _HAS_INTELLIGENCE:
        try:
            niche = _detect_niche(keyword)
            # Humanization rewrite (modifies prose)
            _humanized, _hr_report = get_human_rewriter().rewrite(article)
            article = _humanized
            if _hr_report.changes_made:
                _info(f"Humanization: {_hr_report.changes_made} changes (openers={_hr_report.sentence_openings_diversified}, phrases={_hr_report.ai_phrase_removals})")

            # CTA optimization (modifies article for commercial intent)
            article = get_conversion_optimizer().optimize_cta(article, keyword)

            # AI detection resistance analysis
            _ai_report = get_ai_resistance().analyze(article)
            if _ai_report.overall_human_score < 0.3:
                log.warning("[AI_DETECTION] Low human score=%.3f for '%s'", _ai_report.overall_human_score, keyword)

            # Topic authority graph ingestion
            _quality = validate_article_quality(article, keyword)
            _qa_score = _quality.get("score", 60)
            get_authority_graph().ingest_article(keyword, article, niche, _qa_score)

            # Pattern performance tracking
            _reward = _ai_report.overall_human_score * 0.3 + (_qa_score / 100) * 0.7
            get_pattern_tracker().record_article(keyword, article, _qa_score, niche=niche, reward=_reward)

            # Citation engine analysis
            _citation_graph = get_citation_engine().analyze(article)
            _cite_report = get_citation_engine().enforce_citations(article, _citation_graph)
            if _cite_report.get("block"):
                log.warning("[CITATION_BLOCK] %d unsupported numerical/comparison claims for '%s'",
                             _cite_report["blocked_numerical"] + _cite_report["blocked_comparisons"], keyword)

            # Conversion optimizer analysis
            _conv_report = get_conversion_optimizer().analyze(keyword, article)
            if _conv_report.friction_points:
                _info(f"Conversion friction: {len(_conv_report.friction_points)} points, engagement={_conv_report.engagement_score}")

            # Retrieval-grounded validation (if chunks available via strategy)
            _retrieved = strategy.get("_retrieved_chunks", [])
            if _retrieved:
                get_retrieval_validator().validate(keyword, article, _retrieved)

            # SERP gap analysis (if competitor data available)
            _comp_data = strategy.get("_competitor_articles", [])
            if keyword and _comp_data:
                get_serp_gap_engine().analyze(keyword, article, competitor_articles=_comp_data)

        except Exception as _ie:
            log.warning("[INTELLIGENCE] Phase 3 engine failed for '%s': %s", keyword, _ie)

    # ── Editorial scoring dashboard ───────────────────────────
    try:
        if _HAS_EDITORIAL_SCORE and article:
            _score_report = compute_editorial_score(
                keyword=keyword,
                trust_risk_score=_trust_report.risk_score if _trust_report else None,
                temporal_violations=_temp_violations if _HAS_TEMPORAL_GROUNDING and '_temp_violations' in dir() else None,
                coverage_result=None,
                superlative_report=_sup_report if _HAS_SUPERLATIVE_SUPPRESSOR and '_sup_report' in dir() else None,
            )
            _info(f"Editorial score: {_score_report.final_score}/100 — {_score_report.verdict}")
    except Exception as _es_err:
        log.warning("[EDITORIAL_SCORE] Scoring failed: %s", _es_err)

    # ── Benchmark arena ───────────────────────────────────────
    try:
        if _HAS_BENCHMARKS and article:
            _bench_results = run_all_benchmarks(article, keyword)
            _info(f"Benchmark arena: {_bench_results['overall']['score']}/100 ({_bench_results['overall']['benchmarks_run']} benchmarks)")
    except Exception as _b_err:
        log.warning("[BENCHMARKS] Arena failed: %s", _b_err)

    # Emit pipeline completed event
    try:
        from event_bus import emit as _bus_emit
        _bus_emit("pipeline.completed", {
            "keyword": keyword,
            "model": model,
            "word_count": word_count,
            "trust_verdict": _trust_report.verdict if _trust_report else "unknown",
            "swarm_verdict": _swarm_report.consensus_verdict if _swarm_report else "unknown",
            "governance_verdict": _governance_decision.verdict if _governance_decision else "unknown",
        })
    except ImportError:
        pass

    return article


# ──────────────────────────────────────────────────────────────
#  Module 4 — CTR Optimizer
# ──────────────────────────────────────────────────────────────

def optimize_ctr(keyword: str, article_snippet: str, model: str) -> dict:
    _step("CTR Optimization  —  Title & Meta Description")

    system = "You are a search CTR specialist. Write titles and descriptions that maximize click-through rate."
    user   = f"""Keyword: "{keyword}"

Article opening (first 600 chars):
{article_snippet[:600]}

Generate 3 options each. Return JSON:
{{
  "titles": ["max 60 chars each"],
  "descriptions": ["max 155 chars each"],
  "recommended_title": "",
  "recommended_description": ""
}}

Rules for titles:
- Include the keyword
- Use numbers when natural
- Power words: Proven, Complete, Best, Guide, Step-by-Step
- Trigger curiosity without clickbait

Rules for descriptions:
- Include keyword naturally
- State the value clearly
- End with a soft call to action"""

    result = call_json(system, user, model)

    _ok(f"Title:       {result.get('recommended_title', '')}")
    _ok(f"Description: {result.get('recommended_description', '')}")

    return result


# ──────────────────────────────────────────────────────────────
#  Module 5 — Keyword Cluster Builder  (V3)
# ──────────────────────────────────────────────────────────────

def build_cluster(keyword: str, niche: str, model: str) -> dict:
    _step(f"Keyword Cluster Map  —  Niche: {niche or 'auto-detect'}")

    system = "You are a keyword architecture expert. Build comprehensive topic clusters for SEO authority."
    user   = f"""Build a complete keyword cluster for: "{keyword}"
Niche: {niche or 'detect from keyword'}

Return JSON:
{{
  "pillar": {{
    "keyword":    "main keyword",
    "intent":     "informational|commercial|navigational",
    "word_count": 0,
    "title":      "suggested H1 title"
  }},
  "clusters": [
    {{
      "keyword":          "",
      "type":             "informational|commercial|navigational",
      "priority":         "high|medium|low",
      "estimated_volume": "high|medium|low",
      "title":            "suggested article title"
    }}
  ],
  "long_tail":           ["list of long-tail keyword variants"],
  "internal_link_map": {{
    "pillar_to_clusters": ["cluster keywords to link from pillar"],
    "cluster_to_cluster": ["cross-linking suggestions"]
  }},
  "quick_wins":          ["low-competition, high-intent keywords"],
  "authority_path":      "recommended publishing order summary"
}}"""

    result = call_json(system, user, model)

    total  = len(result.get("clusters", []))
    high   = [x for x in result.get("clusters", []) if x.get("priority") == "high"]

    _ok(f"Pillar:       {result.get('pillar', {}).get('keyword', '')}")
    _ok(f"Clusters:     {total} topics")
    _ok(f"High priority: {len(high)}")
    _ok(f"Long-tail:    {len(result.get('long_tail', []))}")
    _ok(f"Quick wins:   {len(result.get('quick_wins', []))}")
    for item in high[:3]:
        _info(f"[HIGH] {item.get('keyword', '')}  ({item.get('type', '')})")

    return result


# ──────────────────────────────────────────────────────────────
#  Module 6 — Content Calendar  (V3)
# ──────────────────────────────────────────────────────────────

def build_calendar(keyword: str, niche: str, months: int, model: str) -> list:
    _step(f"Content Calendar  —  {months} months")

    system = "You are a strategic content planner. Build data-driven publishing calendars for SEO growth."
    user   = f"""Build a {months}-month content calendar.
Niche: {niche or 'detect from keyword'}
Seed keyword: {keyword}
Publishing frequency: 3 articles/week

Structure per month:
- Week 1:   Pillar article (2000+ words)
- Week 2–3: Cluster articles (1000–1500 words)
- Week 4:   Long-tail + FAQ articles (800+ words)

Return a JSON array (one object per article):
[
  {{
    "month":      1,
    "week":       1,
    "title":      "",
    "keyword":    "",
    "type":       "pillar|cluster|long-tail",
    "word_count": 0,
    "intent":     "informational|commercial|navigational",
    "priority":   "P1|P2|P3",
    "links_to":   ["keywords this article should link to"]
  }}
]"""

    result = call_json(system, user, model)

    if isinstance(result, list):
        pillar     = sum(1 for a in result if a.get("type") == "pillar")
        commercial = sum(1 for a in result if a.get("intent") == "commercial")
        _ok(f"Total articles:   {len(result)}")
        _ok(f"Pillar articles:  {pillar}")
        _ok(f"Commercial intent: {commercial}")
        for item in result[:3]:
            _info(f"Month {item.get('month')} / Week {item.get('week')}: {item.get('title', '')[:55]}")

    return result if isinstance(result, list) else []


# ──────────────────────────────────────────────────────────────
#  Module 7 — Topical Authority Score  (V3)
# ──────────────────────────────────────────────────────────────

def score_authority(niche: str, articles_written: list, model: str) -> dict:
    _step("Topical Authority Score")

    titles = [a.get("keyword", "") for a in articles_written[-20:]]

    system = "You are an SEO authority analyst. Assess topical coverage and provide actionable gaps."
    user   = f"""Niche: "{niche}"
Articles written so far:
{json.dumps(titles, indent=2)}

Assess topical authority and return JSON:
{{
  "authority_score": 0,
  "coverage_pct":    "0%",
  "strong_areas":    ["topics well covered"],
  "weak_areas":      ["topics needing more content"],
  "next_3_articles": ["most impactful articles to write next"],
  "estimated_weeks_to_authority": 0
}}"""

    result = call_json(system, user, model)

    _ok(f"Authority score:  {result.get('authority_score', 0)} / 100")
    _ok(f"Coverage:         {result.get('coverage_pct', '0%')}")
    _ok(f"ETA to authority: {result.get('estimated_weeks_to_authority', '?')} weeks")
    for a in result.get("next_3_articles", [])[:3]:
        _info(f"Write next → {a}")

    return result
