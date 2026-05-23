"""
page_blueprints.py — Structural Diversity Layer

Each page blueprint defines a different section ordering, CTA placement,
FAQ count, and content rhythm. This prevents Google from seeing a
uniform "doorway" pattern across all 920+ pages.

Usage:
    from page_blueprints import pick_blueprint, SECTION_RENDERERS
    bp = pick_blueprint(service, city, modifier)
    html = render_blueprint(bp, context)
"""

import hashlib
import logging
from typing import Any, Callable

log = logging.getLogger("page_blueprints")

# ──────────────────────────────────────────────
# SECTION DEFINITIONS
# ──────────────────────────────────────────────
# Each blueprint is a dict with:
#   "sections": ordered list of section keys
#   "cta_after": render CTA after this section (-1 = end)
#   "faq_count": how many FAQs to show
#   "review_count": how many reviews to show
#   "show_pricing": whether to include pricing table
#   "show_brands": whether to include brands section
#   "show_areas": whether to include areas-served section
#   "show_neighborhoods": whether to expand neighborhoods
#   "brand_para_variant": which brand paragraph template to use
#   "service_item_count": how many service items to show
#   "intro_variant": which intro style (0=tight, 1=expanded)

BLUEPRINT_DEFAULT = {
    "sections": ["intro", "areas", "services", "why_us", "brands", "reviews", "faq", "cta", "contact"],
    "cta_after": -1,
    "faq_count": 6,
    "review_count": 3,
    "show_pricing": False,
    "show_brands": True,
    "show_areas": True,
    "show_neighborhoods": True,
    "brand_para_variant": 0,
    "service_item_count": 6,
    "intro_variant": 0,
}

PAGE_BLUEPRINTS: dict[str, dict[str, Any]] = {
    # ── Blueprint 0: Standard ──
    # Balanced, all sections, CTA at bottom, moderate FAQ
    "standard": {
        "sections": ["intro", "areas", "services", "why_us", "brands", "reviews", "faq", "cta", "contact"],
        "cta_after": -1,
        "faq_count": 6,
        "review_count": 3,
        "show_pricing": False,
        "show_brands": True,
        "show_areas": True,
        "show_neighborhoods": True,
        "brand_para_variant": 0,
        "service_item_count": 6,
        "intro_variant": 0,
    },
    # ── Blueprint 1: Pricing-First ──
    # Pricing table early, reviews light, CTA mid-page
    "pricing_first": {
        "sections": ["intro", "pricing", "areas", "why_us", "services", "brands", "faq", "cta", "contact"],
        "cta_after": 3,
        "faq_count": 5,
        "review_count": 2,
        "show_pricing": True,
        "show_brands": True,
        "show_areas": True,
        "show_neighborhoods": True,
        "brand_para_variant": 1,
        "service_item_count": 5,
        "intro_variant": 1,
    },
    # ── Blueprint 2: FAQ-Heavy ──
    # FAQs early, reviews prominent, CTA after reviews
    "faq_heavy": {
        "sections": ["intro", "services", "faq", "why_us", "reviews", "brands", "cta", "pricing", "contact"],
        "cta_after": 5,
        "faq_count": 8,
        "review_count": 4,
        "show_pricing": True,
        "show_brands": True,
        "show_areas": True,
        "show_neighborhoods": True,
        "brand_para_variant": 2,
        "service_item_count": 4,
        "intro_variant": 2,
    },
    # ── Blueprint 3: Review-Centric ──
    # Reviews at top, FAQ minimal, CTA at end
    "review_centric": {
        "sections": ["intro", "reviews", "services", "why_us", "areas", "faq", "brands", "cta", "contact"],
        "cta_after": -1,
        "faq_count": 4,
        "review_count": 4,
        "show_pricing": False,
        "show_brands": True,
        "show_areas": True,
        "show_neighborhoods": True,
        "brand_para_variant": 3,
        "service_item_count": 7,
        "intro_variant": 3,
    },
    # ── Blueprint 4: Minimal ──
    # Short, direct, less sections, quick-read
    "minimal": {
        "sections": ["intro", "services", "why_us", "faq", "cta", "contact"],
        "cta_after": -1,
        "faq_count": 3,
        "review_count": 2,
        "show_pricing": False,
        "show_brands": False,
        "show_areas": False,
        "show_neighborhoods": False,
        "brand_para_variant": 0,
        "service_item_count": 4,
        "intro_variant": 4,
    },
    # ── Blueprint 5: Authority ──
    # Trust, licenses, certifications prominent
    "authority": {
        "sections": ["intro", "why_us", "areas", "services", "brands", "reviews", "faq", "cta", "contact"],
        "cta_after": 4,
        "faq_count": 6,
        "review_count": 3,
        "show_pricing": True,
        "show_brands": True,
        "show_areas": True,
        "show_neighborhoods": True,
        "brand_para_variant": 1,
        "service_item_count": 5,
        "intro_variant": 1,
    },
    # ── Blueprint 6: Comparison ──
    # Side-by-side, pros/cons structure
    "comparison": {
        "sections": ["intro", "pricing", "why_us", "services", "faq", "brands", "reviews", "cta", "contact"],
        "cta_after": 6,
        "faq_count": 4,
        "review_count": 3,
        "show_pricing": True,
        "show_brands": True,
        "show_areas": True,
        "show_neighborhoods": True,
        "brand_para_variant": 2,
        "service_item_count": 8,
        "intro_variant": 2,
    },
    # ── Blueprint 7: Urgency ──
    # Emergency/24-hour focused, short FAQ, CTA early
    "urgency": {
        "sections": ["intro", "why_us", "cta", "services", "reviews", "faq", "brands", "contact"],
        "cta_after": 2,
        "faq_count": 4,
        "review_count": 2,
        "show_pricing": False,
        "show_brands": False,
        "show_areas": True,
        "show_neighborhoods": False,
        "brand_para_variant": 3,
        "service_item_count": 5,
        "intro_variant": 3,
    },
}

BLUEPRINT_NAMES = list(PAGE_BLUEPRINTS.keys())


# ──────────────────────────────────────────────
# DETERMINISTIC BLUEPRINT SELECTION
# ──────────────────────────────────────────────

def pick_blueprint(service: str, city: str, modifier: str) -> dict[str, Any]:
    """Pick a page blueprint deterministically from service+city+modifier."""
    seed = f"{service}:{city}:{modifier}"
    h = hashlib.md5(seed.encode()).hexdigest()
    idx = int(h[:8], 16) % len(BLUEPRINT_NAMES)
    name = BLUEPRINT_NAMES[idx]
    bp = dict(PAGE_BLUEPRINTS[name])
    bp["_name"] = name
    log.debug("Blueprint %s for %s × %s × %s", name, service, city, modifier)
    return bp


def pick_section_variant(section_key: str, seed_str: str, variants: list[str]) -> str:
    """Pick a section rendering variant deterministically."""
    h = hashlib.md5(f"{section_key}:{seed_str}".encode()).hexdigest()
    idx = int(h[:8], 16) % len(variants)
    return variants[idx]


# ──────────────────────────────────────────────
# SECTION RENDERERS — each returns HTML string
# ──────────────────────────────────────────────

def render_intro(service: str, city: str, modifier: str, blueprint: dict) -> str:
    """Render the intro paragraph, varied by blueprint intro_variant."""
    mod_label = modifier.replace("-", " ").title()
    variants = [
        # variant 0: standard
        f"<p>Looking for {mod_label.lower()} {service} in {city}? Our experienced team has been serving {city} and all of West Michigan since 2015. We provide licensed, insured {service} with upfront pricing and a satisfaction guarantee on every job.</p>",
        # variant 1: direct
        f"<p>Need {mod_label.lower()} {service} in {city}? We're a locally owned company with certified technicians ready to help. Same-day service available across all {city} neighborhoods and surrounding communities.</p>",
        # variant 2: trust
        f"<p>When you need {mod_label.lower()} {service} in {city}, you want someone reliable. Our licensed professionals have served thousands of West Michigan homeowners since 2015 with quality workmanship and transparent pricing.</p>",
        # variant 3: urgent
        f"<p>If you're searching for {mod_label.lower()} {service} in {city}, you've come to the right place. We respond fast, arrive on time, and get the job done right the first time. Fully licensed and insured.</p>",
        # variant 4: local
        f"<p>For {mod_label.lower()} {service} in {city}, trust the local experts. Our Grand Rapids-based team knows the area, understands local building codes, and is committed to keeping your home running smoothly.</p>",
    ]
    idx = min(blueprint.get("intro_variant", 0), len(variants) - 1)
    return variants[idx]


def render_services_html(service: str, blueprint: dict) -> str:
    """Render a service items list, varying count per blueprint."""
    from local_intelligence import NICHE_PROFILES
    profile = NICHE_PROFILES.get(service, {})
    items = profile.get("service_items", [])
    count = min(blueprint.get("service_item_count", 5), len(items))
    if not items or count == 0:
        return ""
    rows = "\n".join(f"            <li><p>{item}</p></li>" for item in items[:count])
    return f"""        <h2>Our {service.title()} Services in Grand Rapids</h2>
        <ul>
{rows}
        </ul>"""


def render_brands_html(service: str, blueprint: dict) -> str:
    """Render a brands section with varied paragraph."""
    from local_intelligence import NICHE_PROFILES
    profile = NICHE_PROFILES.get(service, {})
    brands = profile.get("brands", [])
    if not brands or not blueprint.get("show_brands", True):
        return ""
    brands_str = ", ".join(brands)

    brand_templates = [
        f"<p>We work with all leading brands including {brands_str}. No matter what brand you own, our technicians have the training and parts to get it working again.</p>",
        f"<p>Our technicians are factory-trained and certified on all major brands including {brands_str}. We carry common parts and can order specialized components quickly for faster repairs.</p>",
        f"<p>From {brands_str} — we service them all. Our technicians stay current with the latest models and technology through ongoing manufacturer training programs.</p>",
        f"<p>We're proud to work with trusted brands like {brands_str}. Every brand comes with its own quirks, and our team knows them inside and out from years of hands-on experience.</p>",
    ]
    variant = min(blueprint.get("brand_para_variant", 0), len(brand_templates) - 1)
    return f"""        <h2>Brands We Work With for {service.title()} in Grand Rapids</h2>
{brand_templates[variant]}"""


def render_why_us_html(service: str, city: str) -> str:
    """Render a Why Choose Us section."""
    benefits = [
        f"Licensed and insured in Michigan — full protection for you and your home",
        f"Same-day service available across all {city} neighborhoods and surrounding communities",
        f"Upfront pricing — no hidden fees, no surprises, no overtime charges",
        f"Serving West Michigan since 2015 with thousands of satisfied customers",
        f"Quality workmanship backed by our satisfaction guarantee",
    ]
    return f"""        <h2>Why Choose Us for {service.title()} in {city}</h2>
        <p>When you choose Grand Rapids Home Services for your {service} needs, you get:</p>
        <ul>
{"".join(f'<li>{b}</li>' for b in benefits)}
        </ul>"""


def render_cta_html(service: str, city: str) -> str:
    """Render a CTA section."""
    from local_intelligence import BUSINESS_IDENTITY
    nap = BUSINESS_IDENTITY
    return f"""        <div class="cta-section" style="background:#f0f7ff;border:2px solid #2b6cb0;border-radius:8px;padding:20px;margin:20px 0;text-align:center;">
            <h3>Ready to Get Started? Call Us Now</h3>
            <p style="font-size:1.2em;"><a href="tel:{nap['phone_link']}" style="color:#2b6cb0;font-weight:bold;">{nap['phone']}</a></p>
            <p>Free estimates · Licensed technicians · Upfront pricing · Satisfaction guaranteed</p>
        </div>"""


def render_contact_html() -> str:
    """Render a contact section."""
    from local_intelligence import BUSINESS_IDENTITY
    biz = BUSINESS_IDENTITY
    return f"""        <h2>Contact Us</h2>
        <p>Call <strong>{biz['phone']}</strong> or email <strong>{biz['email']}</strong>.</p>
        <p>{biz['address']}, {biz['city']}, {biz['state']} {biz['zip']}</p>
        <p>Hours: Mon-Fri 7:00 AM - 7:00 PM · Sat 8:00 AM - 5:00 PM · Emergency 24/7</p>"""


# Section renderer registry
SECTION_RENDERERS: dict[str, Callable[..., str]] = {
    "intro": lambda ctx: render_intro(ctx["service"], ctx["city"], ctx["modifier"], ctx["blueprint"]),
    "services": lambda ctx: render_services_html(ctx["service"], ctx["blueprint"]),
    "brands": lambda ctx: render_brands_html(ctx["service"], ctx["blueprint"]),
    "why_us": lambda ctx: render_why_us_html(ctx["service"], ctx["city"]),
    "cta": lambda ctx: render_cta_html(ctx["service"], ctx["city"]),
    "contact": lambda ctx: render_contact_html(),
}


def render_blueprint(blueprint: dict, context: dict) -> str:
    """Render a complete blueprint into HTML sections.

    Context dict must include:
        service, city, modifier, keyword, slug, keyword_title
    Optional: areas_html, pricing_html, reviews_html, faq_html (pre-rendered)
    """
    sections_html = []
    for i, section_key in enumerate(blueprint["sections"]):
        # Check if context has pre-rendered HTML for this section
        ctx_key = f"{section_key}_html"
        if ctx_key in context and context[ctx_key]:
            sections_html.append(context[ctx_key])
        elif section_key in SECTION_RENDERERS:
            sections_html.append(SECTION_RENDERERS[section_key](context))

        # Inject CTA mid-page if blueprint says to place it after this section
        cta_after = blueprint.get("cta_after", -1)
        if cta_after >= 0 and i == cta_after:
            sections_html.append(SECTION_RENDERERS["cta"](context))

    # CTA at end if not placed mid-page
    if blueprint.get("cta_after", -1) < 0:
        sections_html.append(SECTION_RENDERERS["cta"](context))

    return "\n".join(sections_html)
