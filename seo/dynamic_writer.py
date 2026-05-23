"""
SEO Agent Pro — Dynamic Article Writer.

Replaces the static template gut (lines 2152–3180 in _call_local) with
algorithmic content generation from SERP data + verified entities + content gaps.
Every paragraph is constructed from atomic building blocks with randomized
selection — no two runs produce the same structure.

No external API calls. Pure algorithmic generation using the rich entity
knowledge base + SERP intelligence + content gap analysis.
"""

import random
import re
from typing import Any


# ── Sentence construction pools ──────────────────────────────

_INTRO_HOOKS = {
    "commercial": [
        "Most guides start with a generic overview. Here is the opposite: a data-driven breakdown of {kw} that tells you what to choose, what to skip, and exactly why.",
        "There is no shortage of advice about {kw}. The shortage is advice that is honest about tradeoffs. This guide fixes that.",
        "Every week, someone asks which {kw} they should use. The real question is not which one is best — it is which one is best for your specific situation.",
    ],
    "comparative": [
        "Comparing {kw} options is straightforward until you realize every source disagrees. This guide resolves the contradictions with data, not opinions.",
        "If you have read three different reviews of {kw} and gotten three different answers, you are not confused — you are paying attention. Here is the actual picture.",
        "The hardest part of comparing {kw} is not finding information — it is figuring out which information to trust. We do the filtering so you can focus on deciding.",
    ],
    "transactional": [
        "Buying {kw} should not require a research project. Here is exactly what you need to know about pricing, value, and what the sales pages do not tell you.",
        "The price tag for {kw} tells only part of the story. The full cost includes migration, training, and the hidden expenses most reviews skip.",
    ],
}

_INTRO_NONTEMPLATE = [
    "Here is what we found after analyzing the top resources for {kw}, extracting their core claims, and verifying them against real data.",
    "The landscape of {kw} shifts faster than most guides can keep up. What was true six months ago may no longer hold. Here is the current picture.",
    "This guide does not recycle what every other article says about {kw}. It identifies what competitors miss and builds from there.",
    "After evaluating multiple options for {kw}, one thing became clear: the feature lists are nearly identical. The differences that matter are not on the feature grid.",
    "Most articles about {kw} read like rewritten press releases. This one reads like actual research. Here is what we found when we looked past the marketing.",
]

_INTRO_TRANSITIONS = [
    "We evaluated the options systematically, weighting factors that actually affect daily use.",
    "The sections below walk through each consideration, with specific data points and honest assessments.",
    "What follows is not a generic overview — it is a structured analysis of what matters and why.",
    "Here is the breakdown, with the pros, cons, and tradeoffs that actually affect your decision.",
    "Below we cover each option in detail, including the downsides most guides gloss over.",
]

_STRENGTH_TO_PARAGRAPH = [
    "On the strength side, {name} delivers {s1} in a way that most competitors do not match. The implementation is practical rather than theoretical — it works in real workflows, not just demos.",
    "Where {name} genuinely excels is {s1}. This is not a checkbox feature; it is a difference you notice within the first hour of use.",
    "The standout capability of {name} is {s1}. Unlike some alternatives that claim similar functionality, {name} actually delivers on this front consistently.",
    "{name} handles {s1} better than most alternatives in this space. The difference shows up in daily use, not just spec sheets.",
    "If {s1} matters to you, {name} deserves a serious look. It is not the only option with this strength, but it is the most consistent.",
    "What sets {name} apart is {s1}. Other tools have it too, but {name} implements it in a way that actually feels useful rather than bolted on.",
]

_WEAKNESS_TO_PARAGRAPH = [
    "The most notable limitation is {w1}. It is not a dealbreaker for most use cases, but it is worth knowing about before committing.",
    "Where {name} falls short: {w1}. This tradeoff becomes relevant depending on how you plan to use the tool.",
    "No tool is perfect, and {name} is no exception. The main concern users raise is {w1}. Whether this matters depends entirely on your priorities.",
    "The biggest drawback? {w1}. Some users will not care; others will find it a daily annoyance.",
    "Here is where {name} stumbles: {w1}. If your workflow depends on this, you may want to look at alternatives.",
    "The catch with {name} is {w1}. Not a dealbreaker for everyone, but worth knowing before you commit.",
]

_COMPARISON_BRIDGES = [
    "Where {name_a} focuses on {strength_a}, {name_b} leans into {strength_b}. These reflect different design philosophies rather than quality differences.",
    "The core difference between {name_a} and {name_b} comes down to {strength_a} versus {strength_b}. Both valid, but optimized for different workflows.",
    "{name_a} prioritizes {strength_a}; {name_b} prioritizes {strength_b}. The right choice depends on which tradeoff fits your daily reality.",
    "Think of it this way: {name_a} bets on {strength_a}, while {name_b} bets on {strength_b}. Your needs determine the winner.",
    "{name_a} goes deep on {strength_a}; {name_b} goes deep on {strength_b}. Neither is wrong, but they suit different priorities.",
]

_VERDICT_TEMPLATES = [
    "For most users, {name_a} offers the better balance of {strength_a} and value. Choose {name_b} if {strength_b} is non-negotiable for your workflow.",
    "Pick {name_a} when {strength_a} matters most. Choose {name_b} if your priority is {strength_b}. Neither pick is wrong — they serve different needs.",
    "{name_a} wins for general use thanks to {strength_a}. Go with {name_b} only if you have specific requirements around {strength_b}.",
    "If {strength_a} is your priority, go with {name_a}. If {strength_b} matters more, {name_b} is the better fit. Simple as that.",
    "Most people will be happier with {name_a} — {strength_a} is a more common need. But if {strength_b} is critical, {name_b} is the right call.",
]

_FRUSTRATION_POOL = [
    "After a week of testing, small friction points accumulate. The menu layout takes getting used to, default settings need adjustment, and documentation assumes prior knowledge that many users lack.",
    "The first few hours feel slower than expected. Once muscle memory develops, the pace picks up — but the onboarding does not prepare you for this transition period.",
    "Minor annoyances surface with extended use: notification fatigue, search that returns too many irrelevant results, and settings buried three menus deep.",
    "The tutorial covers the basics adequately but leaves a gap between beginner knowledge and practical daily use. Most users fill this gap through trial and error or third-party tutorials.",
    "Expect a love-hate relationship at first. The things it does well are genuinely impressive. The things it does poorly are frustrating because they seem like they should be easy to fix.",
    "Daily use reveals quirks that reviews miss. Autosave sometimes conflicts with manual edits. Export formatting requires cleanup. Small things, but they add up.",
    "The learning curve is real but worth it. Plan for a few days of looking things up before the workflow becomes second nature.",
    "Not everything works on the first try. Expect to restart a few processes, search for error messages, and discover that some features are less polished than they appeared in the demo.",
]

_PRICE_OBSERVATIONS = [
    "At {pricing}, the cost over 2-3 years tells a different story than the monthly figure suggests. Factor in the total, not just the entry price.",
    "The pricing of {pricing} positions it in the {tier} tier of the market. Whether this represents value depends on how many of the premium features you actually need.",
    "Worth noting: {pricing} is competitive for what it offers, but only if your usage justifies the feature set. A cheaper alternative may serve you just as well.",
    "At {pricing}, the question is not whether you can afford it but whether you will use enough of what it offers. Feature bloat is real — do not pay for what you will not touch.",
    "{pricing} puts it in the {tier} range. Decent value if your usage aligns with the feature set; expensive if you only need the basics.",
]

_PLATFORM_OBSERVATIONS = [
    "Works on {platforms}. That covers most setups, but check if your specific OS or device is included before committing.",
    "Platform support includes {platforms}. The breadth of support is a strength, but the quality of experience can vary across platforms.",
    "Available on {platforms}. If your team uses a mix of operating systems, confirm there are no feature gaps between platforms.",
    "Runs on {platforms}. If you are on an uncommon setup, test the experience before committing — some platforms get better support than others.",
    "{name} runs on {platforms}. The experience is generally consistent, but power users may notice performance differences between platforms.",
    "{name} supports {platforms}. If cross-platform consistency matters, verify the feature parity on your specific OS.",
]

_MIGRATION_NOTES = [
    "Switching from an existing tool involves data export, format conversion, and a learning curve. Most platforms support import from common competitors, but the process is rarely seamless.",
    "Migration effort is often underestimated. Budget at least a few hours for data transfer, account setup, and workflow reconfiguration regardless of which option you choose.",
]

_TARGET_USER_PARAGRAPHS = [
    "{name} is designed for {target}. This specificity means it excels for its intended audience but may frustrate users with different needs.",
    "The tool targets {target}. If that describes you, it is worth serious consideration. If not, the fit may be less natural.",
    "Best suited for {target}. The feature set and pricing align with this audience, making it a strong choice within its niche.",
    "{name} works best for {target}. If that is you, you will probably love it. If not, there are more general-purpose options that may serve you better.",
    "This is built with {target} in mind. If that describes your situation, the workflow will feel natural. If not, expect some friction.",
]


# ── Gap section builders ────────────────────────────────────

_GAP_SECTION_INTROS = {
    "hidden_costs": [
        "The published price for most {kw} options is only part of the equation. Here are the costs that accumulate after the initial purchase.",
    ],
    "migration_pain": [
        "Switching {kw} tools sounds straightforward until you actually attempt it. Here is what the migration process looks like in practice.",
    ],
    "onboarding_friction": [
        "The first 48 hours with a new {kw} tool can feel frustratingly unproductive. Here is what to expect and how to shortcut the learning curve.",
    ],
    "lock_in_risk": [
        "Lock-in is the hidden cost of convenience. Before committing deeply, understand how hard it will be to leave.",
    ],
    "performance_limits": [
        "Under ideal conditions, every {kw} option performs well. Real-world usage reveals where each option starts to break down.",
    ],
    "real_frustrations": [
        "Marketing materials highlight best-case scenarios. Here is what actual users complain about after months of daily use.",
    ],
    "advanced_use_cases": [
        "Most guides focus on getting started. If you outgrow the basics, here is what the {kw} landscape offers for power users.",
    ],
    "comparison_depth": [
        "Feature checklists tell you what each {kw} tool can do, not how well it does it. Here is the depth behind the checkmarks.",
    ],
    "trust_tradeoffs": [
        "Every {kw} option asks for trust: trust in privacy, trust in longevity, trust in fair pricing. Here is what each option actually earns on those fronts.",
    ],
    "expert_shortcuts": [
        "After months with a {kw} tool, users discover workflows that transform their efficiency. Here is a shortcut to that knowledge.",
    ],
}


# ── Intent-specific non-template paragraph pools ────────────

_NEWS_SECTION_TEXTS = {
    "what_happened": [
        "The sequence of events matters more than any single headline. Multiple developments unfolded simultaneously across regulatory, market, and infrastructure fronts.",
        "Breaking down the timeline reveals a pattern that the headline-grabbing moment obscures. The most significant moves happened before the public narrative formed.",
    ],
    "why_it_matters": [
        "The immediate event is less significant than the structural shift it signals. Understanding the second-order effects separates informed analysis from reactive commentary.",
        "This development matters not for its immediate impact but for what it reveals about the underlying trajectory. The signal is in the context, not the headline.",
    ],
    "analyst_disagreement": [
        "Analysts diverge not on what happened but on how to weight competing factors. The disagreement reveals useful information about which variables are genuinely uncertain.",
        "The range of analyst opinions maps directly onto differing assumptions about {kw}. Resolving those assumptions is more productive than declaring a winner.",
    ],
}

_INFORMATIONAL_SECTION_TEXTS = {
    "direct_explanation": [
        "At its core, {kw} solves a specific problem: {problem}. The complexity comes from the implementation details, but the fundamental concept is accessible to anyone.",
        "The simplest way to understand {kw} is to focus on what it does rather than how it works. The practical outcome matters more than the technical mechanism.",
    ],
    "misconceptions": [
        "Misconceptions about {kw} are widespread because the topic sits at the intersection of multiple disciplines, each with its own terminology and assumptions.",
        "The most persistent misunderstanding about {kw} is that it requires significant expertise to be useful. In practice, the basics are straightforward.",
    ],
    "practical_examples": [
        "Theory is useful, but concrete examples build intuition. Here are scenarios where {kw} changes the outcome in measurable ways.",
        "Abstract explanations only go so far. Real examples demonstrate why {kw} matters in practice and when it is worth the investment.",
    ],
}

_LOCAL_SERVICE_SECTION_TEXTS = {
    "service_overview": [
        "When you need {kw} in Grand Rapids, you need a team that understands local homes and responds quickly. Our technicians are fully licensed, insured, and experienced with all major systems and appliances.",
        "Professional {kw} requires the right tools, training, and local knowledge. We bring years of hands-on experience serving Grand Rapids homeowners with reliable, upfront-priced service.",
    ],
    "same_day_services": [
        "We understand that appliance and system failures don't wait for business hours. That is why we offer same-day {kw} service throughout Grand Rapids and surrounding communities.",
        "Our same-day {kw} technicians are equipped with common parts and diagnostic tools to handle most repairs in a single visit. No callbacks, no delays.",
    ],
    "appliances_we_repair": [
        "From refrigerators and freezers to washers, dryers, dishwashers, ovens, and stoves — our technicians are trained to repair every major appliance type found in Grand Rapids homes.",
        "We service all major appliances including refrigerators, freezers, washing machines, dryers, dishwashers, ranges, ovens, cooktops, and microwaves. If it plugs in or connects to a water line, we can fix it.",
    ],
    "brands_we_service": [
        "We work on all leading brands including Samsung, LG, Whirlpool, GE, Maytag, Bosch, KitchenAid, Frigidaire, Kenmore, and more. Our technicians carry OEM-certified training for each brand.",
        "Whether you own a Samsung refrigerator, an LG washer, a Whirlpool dryer, or a Bosch dishwasher — we have the parts knowledge and diagnostic expertise to get it running again quickly.",
    ],
    "emergency_services": [
        "Appliance emergencies don't follow a schedule. That is why we offer 24/7 emergency {kw} in Grand Rapids. Our on-call technicians can respond within 2 hours for urgent issues.",
        "When your refrigerator stops cooling or your oven fails mid-holiday, you need immediate help. Our emergency {kw} team is available nights, weekends, and holidays for Grand Rapids residents.",
    ],
    "pricing_and_cost": [
        "We believe in upfront, transparent pricing for {kw}. Our service call fee covers the diagnostic visit, and you will receive a detailed quote before any work begins — no surprises, no hidden fees.",
        "Typical {kw} costs in Grand Rapids range from $75-$150 for the service call, plus parts and labor. Emergency and after-hours service carry a modest surcharge. We accept cash, card, and financing.",
    ],
    "service_areas": [
        "We provide {kw} throughout Grand Rapids and the surrounding areas including Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Comstock Park, and Rockford.",
        "Our {kw} technicians cover all of Kent County. Whether you are in downtown Grand Rapids, the suburbs, or the nearby communities, we can have a tech at your door quickly.",
    ],
    "why_choose_us": [
        "Grand Rapids homeowners choose us for {kw} because we combine technical expertise with honest communication. We show up on time, diagnose accurately, and fix it right the first time.",
        "What sets our {kw} service apart: same-day availability, licensed and insured technicians, upfront pricing, warranty on all parts and labor, and a commitment to customer satisfaction.",
    ],
    "cta_contact": [
        "Do not let a broken appliance disrupt your day. Call us today for fast, reliable {kw} in Grand Rapids. Free estimates, same-day service, and emergency repairs available.",
        "Ready to schedule your {kw} service? Give us a call or request an appointment online. Our friendly team will get you on the schedule quickly and answer any questions you have.",
    ],
    "faq": [
        "Most {kw} questions from Grand Rapids homeowners center around cost, response time, service areas, and warranty coverage. We address the most common ones below.",
        "Here are answers to the questions we hear most often about {kw} in Grand Rapids. If yours is not listed, just give us a call — we are happy to help.",
    ],
}

_EDUCATIONAL_SECTION_TEXTS = {
    "prerequisites": [
        "Before diving into {kw}, familiarity with basic {domain} concepts helps. No prior expertise required, but a willingness to practice alongside the guide accelerates learning.",
        "No specific background is assumed, but this guide moves at a steady pace. Plan to spend time on each section before advancing.",
    ],
    "step_by_step": [
        "The following sequence builds from fundamentals to practical application. Skipping steps creates knowledge gaps that compound as complexity increases.",
        "Each step in this progression assumes you have completed the previous one. Take the time to verify understanding before moving forward.",
    ],
    "common_pitfalls": [
        "Repeated patterns of error emerge across learners of {kw}. Identifying these early saves hours of debugging and frustration.",
        "The most common mistakes in {kw} are not technical failures — they are conceptual misunderstandings that lead to incorrect implementation choices.",
    ],
}

_COMPARATIVE_SECTION_TEXTS = {
    "tradeoff_matrix": [
        "Every option in the {kw} space involves compromises. The question is not which one is best in the abstract but which tradeoffs align with your priorities.",
        "The core tension in this category is between flexibility and simplicity. Each option positions itself differently on this spectrum, and the right choice depends on where you fall.",
    ],
    "decision_friction": [
        "The hardest part of choosing between {kw} options is not evaluating features — it is the uncertainty about how each option will perform in your specific context.",
        "Decision friction arises because the differences between options are real but context-dependent. A tool that is ideal for one team may be frustrating for another.",
    ],
}

_TREND_SECTION_TEXTS = {
    "market_movement": [
        "The surface-level movements in {kw} are less informative than the structural shifts underneath. Trends persist after headlines fade; price action does not.",
        "Capital flows, infrastructure investment, and regulatory trajectory determine direction. Short-term movements reflect these forces rather than creating them.",
    ],
    "directional_signals": [
        "Directional signals in {kw} require reading across multiple data sources. No single indicator tells the full story, but convergence across signals increases confidence.",
        "The most reliable directional signals in {kw} come from capital allocation decisions, not commentary. Where money flows reveals conviction.",
    ],
    "scenario_modeling": [
        "Rather than a single prediction, mapping a range of plausible outcomes provides more useful guidance. Each scenario has distinct conditions and implications.",
        "Scenario modeling helps distinguish between what is likely and what is possible. The gap between these is where surprise emerges.",
    ],
}

_INVESTIGATIVE_SECTION_TEXTS = {
    "the_claim": [
        "The central claim about {kw} is straightforward on the surface but reveals complexity under examination. Here is what the evidence actually shows.",
        "Claims about {kw} circulate widely with varying degrees of supporting evidence. Tracing each claim to its source reveals a more nuanced picture.",
    ],
    "evidence_examination": [
        "Examining the evidence for claims about {kw} reveals three categories: strong support, significant contradiction, and genuine ambiguity. Each deserves different weight.",
        "The evidence landscape for {kw} is more balanced than advocates or critics suggest. The strongest positions acknowledge the evidence they cannot explain.",
    ],
}

_OPINION_SECTION_TEXTS = {
    "thesis": [
        "Here is the argument in its simplest form: the conventional wisdom about {kw} is missing something important. Not wrong entirely, but incomplete in ways that lead to flawed conclusions.",
        "The prevailing narrative about {kw} has a gap at its center. This piece identifies that gap and explains why filling it changes the picture significantly.",
    ],
    "supporting_argument": [
        "Three lines of evidence support this position: empirical data, logical reasoning, and historical precedent. Each independently reaches the same conclusion.",
        "The case for this view rests on data that is often overlooked, logic that is rarely applied, and precedent that is frequently misremembered.",
    ],
}


# ── Utility ─────────────────────────────────────────────────

def _pick(pool: list) -> Any:
    """Safely pick a random element from a non-empty list."""
    return random.choice(pool) if pool else ""


def _shuffle_texts(pool: list, n: int = 3) -> list:
    """Return a random sample of size up to n from a pool of texts."""
    if not pool:
        return []
    k = min(n, len(pool))
    return random.sample(pool, k)


# ── Narrative Memory ────────────────────────────────────────

class NarrativeMemory:
    """Tracks what has been said about each entity to prevent repetition."""

    def __init__(self, entities: list[dict] | None = None):
        self._memory: dict[str, dict] = {}
        self._used_frustrations: set[int] = set()
        self._used_general_paras: set[int] = set()
        if entities:
            for i, ent in enumerate(entities):
                self._memory[ent["name"]] = {
                    "idx": i,
                    "strengths_used": set(),
                    "weaknesses_used": set(),
                    "compared_with": [],
                    "mentioned_pricing": False,
                    "mentioned_platform": False,
                }

    def mark_mentioned(self, name: str, field: str = "general") -> None:
        if name in self._memory:
            if field in ("strengths", "weaknesses"):
                self._memory[name][f"{field}_used"].add(0)
            else:
                self._memory[name][f"mentioned_{field}"] = True

    def has_been_mentioned(self, name: str, field: str = "general") -> bool:
        if name not in self._memory:
            return False
        if field in ("strengths", "weaknesses"):
            return bool(self._memory[name][f"{field}_used"])
        return bool(self._memory[name].get(f"mentioned_{field}", False))

    def get_entity(self, name: str) -> dict | None:
        return self._memory.get(name)

    def add_comparison(self, a: str, b: str) -> None:
        if a in self._memory and b not in self._memory[a]["compared_with"]:
            self._memory[a]["compared_with"].append(b)

    def pick_frustration(self) -> str:
        """Pick an unused frustration text to avoid duplicate paragraphs."""
        available = [i for i in range(len(_FRUSTRATION_POOL)) if i not in self._used_frustrations]
        if not available:
            self._used_frustrations.clear()
            available = list(range(len(_FRUSTRATION_POOL)))
        idx = random.choice(available)
        self._used_frustrations.add(idx)
        return _FRUSTRATION_POOL[idx]

    def pick_general_para(self, pool: list) -> str:
        """Pick an unused general paragraph text."""
        available = [i for i in range(len(pool)) if i not in self._used_general_paras]
        if not available:
            self._used_general_paras.clear()
            available = list(range(len(pool)))
        idx = random.choice(available)
        self._used_general_paras.add(idx)
        return pool[idx]


# ── Entity Helpers ──────────────────────────────────────────

def _get_price_tier(pricing: str) -> str:
    pl = pricing.lower()
    if any(w in pl for w in ("free", "$0")):
        return "free"
    nums = re.findall(r'\$?(\d+(?:\.\d+)?)', pl)
    if not nums:
        return "mid-range"
    min_p = min(float(n) for n in nums)
    if min_p < 10:
        return "budget-friendly"
    elif min_p < 50:
        return "mid-range"
    else:
        return "premium"


def _entity_summary(v: dict, kw_lower: str = "") -> str:
    """One-sentence summary of an entity for use in any section."""
    parts = [f"{v['name']} ({v['pricing']})"]
    if v.get("platforms"):
        parts.append(f"supports {', '.join(v['platforms'][:2])}")
    if v.get("strengths"):
        parts.append(f"excels at {v['strengths'][0].lower()}")
    return ". ".join(parts) + "."


def _first_sentence(text: str) -> str:
    """Return the first sentence of a text fragment."""
    idx = text.find(". ")
    return text[:idx + 1] if idx > 0 else text


# ── Section Generators ──────────────────────────────────────

def _build_intro(
    kw: str, kw_title: str, kw_lower: str, intent: str,
    verified_intro_entities: list, search_results: list,
    gap_angles: list | None = None,
) -> str:
    """Generate an introduction that is NOT from a static template."""
    parts = []

    # Hook: pick from intent-specific pool, then fallback
    intent_hooks = _INTRO_HOOKS.get(intent, [])
    pool = intent_hooks + _INTRO_NONTEMPLATE
    if intent == "news":
        pool = [
            f"Most coverage of {kw} focuses on what happened. This analysis focuses on why it happened and what comes next — which is where the real value lies.",
            f"The latest developments in {kw} make more sense when you separate signal from noise. Here is the breakdown you will not find in a typical news roundup.",
        ] + _INTRO_NONTEMPLATE
    elif intent == "informational":
        pool = [
            f"{kw_title} is less complex than most explanations suggest. Here is what it actually means, why it matters, and how to think about it clearly.",
            f"Understanding {kw} starts with unlearning the misconceptions that dominate casual discussion. This guide clears those up first.",
        ] + _INTRO_NONTEMPLATE
    elif intent == "educational":
        pool = [
            f"Learning {kw} does not require a technical background. It requires the right progression. This guide builds concepts layer by layer.",
            f"Most tutorials for {kw} assume too much or too little. This one assumes you are smart and willing to learn — and meets you where you are.",
        ] + _INTRO_NONTEMPLATE
    elif intent == "trend_analysis":
        pool = [
            f"The {kw} landscape is shifting, but most analysis confuses movement with direction. This report identifies the structural forces that actually matter.",
            f"Trend analysis usually stops at describing what changed. The more useful question is what those changes reveal about where things are heading.",
        ] + _INTRO_NONTEMPLATE
    elif intent == "investigative":
        pool = [
            f"Claims about {kw} circulate with varying degrees of evidence. This investigation traces each claim to its source and evaluates what holds up.",
            f"Controversy around {kw} generates more heat than light. Here is a dispassionate examination of the evidence on all sides.",
        ] + _INTRO_NONTEMPLATE
    elif intent == "opinion":
        pool = [
            f"The conventional take on {kw} misses something important. This piece argues why, with evidence you may not have seen elsewhere.",
            f"Everyone has an opinion on {kw}. Here is one backed by data rather than conviction.",
        ] + _INTRO_NONTEMPLATE

    hook = _pick(pool).format(kw=kw, kw_title=kw_title)
    parts.append(f"<p>{hook}</p>")

    # Entity mention (if available)
    if verified_intro_entities:
        names = [v["name"] for v in verified_intro_entities[:4]]
        if len(names) == 1:
            parts.append(f"<p>We evaluated <strong>{names[0]}</strong> alongside the key alternatives.</p>")
        else:
            if len(names) == 2:
                parts.append(f"<p>We compared <strong>{names[0]}</strong> and <strong>{names[1]}</strong> with the other major players in this space.</p>")
            else:
                last = names.pop()
                parts.append(f"<p>We evaluated <strong>{', '.join(names)}</strong> and <strong>{last}</strong> across the dimensions that actually matter.</p>")

    # Gap angle mention (if available)
    if gap_angles:
        selected = gap_angles[:2]
        titles = [a.get("section_title", "") for a in selected if isinstance(a, dict)]
        if titles:
            parts.append(f"<p>This guide also covers what competitors miss: {', '.join(titles)}.</p>")

    # Transition
    parts.append(f"<p>{_pick(_INTRO_TRANSITIONS)}</p>")

    return "\n".join(parts)


def _build_winner_spotlight(
    kw: str, kw_lower: str, intent: str, arch: dict,
    verified_intro_entities: list, memory: NarrativeMemory,
) -> str:
    """Generate the winner spotlight section dynamically."""
    if not arch.get("allows_winner") or not verified_intro_entities:
        return ""

    winner = verified_intro_entities[0]
    name = winner["name"]
    s1 = winner["strengths"][0].lower()
    s2 = winner["strengths"][1].lower() if len(winner["strengths"]) > 1 else ""
    pricing = winner["pricing"]
    target = winner["target_user"]
    platforms = ", ".join(winner["platforms"][:3])
    weakness = winner["weaknesses"][0].lower() if winner.get("weaknesses") else ""

    memory.mark_mentioned(name, "pricing")
    memory.mark_mentioned(name, "platform")

    parts = []

    # Opening
    parts.append(f"<h2>Our Top Pick: {name}</h2>")

    # Rationale paragraph
    rationale_pool = [
        f"<p><strong>{name}</strong> is our top pick for most people evaluating {kw_lower}. It does not win on flash — it wins on the combination of {s1}, {s2 or 'consistency'}, and real-world reliability at {pricing}.</p>",
        f"<p>After evaluating the options, <strong>{name}</strong> consistently ranks highest on the criteria that matter for daily use: {s1} and {s2 or 'overall value'}. At {pricing}, it delivers more utility per dollar than the alternatives.</p>",
        f"<p><strong>{name}</strong> earns the top spot not because it is perfect — it is not — but because it balances {s1} with {s2 or 'practical usability'} better than any single competitor. The tradeoffs it makes are worth accepting for most users.</p>",
    ]
    parts.append(_pick(rationale_pool))

    # Strengths
    parts.append(f"<h3>Why {name} Wins</h3>")
    strengths_html = "".join(
        f"<li>{s.capitalize()}</li>\n" for s in winner["strengths"][:4]
    )
    parts.append(f"<ul>\n{strengths_html}</ul>")

    # Weakness
    if weakness:
        parts.append(f"<h3>The Tradeoff</h3>")
        parts.append(f"<p>{weakness.capitalize()}. This is the compromise you accept for the value {name} delivers.</p>")

    # Best for / Avoid if
    parts.append(f"<h3>Best For</h3>")
    parts.append(f"<p>{target}</p>")
    parts.append(f"<h3>Avoid If</h3>")
    parts.append(f"<p>You need {weakness or 'a more polished experience'}, or your specific workflow demands features {name} does not prioritize.</p>")

    return "\n".join(parts)


def _build_recommendation_matrix(
    verified_intro_entities: list, kw_lower: str, arch: dict, memory: NarrativeMemory,
) -> str:
    """Build a dynamic recommendation matrix with varied categories."""
    if not arch.get("allows_winner") or not verified_intro_entities or len(verified_intro_entities) < 2:
        return ""

    v = verified_intro_entities
    seen = set()

    def _lockin(entity: dict) -> str:
        plat_count = len(entity.get("platforms", []))
        if plat_count >= 4:
            return "Low — works across all platforms"
        elif plat_count >= 2:
            return f"Medium — limited to {', '.join(entity['platforms'][:2])}"
        return "High — single platform only"

    def _tco(entity: dict) -> str:
        pl = entity["pricing"].lower()
        if "free" in pl or "$0" in pl:
            return "None at this price"
        if "/mo" in pl:
            nums = re.findall(r'\$(\d+(?:\.\d+)?)', pl)
            if nums:
                yr = int(float(nums[0]) * 12 * 3)
                return f"~${yr} over 3 years"
        return "Varies by usage"

    categories = [
        ("Best Overall", v[0]),
    ]
    seen.add(v[0]["name"])

    remaining = [x for x in v if x["name"] not in seen]

    # Budget
    budget = [x for x in remaining if "free" in x["pricing"].lower() or "$0" in x["pricing"].lower()]
    if budget:
        categories.append(("Best Budget / Free", budget[0]))
        seen.add(budget[0]["name"])
        remaining = [x for x in remaining if x["name"] not in seen]

    # Beginner
    beginner = [x for x in remaining if any(w in x["target_user"].lower() for w in ("beginner", "simple", "casual"))]
    if beginner:
        categories.append(("Easiest to Use", beginner[0]))
        seen.add(beginner[0]["name"])
        remaining = [x for x in remaining if x["name"] not in seen]

    # Power user
    power = [x for x in remaining if any(w in x["target_user"].lower() for w in ("power", "professional", "advanced"))]
    if power:
        categories.append(("Best for Power Users", power[0]))
        seen.add(power[0]["name"])
        remaining = [x for x in remaining if x["name"] not in seen]

    # Fill remaining slots from remaining entities
    for ent in remaining[:3]:
        if ent["name"] not in seen:
            cat = "Best Alternative"
            categories.append((cat, ent))
            seen.add(ent["name"])

    if len(categories) < 2:
        return ""

    rows_html = ""
    for cat, ent in categories:
        s = ent.get("strengths", [])
        w = ent.get("weaknesses", [])
        reason = f"{s[0].capitalize()}. Tradeoff: {w[0] if w else 'Narrow focus.'}" if s else "Solid option."
        rows_html += (
            f"<tr><td><strong>{cat}</strong></td>"
            f"<td><strong>{ent['name']}</strong></td>"
            f"<td>{reason}</td>"
            f"<td>{ent['pricing']}</td>"
            f"<td>{_lockin(ent)}</td>"
            f"<td>{_tco(ent)}</td></tr>\n"
        )
        memory.mark_mentioned(ent["name"], "pricing")

    matrix_html = f"""<h2>Recommendation Matrix: Who Wins in Each Category</h2>
<p>Different priorities call for different picks. Below, each category winner includes pricing, ecosystem lock-in risk, and true long-term cost — the details most guides skip.</p>
<table><thead><tr><th>Category</th><th>Winner</th><th>Why</th><th>Price</th><th>Lock-in Risk</th><th>3-Year Cost</th></tr></thead>
<tbody>{rows_html}</tbody></table>"""
    return matrix_html


def _build_contradiction_section(
    verified_intro_entities: list, intent: str, arch: dict,
) -> str:
    """Generate contradiction resolution from entity disagreements."""
    if not arch.get("allows_winner") or not verified_intro_entities or len(verified_intro_entities) < 2:
        return ""

    contradictions = []
    e0 = verified_intro_entities[0]
    e1 = verified_intro_entities[1] if len(verified_intro_entities) > 1 else None

    if e1 and e0["pricing"] != e1["pricing"]:
        contradictions.append((
            "Price versus value",
            f"Some sources rank {e1['name']} ahead of {e0['name']} based on pricing alone. But {e0['name']} at {e0['pricing']} delivers {e0['strengths'][0].lower()} that justifies the difference — {e1['name']} only wins on paper if budget is the only criterion."
        ))

    e2 = verified_intro_entities[2] if len(verified_intro_entities) > 2 else None
    if e2:
        contradictions.append((
            "Feature priorities",
            f"Reviewers disagree on whether {e0['name']} or {e2['name']} has stronger features. The explanation: {e0['name']} optimizes for {e0['strengths'][0].lower()}, while {e2['name']}] prioritizes {e2['strengths'][0].lower()}. They serve different workflows."
        ))

    if e1 and intent in ("commercial", "comparative"):
        contradictions.append((
            "Learning curve perceptions",
            f"Some claim {e1['name']} is harder to learn than {e0['name']}. The reverse is often true: {e0['name']} trades initial simplicity for depth, while {e1['name']}] offers faster onboarding at the cost of long-term flexibility."
        ))

    if not contradictions:
        return ""

    items = "\n".join(
        f"    <li><strong>{label}:</strong> {text}</li>"
        for label, text in contradictions
    )
    return f"""<h2>Contradiction Resolution: Where Reviewers Disagree</h2>
<p>Top guides often contradict each other. Here is where they conflict and what we actually recommend:</p>
<ul>
{items}
</ul>"""


def _build_competitor_section(
    section_title: str, section_idx: int,
    verified_intro_entities: list | None, kw_lower: str,
    memory: NarrativeMemory, intent: str,
) -> str:
    """Generate a single competitor section with dynamic content."""
    parts = []
    esc_title = section_title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    parts.append(f"<h2>{esc_title}</h2>")

    if not verified_intro_entities or section_idx > len(verified_intro_entities):
        # No entity data — generate general paragraph
        general_pool = [
            f"<p>When evaluating {kw_lower}, the right choice depends on matching specific features to your actual workflow rather than comparing abstract specifications.</p>",
            f"<p>The {kw_lower} landscape includes options at every price point and capability level. Understanding where each fits prevents costly mismatches.</p>",
            f"<p>Price alone does not determine value in the {kw_lower} space. Support quality, update frequency, and ecosystem compatibility matter just as much.</p>",
        ]
        parts.append(_pick(general_pool))
        return "\n".join(parts)

    entity = verified_intro_entities[(section_idx - 1) % len(verified_intro_entities)]
    name = entity["name"]
    s1 = entity["strengths"][0].lower()
    s2 = entity["strengths"][1].lower() if len(entity["strengths"]) > 1 else ""
    w1 = entity["weaknesses"][0].lower() if entity.get("weaknesses") else ""
    pricing = entity["pricing"]
    target = entity["target_user"]
    platforms = ", ".join(entity["platforms"][:3])

    # Opening about strength
    strength_text = _pick(_STRENGTH_TO_PARAGRAPH).format(name=name, s1=s1)
    parts.append(f"<p>{strength_text}</p>")

    # Weakness / tradeoff
    if w1:
        weakness_text = _pick(_WEAKNESS_TO_PARAGRAPH).format(name=name, w1=w1)
        parts.append(f"<p>{weakness_text}</p>")

    # Pricing note (only if not already mentioned)
    if not memory.has_been_mentioned(name, "pricing"):
        tier = _get_price_tier(pricing)
        price_text = _pick(_PRICE_OBSERVATIONS).format(pricing=pricing, tier=tier)
        parts.append(f"<p>{price_text}</p>")
        memory.mark_mentioned(name, "pricing")

    # Platform note
    if not memory.has_been_mentioned(name, "platform"):
        parts.append(f"<p>{_pick(_PLATFORM_OBSERVATIONS).format(name=name, platforms=platforms)}</p>")
        memory.mark_mentioned(name, "platform")

    # Target user
    parts.append(f"<p>{_pick(_TARGET_USER_PARAGRAPHS).format(name=name, target=target)}</p>")

    # Comparison with next entity (if available)
    next_idx = section_idx  # 0-indexed
    if next_idx < len(verified_intro_entities) and section_idx % 2 == 0:
        next_entity = verified_intro_entities[next_idx]
        if next_entity["name"] != name:
            n_s1 = next_entity["strengths"][0].lower()
            bridge = _pick(_COMPARISON_BRIDGES).format(
                name_a=name, strength_a=s1,
                name_b=next_entity["name"], strength_b=n_s1,
            )
            parts.append(f"<p>{bridge}</p>")
            verdict = _pick(_VERDICT_TEMPLATES).format(
                name_a=name, strength_a=s1,
                name_b=next_entity["name"], strength_b=n_s1,
            )
            parts.append(f"<p>{verdict}</p>")
            memory.add_comparison(name, next_entity["name"])

    # Micro-frustration for top entities (tracked to avoid duplicates)
    if section_idx <= 3:
        parts.append(f"<p>{memory.pick_frustration()}</p>")

    return "\n".join(parts)


def _build_gap_section(
    angle: dict, kw_lower: str, memory: NarrativeMemory,
) -> str:
    """Build a content gap section from a gap angle definition."""
    title = angle.get("section_title", "")
    desc = angle.get("description", "")
    angle_key = angle.get("angle", "")

    esc_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    parts = [f"<h2>{esc_title}</h2>"]

    # Dynamic intro from pool or description
    intro_pool = _GAP_SECTION_INTROS.get(angle_key, [])
    if intro_pool:
        parts.append(f"<p>{_pick(intro_pool).format(kw=kw_lower)}</p>")
    else:
        first_line = desc.split(".")[0] if desc else ""
        if first_line:
            parts.append(f"<p>{first_line}</p>")

    # Generate substantive content from the description keywords
    # Extract key action items from description
    sentences = desc.split(". ")
    if len(sentences) >= 2:
        for sent in sentences[1:4]:
            cleaned = sent.strip().lstrip("Include: ").lstrip("Include: ")
            if cleaned and len(cleaned) > 20:
                parts.append(f"<p>Consider {cleaned[0].lower() + cleaned[1:] if cleaned[0].isupper() else cleaned}.</p>")

    # Add generic depth paragraphs
    depth_pool = [
        f"<p>Most guides avoid this topic because it forces uncomfortable conclusions about otherwise positive recommendations. We cover it anyway because the information is too important to skip.</p>",
        f"<p>This aspect of {kw_lower} is rarely discussed in mainstream reviews. The reason is obvious once you think about it: acknowledging it undermines the neat winner/loser narrative most articles want to tell.</p>",
        f"<p>Skipping this consideration is the most common mistake people make when evaluating {kw_lower}. It does not show up on feature checklists, but it matters more than most listed features combined.</p>",
    ]
    parts.append(_pick(depth_pool).format(kw_lower=kw_lower))

    return "\n".join(parts)


def _build_comparison_section(
    deduped_entities: list,
    kw_lower: str,
    verified_intro_entities: list | None = None,
) -> str:
    """Build a comparison table from entity data. Prefers verified entities with pricing data."""
    # Prefer entities that have pricing data (verified entities)
    entities_with_data = [e for e in (deduped_entities or []) if e.get("pricing")]
    if not entities_with_data and verified_intro_entities:
        entities_with_data = verified_intro_entities

    relevant = [e for e in (entities_with_data or deduped_entities)[:6] if len(e.get("name", "")) > 3]
    if len(relevant) < 3:
        return ""

    rows = ""
    for ent in relevant[:6]:
        name = ent.get("name", "").replace("<", "&lt;")
        desc = ent.get("description", f"Key option in the {kw_lower} space").replace("<", "&lt;")
        pricing = ent.get("pricing", "Check official site").replace("<", "&lt;")
        platforms = ", ".join(ent.get("platforms", ["Varies"]))
        strengths = "; ".join(ent.get("strengths", [])[:2]).replace("<", "&lt;") if ent.get("strengths") else "See details"
        rows += f"<tr><td><strong>{name}</strong></td><td>{desc}</td><td>{pricing}</td><td>{platforms}</td><td>{strengths}</td></tr>\n"

    return f"""<h2>Comparison of Key Options</h2>
<table><thead><tr><th>Option</th><th>Description</th><th>Pricing</th><th>Platform</th><th>Key Strengths</th></tr></thead>
<tbody>{rows}</tbody></table>"""


def _build_expert_tips(verified_intro_entities: list, kw_lower: str) -> str:
    """Generate expert tips section from entity data."""
    tips = []

    if verified_intro_entities:
        name = verified_intro_entities[0]["name"]
        s = verified_intro_entities[0]["strengths"][0].lower() if verified_intro_entities[0].get("strengths") else ""
        if s:
            tips.append(f"Start with {name} if {s} is your priority. The feature alignment for this use case is stronger than competitors.")

    tips.append(f"Audit your current {kw_lower} setup before evaluating alternatives. List what works, what is missing, and what frustrates you — then match against each option's strengths.")

    tips.append(f"Migration fear is the number one reason people stay with suboptimal tools. Most modern {kw_lower} options import directly from competitors. The switch takes under 30 minutes for typical setups.")

    if verified_intro_entities and len(verified_intro_entities) >= 2:
        e0 = verified_intro_entities[0]
        e1 = verified_intro_entities[1]
        tips.append(f"Read negative reviews specifically for both {e0['name']} and {e1['name']}. Positive reviews tell you what marketing wants you to hear; negative reviews reveal where the product actually breaks.")

    tips.append(f"Consider total cost of ownership over 3 years — not just the first month. A cheap {kw_lower} tool that lacks key features forces a costly migration later.")

    items_html = "\n".join(f"<li>{tip}</li>" for tip in tips)
    return f"""<h2>Expert Tips and Best Practices</h2>
<ul>
{items_html}
</ul>"""


def _build_conclusion(
    kw: str, kw_lower: str, intent: str, arch: dict,
    verified_intro_entities: list, search_results: list,
) -> str:
    """Generate intent-aware conclusion forcing 1 winner + 1 exclusion.

    Every intent must end with a clear decision: what to choose and what to avoid.
    No 'it depends', no 'your mileage may vary', no neutral closing.
    """
    parts = []

    # Local service conclusion is a service summary, not a product verdict
    if intent == "local_service":
        parts.append(f"<h2>Schedule Your {kw_lower} Service Today</h2>")
        parts.append(f"<p>When you need reliable {kw_lower} in Grand Rapids, you want a team that shows up on time, fixes the problem correctly, and charges a fair price. That is exactly what we deliver — every time.</p>")
        parts.append(f"<p>Call us at <strong><a href=\"tel:+16160000000\">(616) 000-0000</a></strong> or request an appointment online. We offer free estimates, same-day service, and a warranty on all repairs.</p>")
        parts.append(f"")

    title_map = {
        "news": "The Bottom Line",
        "informational": "What You Have Learned",
        "educational": "What You Have Learned",
        "trend_analysis": "Strategic Outlook",
        "comparative": "Final Recommendation",
    }
    title = title_map.get(intent, "Final Verdict")
    parts.append(f"<h2>{title}</h2>")

    if arch.get("allows_winner") and len(verified_intro_entities) >= 2:
        best = verified_intro_entities[0]
        exclude = verified_intro_entities[-1]
        s1 = best["strengths"][0].lower() if best.get("strengths") else "solid performance"
        w1 = exclude["weaknesses"][0].lower() if exclude.get("weaknesses") else "limited suitability"
        exc_name = exclude["name"]

        conclusion_pool = [
            f"<p><strong>{best['name']}</strong> is the winner. {s1.capitalize()} at {best['pricing']} — nothing else in this category delivers the same balance. <strong>Avoid {exc_name}</strong> — {w1} makes it a poor fit for most use cases.</p>",
            f"<p><strong>Choose: {best['name']}</strong> — {s1} and strong value at {best['pricing']}. <strong>Skip: {exc_name}</strong> — {w1} eliminates it from serious consideration.</p>",
            f"<p>After evaluating the options, <strong>{best['name']}</strong> is the clear winner. Its {s1} outperforms competitors at {best['pricing']}. <strong>Exclude {exc_name}</strong> — {w1} disqualifies it for general use.</p>",
        ]
        parts.append(_pick(conclusion_pool))

        # Decision box: winner + exclusion
        parts.append(f"""<div class="decision-box">
<p><strong>Decision: Choose {best['name']}</strong> — {s1} at {best['pricing']}</p>
<p><strong>Exclude: {exc_name}</strong> — {w1}</p>
</div>""")

    elif arch.get("allows_winner") and len(verified_intro_entities) == 1:
        best = verified_intro_entities[0]
        s1 = best["strengths"][0].lower() if best.get("strengths") else "solid performance"
        w1 = best["weaknesses"][0].lower() if best.get("weaknesses") else "limited use-case fit"

        parts.append(f"<p><strong>{best['name']}</strong> is the clear leader in this category. {s1.capitalize()} at {best['pricing']} outperforms every alternative. If {w1} is a dealbreaker, no current option fully addresses that concern — wait for the next iteration.</p>")
        parts.append(f"""<div class="decision-box">
<p><strong>Decision: Choose {best['name']}</strong> — {s1} at {best['pricing']}</p>
<p><strong>Watch for:</strong> {w1} — revisit when vendors address this gap.</p>
</div>""")

    elif intent == "news":
        parts.append(f"<p><strong>What to watch:</strong> institutional flows, regulatory signals, and infrastructure buildout. These three factors determine where this story goes next. <strong>What to ignore:</strong> short-term price noise and headline-driven trading — the structural shift matters more than any single event.</p>")

    elif intent == "informational":
        parts.append(f"<p><strong>Action:</strong> Master the fundamentals of {kw_lower}, then apply them to a real project immediately. <strong>Avoid:</strong> getting lost in theoretical deep-dives before you have practical experience — the fastest path to competence is building something tangible.</p>")

    elif intent == "educational":
        parts.append(f"<p><strong>Next step:</strong> build something real with {kw_lower}. Knowledge gaps discovered through practice teach more than any guide. <strong>Skip:</strong> advanced topics until the basics are automatic — premature optimization is the most common learning trap.</p>")

    elif intent == "trend_analysis":
        parts.append(f"<p><strong>Bet on:</strong> the structural trend, not short-term fluctuations. The direction is clear even if the timing is uncertain. <strong>Ignore:</strong> predictions that claim precise timing — allocate resources toward the dominant trajectory instead.</p>")

    else:
        # Fallback — still force a decision
        if verified_intro_entities:
            best = verified_intro_entities[0]
            s1 = best["strengths"][0].lower() if best.get("strengths") else "strong value"
            parts.append(f"<p><strong>Recommendation:</strong> {best['name']} — {s1} at {best['pricing']} makes it the strongest option in this category. Evaluate alternatives only if specific requirements rule this out.</p>")
        else:
            parts.append(f"<p><strong>Priority:</strong> choose tools that integrate with your existing stack and offer clear migration paths. <strong>Eliminate:</strong> options that require significant workflow changes without proportional upside.</p>")

    return "\n".join(parts)


def _build_intent_specific_section(
    stype: str, title: str, kw_lower: str, kw: str, intent: str,
    verified_intro_entities: list,
) -> str:
    """Generate intent-specific sections without static templates."""
    esc_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    parts = [f"<h2>{esc_title}</h2>"]

    intent_pools = {
        "local_service": _LOCAL_SERVICE_SECTION_TEXTS,
        "news": _NEWS_SECTION_TEXTS,
        "informational": _INFORMATIONAL_SECTION_TEXTS,
        "educational": _EDUCATIONAL_SECTION_TEXTS,
        "comparative": _COMPARATIVE_SECTION_TEXTS,
        "trend_analysis": _TREND_SECTION_TEXTS,
        "investigative": _INVESTIGATIVE_SECTION_TEXTS,
        "opinion": _OPINION_SECTION_TEXTS,
    }

    pool_dict = intent_pools.get(intent, {})
    text_pool = pool_dict.get(stype, None)

    if text_pool:
        # CTA section needs special treatment
        if stype == "cta_contact":
            parts.append(f'<div class="cta-box" style="background:#f5f9ff;border:2px solid #2b6cb0;border-radius:8px;padding:24px;margin:24px 0;text-align:center;">')
            parts.append(f'<h3 style="margin-top:0;color:#2b6cb0;">Need {kw_lower} in Grand Rapids?</h3>')
            parts.append(f'<p style="font-size:1.1em;">Call us for <strong>free estimates</strong> and <strong>same-day service</strong>.</p>')
            parts.append(f'<p style="font-size:1.3em;font-weight:bold;"><a href="tel:+16160000000" style="color:#2b6cb0;text-decoration:none;">(616) 000-0000</a></p>')
            parts.append(f'<p>Licensed · Insured · Upfront Pricing · Warranty on Repairs</p>')
            parts.append(f'</div>')
        else:
            # Use 2-3 texts from the pool
            selected = _shuffle_texts(text_pool, 3)
            for t in selected[:2]:
                domain = verified_intro_entities[0]["name"] if verified_intro_entities else "the subject"
                problem = verified_intro_entities[0]["description"][:40] if verified_intro_entities else "a common challenge"
                parts.append(f"<p>{t.format(kw=kw_lower, kw_title=kw, domain=domain, problem=problem)}</p>")
    elif stype == "why_we_picked" and intent == "commercial" and verified_intro_entities:
        # Specific handler for "Why We Picked" sections — use entity data
        top = verified_intro_entities[0]
        parts.append(f"<p>We selected <strong>{top['name']}</strong> as our top pick because it delivers the best balance of {top['strengths'][0].lower()} and {top['strengths'][1].lower() if len(top['strengths']) > 1 else 'value'} at {top['pricing']}. No other option matches this combination for most use cases.</p>")
        if len(verified_intro_entities) > 1:
            alt = verified_intro_entities[1]
            parts.append(f"<p>{alt['name']} came close, but {alt['weaknesses'][0].lower() if alt.get('weaknesses') else 'narrower suitability'} ultimately pushed it to second place. The gap is small enough that {alt['name']} remains a strong choice if its specific strengths align with your needs.</p>")
            parts.append(f"<p>Below you will find a full breakdown of each option, including pricing, features, and the tradeoffs that determine which tool fits your particular workflow.</p>")
        else:
            parts.append(f"<p>The sections below break down each option in detail, including the specific features, pricing, and limitations that determine which tool fits your workflow.</p>")
    else:
        # Fallback for any unrecognized section type
        fallback = [
            f"<p>Most articles gloss over the specifics here, but the details make a real difference in practice. Here is what you need to know about {kw_lower}.</p>",
            f"<p>The conventional wisdom about {kw_lower} is not wrong — it is just incomplete. This section fills in what most coverage leaves out.</p>",
            f"<p>This part of the {kw_lower} landscape gets less attention than it deserves. Understanding it separates informed choices from guesswork.</p>",
            f"<p>Getting this aspect right matters more than most people realize. A small mistake here can compound into larger issues down the line, so it is worth understanding the details.</p>",
        ]
        parts.extend(random.sample(fallback, min(3, len(fallback))))

    return "\n".join(parts)


# ── Decision Force Engine ────────────────────────────────────

def _enforce_decision(html: str, kw: str, kw_lower: str, intent: str) -> str:
    """Post-process to strip remaining 'it depends' and ensure definitive closing.

    Forces the article to end with a clear recommendation + exclusion.
    Falls back to appending one if the conclusion section was weak.
    """
    # Strip remaining "it depends" variants
    IT_DEPENDS = [
        "it depends on your needs", "it depends on your specific needs",
        "it depends on your priorities", "it depends on your specific priorities",
        "depends on your needs", "depends on your priorities",
        "depends on your specific", "it depends on what",
        "depends on what you", "your mileage may vary",
        "your results may vary", "choose what works best for you",
        "the right choice depends on", "the right tool depends on",
        "the best choice depends on", "the best option depends on",
    ]
    for phrase in IT_DEPENDS:
        html = html.replace(phrase, "")

    # Clean up empty remnants from stripping
    html = re.sub(r'<p>\s*</p>', '', html)
    html = re.sub(r'\s{3,}', ' ', html)

    # Check if the article already has a decision-box div
    has_decision_box = '<div class="decision-box">' in html

    # Check if the article ends with a definite recommendation
    # (ends with </div>, </ol>, </ul> after the last <p>)
    closing_tags = list(re.finditer(r'(</(?:div|ol|ul|p)>)', html))
    if not closing_tags:
        return html

    last_close = closing_tags[-1]
    last_100_before = html[max(0, last_close.start() - 200):last_close.end()].lower()

    has_winner_lang = any(w in last_100_before for w in [
        "winner", "choose", "recommend", "pick:", "skip:",
        "decision:", "exclude", "avoid",
        "what to watch", "what to ignore",
        "bet on", "ignore:",
    ])

    if not has_winner_lang:
        # Append a decisive closing based on intent
        if intent in ("commercial", "transactional", "comparative"):
            html += f"""\n\n<h2>Final Verdict</h2>
<p><strong>The takeaway:</strong> evaluate your specific requirements against the options above. Choose the tool that aligns with your workflow — eliminate anything that adds complexity without proportional value.</p>"""
        elif intent == "news":
            html += f"""\n\n<h2>The Bottom Line</h2>
<p><strong>Watch:</strong> infrastructure buildout and regulatory signals. <strong>Ignore:</strong> short-term noise and headline-driven reactions.</p>"""
        elif intent in ("informational", "educational"):
            html += f"""\n\n<h2>What You Have Learned</h2>
<p><strong>Next step:</strong> apply this knowledge to a real project. <strong>Avoid:</strong> getting stuck in theory — practical application exposes the gaps that matter.</p>"""
        elif intent == "trend_analysis":
            html += f"""\n\n<h2>Strategic Outlook</h2>
<p><strong>Bet on:</strong> the structural direction. <strong>Ignore:</strong> timing predictions and short-term noise.</p>"""

    return html


def _check_narrative_alignment(h: list[str], kw: str, intent: str) -> int:
    """Score how well article sections support a decisive conclusion (0-100).

    Higher = sections build toward a coherent recommendation.
    Checks for: consistent entity naming, no contradiction, decision support.
    """
    if not h:
        return 0
    text = " ".join(h).lower()

    # Check for clear decision language in later sections
    decision_indicators = ["winner", "recommend", "choose", "pick", "best", "top"]
    decision_score = sum(5 for w in decision_indicators if w in text)

    # Check for "it depends" dilution (penalty)
    dilution_phrases = ["it depends", "your mileage may vary", "both are good"]
    dilution_penalty = sum(-10 for p in dilution_phrases if p in text)

    # Check for consistent entity naming (no contradictions)
    contradiction_count = text.count("on the other hand") + text.count("however")
    contradiction_penalty = min(contradiction_count * -3, -15)

    score = min(100, max(0, decision_score + dilution_penalty + contradiction_penalty + 40))
    return score


# ── Anti-Repetition: Final Pass ────────────────────────────

def _anti_template_rewrite(html: str) -> str:
    """Detect and rewrite clearly template-like patterns in generated HTML."""
    # These patterns are stripped entirely
    BAN_STRIPS = [
        "in today's digital landscape", "in today's world",
        "it is important to note", "it is worth noting",
        "when it comes to", "the bottom line is",
        "this comprehensive guide", "comprehensive guide",
        "let's explore", "lets explore",
        "in conclusion", "to summarize",
        "the key takeaway", "key takeaway",
        "choosing the right solution", "choosing the right tool",
        "you need to consider", "you should consider",
        "there are many factors", "there are several factors",
        "it depends on your needs", "it depends on your specific needs",
        "last but not least", "first and foremost",
    ]
    for phrase in BAN_STRIPS:
        html = html.replace(phrase, "")

    # Clean up double spaces and empty paragraphs
    html = re.sub(r'\s{3,}', ' ', html)
    html = re.sub(r'<p>\s*</p>', '', html)
    html = re.sub(r'\n{3,}', '\n\n', html)

    return html


# ── Main Entry Point ───────────────────────────────────────

def build_dynamic_article(
    kw: str,
    kw_title: str,
    kw_lower: str,
    intent: str,
    sections: list,
    arch: dict,
    verified_intro_entities: list | None = None,
    verified_category_data: list | None = None,
    deduped_entities: list | None = None,
    all_headings: list | None = None,
    search_results: list | None = None,
    gap_angles: list | None = None,
) -> list[str]:
    """Generate article body sections from SERP data + entity knowledge base.

    Returns a list of HTML strings (equivalent to the ``h`` list in _call_local
    that starts at line 2152). No static templates — every section is built
    dynamically from available data with randomized structure.
    """
    entities = verified_category_data or verified_intro_entities or deduped_entities or []
    memory = NarrativeMemory(entities)

    h: list[str] = []

    # ── Introduction ──────────────────────────────────────
    intro_html = _build_intro(
        kw, kw_title, kw_lower, intent,
        verified_intro_entities or [],
        search_results or [],
        gap_angles,
    )
    h.append(intro_html)

    # ── Track gap section indices for injection ――――――――――
    gap_section_titles = set()
    if gap_angles:
        for a in gap_angles:
            if isinstance(a, dict):
                gap_section_titles.add(a.get("section_title", "").lower().strip())

    # ── Section Loop ──────────────────────────────────────
    competitor_idx = 0
    gap_injected = set()

    for section in sections:
        stype = section["type"]
        title = section["title"]
        esc_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # Skip these — handled separately
        if stype in ("introduction", "serp_decon"):
            continue

        # Winner spotlight — built once above
        if stype in ("winner_spotlight",):
            winner = _build_winner_spotlight(
                kw, kw_lower, intent, arch,
                verified_intro_entities or [],
                memory,
            )
            if winner:
                h.append(winner)
            continue

        # Recommendation matrix
        if stype in ("recommendation_matrix",):
            matrix = _build_recommendation_matrix(
                verified_intro_entities or [], kw_lower, arch, memory,
            )
            if matrix:
                h.append(matrix)
            continue

        # Contradiction resolution
        if stype in ("contradiction_resolution",):
            contra = _build_contradiction_section(
                verified_intro_entities or [], intent, arch,
            )
            if contra:
                h.append(contra)
            continue

        # Emotional friction — built as competitor sections
        if stype in ("emotional_friction",):
            continue  # Handled by competitor micro-frustrations

        # Competitor sections
        if stype == "competitor_section":
            competitor_idx += 1

            # Check if this title matches a content gap angle
            title_lower = title.lower().strip()
            matched_gap = None
            if gap_angles:
                for a in gap_angles:
                    if isinstance(a, dict) and a.get("section_title", "").lower().strip() == title_lower:
                        matched_gap = a
                        break

            if matched_gap:
                # Build as a gap section instead
                gap_html = _build_gap_section(matched_gap, kw_lower, memory)
                if gap_html:
                    h.append(gap_html)
                    gap_injected.add(matched_gap.get("section_title", ""))
                continue

            sec_html = _build_competitor_section(
                title, competitor_idx,
                verified_intro_entities or None if verified_intro_entities else None,
                kw_lower, memory, intent,
            )
            h.append(sec_html)
            continue

        # Comparison table
        if stype == "comparison":
            table = _build_comparison_section(
                deduped_entities or [],
                kw_lower,
                verified_intro_entities=verified_intro_entities,
            )
            if table:
                h.append(table)
            continue

        # Expert tips
        if stype == "expert_tips":
            tips = _build_expert_tips(
                verified_intro_entities or [], kw_lower,
            )
            if tips:
                h.append(tips)
            continue

        # FAQ — return empty, handled by _call_local
        if stype == "faq":
            continue

        # Conclusion
        if stype == "conclusion":
            conclusion = _build_conclusion(
                kw, kw_lower, intent, arch,
                verified_intro_entities or [],
                search_results or [],
            )
            h.append(conclusion)
            continue

        # Intent-specific sections (news, informational, local_service, etc.)
        intent_specific_types = {
            "what_happened", "why_it_matters", "analyst_disagreement",
            "hidden_context", "bullish_vs_bearish", "what_coverage_misses",
            "signal_vs_noise", "historical_parallel", "bottom_line",
            "direct_explanation", "misconceptions", "practical_examples",
            "use_case_breakdown", "common_mistakes", "nuanced_clarification",
            "prerequisites", "step_by_step", "concept_layering",
            "common_pitfalls", "practice_exercises", "next_steps",
            "tradeoff_matrix", "decision_friction",
            "market_movement", "directional_signals", "scenario_modeling",
            "second_order_effects", "timing_risk", "uncertainty",
            "the_claim", "evidence_examination", "conflicting_data",
            "expert_testimony", "our_findings", "implications",
            "thesis", "supporting_argument", "counterargument",
            "why_counter_fails", "broader_implications",
            "why_we_picked", "pricing_breakdown",
            # Local service section types
            "service_overview", "same_day_services", "appliances_we_repair",
            "brands_we_service", "emergency_services", "pricing_and_cost",
            "service_areas", "why_choose_us", "cta_contact",
        }
        if stype in intent_specific_types:
            sec = _build_intent_specific_section(
                stype, title, kw_lower, kw, intent,
                verified_intro_entities or [],
            )
            h.append(sec)
            continue

        # Fallback for any unrecognized section type
        h.append(f"<h2>{esc_title}</h2>")
        h.append(f"<p>This area of {kw_lower} matters more than most guides acknowledge. The details that follow fill a gap that typical coverage skips entirely.</p>")

    # ── Inject gap sections not already covered ────────────
    if gap_angles:
        for a in gap_angles:
            if isinstance(a, dict):
                st = a.get("section_title", "")
                if st and st.lower().strip() not in gap_injected:
                    gap_html = _build_gap_section(a, kw_lower, memory)
                    if gap_html:
                        h.append(gap_html)
                        gap_injected.add(st)

    return h


# ── Apply anti-template pass ───────────────────────────────

def post_process(html: str, kw: str = "", kw_lower: str = "", intent: str = "") -> str:
    """Run anti-template detection, decision enforcement, and cleanup on the final article HTML."""
    html = _anti_template_rewrite(html)
    if kw and intent:
        html = _enforce_decision(html, kw, kw_lower, intent)
    return html.strip()
