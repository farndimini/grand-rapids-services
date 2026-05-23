"""
programmatic_expander.py — Programmatic SEO Page Expander

Generates a service × city × modifier matrix of unique localized pages.
Every page is differentiated by intro, FAQ, reviews, CTA, landmarks,
neighborhoods, ZIP codes, urgency framing, and internal links.

Usage:
    from programmatic_expander import generate_batch
    pages = generate_batch(limit=25)
"""

import json
import logging
import os
import random
import re
from datetime import datetime
from typing import Any

from local_intelligence import (
    BUSINESS_IDENTITY,
    GRAND_RAPIDS,
    LANDMARKS,
    MAJOR_HIGHWAYS,
    NEIGHBORHOODS,
    NEIGHBORHOOD_METADATA,
    NICHE_METADATA,
    NICHE_PROFILES,
    REVIEWS,
    SUBURBS,
    ZIP_CODES,
    build_enriched_local_business_schema,
    build_local_faq_html,
    build_local_faq_schema,
    enhance_article,
    get_niche_profile,
)
from internal_linking_engine import SERVICE_CITIES, enhance_with_links
from post_processor import fix_article
from content_fingerprint import _fingerprint_text, _strip_html_body, jaccard_similarity, find_template_bleed
from page_blueprints import pick_blueprint, render_blueprint, SECTION_RENDERERS

log = logging.getLogger("programmatic_expander")

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "projects", "grand_rapids")
SITE_URL = os.environ.get("SEO_AGENT_SITE_URL", "https://yoursite.com")

# Map modifier keys to directory names under PROJECT_ROOT
MODIFIER_DIRS = {
    "emergency": "emergency",
    "same-day": "same_day",
    "same_day": "same_day",
    "affordable": "affordable",
    "near-me": "near_me",
    "near_me": "near_me",
    "24-hour": "24_hour",
    "24_hour": "24_hour",
    "licensed": "licensed",
    "commercial": "commercial",
    "top-rated": "top_rated",
    "top_rated": "top_rated",
    "free-estimate": "free_estimate",
    "free_estimate": "free_estimate",
    "family-owned": "family_owned",
    "family_owned": "family_owned",
}
SITE_NAME = "Grand Rapids Home Services"
STREET_ADDRESS = "1234 Plainfield Ave NE"
BUSINESS_ZIP = "49505"

SERVICES = [
    "appliance repair",
    "garage door repair",
    "garage door installation",
    "basement remodel",
    "shower remodel",
    "plumbing",
    "hvac",
    "electrical",
    "roofing",
    "water damage restoration",
    "mold remediation",
    "flooring",
    "window replacement",
    "siding",
    "concrete",
    "deck and patio",
    "kitchen remodeling",
    "bathroom remodeling",
    "painting",
    "fencing",
    "landscaping",
    "tree service",
    "pest control",
]

EXPAND_CITIES = {
    "Grand Rapids": {"slug": "grand-rapids", "county": "Kent County", "zip_prefix": "495", "description": "the largest city in West Michigan"},
    "Kentwood": {"slug": "kentwood", "county": "Kent County", "zip_prefix": "495", "description": "a thriving suburban community south of Grand Rapids"},
    "Wyoming": {"slug": "wyoming-mi", "county": "Kent County", "zip_prefix": "495", "description": "a growing city southwest of downtown"},
    "East Grand Rapids": {"slug": "east-grand-rapids", "county": "Kent County", "zip_prefix": "495", "description": "an upscale suburban community east of downtown"},
    "Walker": {"slug": "walker-mi", "county": "Kent County", "zip_prefix": "495", "description": "a family-friendly city northwest of Grand Rapids"},
    "Ada": {"slug": "ada-mi", "county": "Kent County", "zip_prefix": "493", "description": "a charming village along the Thornapple River"},
    "Cascade": {"slug": "cascade-mi", "county": "Kent County", "zip_prefix": "495", "description": "a scenic township southeast of Grand Rapids"},
    "Rockford": {"slug": "rockford-mi", "county": "Kent County", "zip_prefix": "493", "description": "a historic community along the Rogue River"},
}

MODIFIERS = {
    "emergency": {"priority": 1, "intent": "high conversion", "label": "Emergency", "urgency": "24/7", "hook_tag": "emergency"},
    "same-day": {"priority": 2, "intent": "transactional", "label": "Same-Day", "urgency": "same day", "hook_tag": "same_day"},
    "affordable": {"priority": 3, "intent": "commercial", "label": "Affordable", "urgency": "budget-friendly", "hook_tag": "affordable"},
    "near-me": {"priority": 4, "intent": "local intent", "label": "Near Me", "urgency": "local", "hook_tag": "near_me"},
    "24-hour": {"priority": 5, "intent": "urgency", "label": "24 Hour", "urgency": "24/7", "hook_tag": "emergency"},
    "licensed": {"priority": 6, "intent": "trust", "label": "Licensed", "urgency": "professional", "hook_tag": "licensed"},
    "commercial": {"priority": 7, "intent": "commercial", "label": "Commercial", "urgency": "business", "hook_tag": "commercial"},
    "top-rated": {"priority": 8, "intent": "trust", "label": "Top-Rated", "urgency": "quality", "hook_tag": "top_rated"},
    "free-estimate": {"priority": 9, "intent": "commercial", "label": "Free Estimate", "urgency": "savings", "hook_tag": "free_estimate"},
    "family-owned": {"priority": 10, "intent": "trust", "label": "Family-Owned", "urgency": "local", "hook_tag": "family_owned"},
}

INTRO_HOOKS = {
    "emergency": [
        "When {service} emergencies happen in {city}, you need a team that responds immediately. Our {city} technicians are on call 24/7 for urgent repairs.",
        "Emergency {service} situations don't wait for business hours. That's why our {city} team provides round-the-clock service when you need it most.",
        "Stranded with a {service} emergency in {city}? We offer fast response times and expert service, even on weekends and holidays.",
        "Don't let a {service} emergency disrupt your day in {city}. Our rapid-response team is ready to help anytime, day or night.",
        "A {service} emergency can happen at the worst possible moment. That's why our {city} team is always ready to respond, 365 days a year.",
        "When you're facing a {service} crisis in {city}, every minute counts. Our fast-response team is on standby 24 hours a day.",
        "{service} emergencies don't follow a schedule, and neither do we. Our {city} technicians are available around the clock for urgent needs.",
        "Urgent {service} problem in {city}? Don't wait — our emergency team can be at your location within the hour, day or night.",
    ],
    "same-day": [
        "Need {service} in {city} today? Our same-day service means you don't have to wait days for a qualified technician to arrive.",
        "Same-day {service} in {city} is our specialty. Call before noon and we'll have a technician at your door ready to help.",
        "When you need fast {service} in {city}, our same-day scheduling gets a technician to your home within hours, not days.",
        "No appointment weeks out. We offer genuine same-day {service} across {city} and all surrounding communities.",
        "Busy schedule? Our same-day {service} in {city} works around your availability. Morning call means afternoon service.",
        "Don't let a broken appliance disrupt your week. Our same-day {service} in {city} gets you back up and running fast.",
        "Same-day {service} in {city} means we prioritize your time. Most calls before 11 AM get service the same afternoon.",
        "Hassle-free same-day {service} in {city} — one call, same-day visit, no runaround. That's our promise to you.",
    ],
    "affordable": [
        "Quality {service} in {city} doesn't have to break the bank. We offer competitive, transparent pricing without cutting corners.",
        "Affordable {service} in {city} is possible. Get upfront pricing, no hidden fees, and quality workmanship every time.",
        "Looking for budget-friendly {service} in {city}? Our rates are fair, our estimates are free, and our work is guaranteed.",
        "You shouldn't overpay for {service} in {city}. We provide honest quotes and quality work at prices that make sense.",
        "Get the best value for {service} in {city}. Our prices are competitive, our work is guaranteed, and there are no surprises on your bill.",
        "Affordable doesn't mean cheap. Our {service} in {city} delivers professional results at prices that respect your budget.",
        "We believe everyone deserves quality {service} in {city} at a fair price. Free estimates, no hidden costs, guaranteed work.",
        "Compare our {service} prices in {city}. We're confident you'll find fair rates, transparent quotes, and real value for your money.",
    ],
    "near-me": [
        "Searching for {service} near you in {city}? Our local technicians are based right here in the community and ready to help.",
        "Looking for {service} near me in {city}? We're your neighbors, serving {city} homes with professional, reliable service.",
        "Find trusted {service} near you in {city}. Our locally-based team knows the area and can be at your home quickly.",
        "Need {service} close to home in {city}? We're a local business serving our neighbors with the quality we'd want for our own homes.",
        "Why search for {service} far away when top-rated {service} near you in {city} is just a phone call away?",
        "Local {service} matters. Our {city} technicians know the neighborhood streets and can reach your home faster than out-of-town companies.",
        "Your neighbors trust us for {service} near {city}. Read our reviews and see why local homeowners choose us again and again.",
        "Skip the drive time. Our {city}-based {service} team is already nearby, ready to respond quickly to your service request.",
    ],
    "24-hour": [
        "Round-the-clock {service} in {city} — our technicians are available 24 hours a day, 7 days a week, including holidays.",
        "Day or night, our {city} team provides {service} when you need it most. True 24-hour service with no after-hours markup.",
        "Problems don't follow a 9-to-5 schedule. That's why we offer genuine 24-hour {service} across {city} every day of the year.",
        "Late-night {service} emergency in {city}? Our 24-hour team is just a phone call away, ready to respond at any hour.",
        "Midnight {service} issue in {city}? Don't wait until morning. Our 24-hour team is awake and ready to help right now.",
        "Rain or shine, 2 AM or 2 PM — our {service} team in {city} never sleeps. Call anytime for immediate assistance.",
        "True 24-hour {service} in {city} means a real technician answers your call, not a voicemail box. We're here when you need us.",
        "Weekends, holidays, late nights — our {city} {service} team covers them all with no premium pricing for after-hours calls.",
    ],
    "licensed": [
        "Searching for licensed {service} in {city}? Our technicians are fully licensed, bonded, and insured — giving you complete peace of mind.",
        "When hiring for {service} in {city}, you deserve a licensed professional who meets all Michigan regulatory requirements and carries proper insurance.",
        "Don't trust your {service} needs in {city} to just anyone. All our technicians are licensed, background-checked, and insured for your protection.",
        "Licensed {service} in {city} matters because it means proper training, insurance coverage, and accountability. That's what we deliver on every job.",
        "We take licensing seriously. Every {service} technician in {city} holds current Michigan licenses and undergoes ongoing training to stay current.",
        "When you hire licensed {service} in {city}, you're protected. Our credentials mean we meet safety standards, carry insurance, and stand behind our work.",
        "Peace of mind comes standard with our licensed {service} in {city}. Fully insured, bonded, and certified — your home is in safe hands.",
        "Why risk unlicensed {service} in {city}? Our team is fully licensed by the State of Michigan with comprehensive liability insurance on every job.",
    ],
    "commercial": [
        "Need commercial {service} in {city}? Our team handles businesses, offices, retail spaces, and commercial properties throughout the Grand Rapids area.",
        "Commercial {service} in {city} requires different expertise than residential work. We understand business schedules, code requirements, and minimizing downtime.",
        "Running a business in {city} is demanding enough. Our commercial {service} team works around your schedule — after hours, weekends, or during business slowdowns.",
        "Professional commercial {service} in {city} for property managers, business owners, and facility managers. We handle projects of any scale.",
        "Your {city} business deserves commercial-grade {service} from a team that understands commercial permitting, safety compliance, and project timelines.",
        "From retail spaces to office buildings, we provide commercial {service} in {city} with minimal disruption to your operations and maximum quality.",
        "Commercial {service} in {city} — we work with property managers and business owners to keep their properties running smoothly with flexible scheduling.",
        "Multi-unit commercial {service} in {city} is our specialty. We coordinate with property managers for efficient, cost-effective service across entire complexes.",
    ],
    "top-rated": [
        "Top-rated {service} in {city} — see why our customers consistently give us 5 stars. We're proud to be one of the highest-rated {service} providers in West Michigan.",
        "Don't take our word for it. We're known as the top-rated {service} company in {city} because our customers consistently praise our quality, speed, and professionalism.",
        "Consistently ranked among the top {service} providers in {city}, our reputation is built on thousands of satisfied customers and years of proven results.",
        "Why settle for average {service} in {city}? Our top-rated team delivers exceptional results backed by glowing customer reviews and industry recognition.",
        "Our top-rated {service} in {city} status isn't an accident. It comes from years of exceeding expectations, transparent pricing, and genuine care for every customer.",
        "Searching for the best {service} in {city}? Our top-rated technicians have earned their reputation through consistent quality, fast response, and fair prices.",
        "Top-rated {service} in {city} means you get the best. Highest customer satisfaction scores, fastest response times, and a satisfaction guarantee on every job.",
        "We're proud to be a top-rated {service} provider in {city}. Read our reviews, check our ratings, and see why homeowners across West Michigan trust us.",
    ],
    "free-estimate": [
        "Get a free estimate for {service} in {city} — no obligation, no hidden fees, no pressure. We'll assess your needs and provide a transparent quote upfront.",
        "Free estimates for {service} in {city} are just the start. We provide detailed written quotes so you know exactly what to expect before any work begins.",
        "Why pay for quotes? We offer free, detailed estimates for {service} in {city} with full transparency on materials, labor, and timeline.",
        "Before you commit to {service} in {city}, get a free estimate from our team. We'll walk through your project, answer questions, and provide a fair price.",
        "Free estimates on all {service} in {city}. Our detailed quotes include labor, materials, permits, and timeline — no surprises, no fine print.",
        "Planning {service} in {city}? Start with a free, no-obligation estimate. We'll assess the scope, discuss options, and provide competitive pricing.",
        "We believe in transparent pricing for {service} in {city}. That's why we offer free estimates with detailed breakdowns — what you see is what you pay.",
        "Free estimate for {service} in {city} — call us today and we'll schedule a convenient time to assess your project and provide a competitive quote.",
    ],
    "family-owned": [
        "Family-owned {service} in {city} since 2015. When you call us, you talk directly to the people who own the business — not a call center.",
        "Choose a family-owned {service} company in {city} that treats you like family. We've been serving our neighbors since 2015 with honesty and integrity.",
        "We're a family-owned {service} business in {city}, and we treat every home like it's our own. That means quality work, fair prices, and genuine care.",
        "Family-owned and community-focused. Our {service} team in {city} has deep roots in West Michigan and a reputation built on trust, not advertising.",
        "When you hire our family-owned {service} company in {city}, you support a local business. We live here, work here, and care deeply about our community.",
        "Three generations of {service} expertise in {city}. Our family-owned business brings decades of combined experience to every job we take on.",
        "Behind every {service} job in {city} is a family that stands behind their work. We're locally owned, family operated, and committed to your satisfaction.",
        "Family-owned {service} in {city} means personal accountability. The name on the truck is the same family that answers your call and stands by the work.",
    ],
}

# Review selection helper: map cities to reviewer areas for better matching
CITY_REVIEW_PREFERENCE = {
    "Grand Rapids": ["East Hills", "Heritage Hill", "Belknap Lookout", "Midtown", "East Grand Rapids", "Grand Rapids"],
    "Kentwood": ["Kentwood", "South Kent", "Paris Ridge"],
    "Wyoming": ["Wyoming", "Rogers Plaza", "Godfrey-Lee"],
    "East Grand Rapids": ["East Grand Rapids", "Gaslight Village", "Wealthy Street"],
    "Walker": ["Walker", "Standale"],
    "Ada": ["Ada", "Ada Village"],
    "Cascade": ["Cascade", "Cascade Township"],
    "Rockford": ["Rockford", "Rockford Village"],
}

# Blueprint-based section order templates (kept for backward compat)
SECTION_ORDERS = [
    ["intro", "brands", "services", "why_choose", "areas", "faq", "contact"],
    ["intro", "services", "brands", "why_choose", "areas", "faq", "contact"],
    ["intro", "why_choose", "services", "brands", "areas", "faq", "contact"],
    ["intro", "brands", "services", "areas", "why_choose", "faq", "contact"],
    ["intro", "services", "why_choose", "brands", "faq", "areas", "contact"],
]

SERVICE_SUMMARIES = {
    "appliance repair": "We repair refrigerators, freezers, dishwashers, ovens, washers, dryers, and all major home appliances from top brands.",
    "garage door repair": "We fix broken springs, off-track doors, malfunctioning openers, damaged panels, and all garage door issues.",
    "garage door installation": "We install new garage doors of all types — insulated, carriage house, modern glass, roll-up, and smart-enabled.",
    "basement remodel": "We transform unfinished basements into beautiful living spaces — home theaters, guest suites, bars, and home offices.",
    "shower remodel": "We design and install custom showers — walk-in, tile, accessible, steam, and tub-to-shower conversions.",
}

BENEFITS = {
    "appliance repair": [
        "OEM-certified technicians with factory training on all major brands",
        "Same-day service available for most repairs in {city}",
        "Upfront pricing — no surprises, no hidden fees",
        "90-day warranty on parts and 1 year on labor",
    ],
    "garage door repair": [
        "Emergency service available 24/7 for urgent garage door issues",
        "Most repairs completed in under 2 hours",
        "Licensed and insured garage door technicians",
        "1-year warranty on parts, 2 years on labor",
    ],
    "garage door installation": [
        "Free estimates with no obligation",
        "Professional installation by certified technicians",
        "Lifetime warranty on door materials",
        "Same-day and next-day installation available",
    ],
    "basement remodel": [
        "Free design consultation and estimate",
        "Licensed contractors with years of remodeling experience",
        "Full project management from permit to finishing",
        "2-year workmanship warranty on all projects",
    ],
    "shower remodel": [
        "Free consultation and 3D design preview",
        "Certified bath designers on staff",
        "Quality materials from top manufacturers",
        "Projects completed in as little as 3-7 days",
    ],
}


# ──────────────────────────────────────────────
# SLUG GENERATOR
# ──────────────────────────────────────────────

def generate_slug(service: str, modifier: str, city: str) -> str:
    """Generate a clean URL slug for a page combination."""
    parts = []
    if modifier:
        parts.append(modifier)
    parts.append(service)
    parts.append(city)
    parts.append("mi")
    raw = "-".join(parts)
    return re.sub(r"[^a-z0-9-]+", "-", raw.lower()).strip("-")


def generate_keyword(service: str, modifier: str, city: str) -> str:
    """Generate the full keyword string for a page."""
    mod_label = MODIFIERS[modifier]["label"].lower().replace(" ", "-")
    return f"{mod_label} {service} {city.lower()} mi"


# ──────────────────────────────────────────────
# MATRIX BUILDER
# ──────────────────────────────────────────────

def build_matrix() -> list[dict[str, Any]]:
    """Build all service × city × modifier combinations sorted by priority."""
    pages = []
    for service in SERVICES:
        for city in EXPAND_CITIES:
            for modifier, mod_data in MODIFIERS.items():
                pages.append({
                    "service": service,
                    "city": city,
                    "modifier": modifier,
                    "mod_data": mod_data,
                    "slug": generate_slug(service, modifier, city),
                    "keyword": generate_keyword(service, modifier, city),
                    "priority": mod_data["priority"],
                })
    # Sort by modifier priority then service then city
    pages.sort(key=lambda p: (p["priority"], p["service"], p["city"]))
    return pages


# ──────────────────────────────────────────────
# BASE ARTICLE BUILDER
# ──────────────────────────────────────────────

def _pick_intro(service: str, modifier: str, city: str) -> str:
    """Pick a varied intro hook for the combination."""
    hooks = INTRO_HOOKS.get(modifier, [])
    if not hooks:
        return (
            f"Looking for professional {service} in {city}? "
            f"Our experienced team has been serving {city} and all of West Michigan since {BUSINESS_IDENTITY['founded_year']}."
        )
    return random.choice(hooks).format(service=service, city=city)


def _build_service_list_html(service: str) -> str:
    """Build a service items list from the niche profile."""
    profile = NICHE_PROFILES.get(service)
    if not profile:
        return ""
    items = profile.get("service_items", [])
    if not items:
        return ""
    # Pick a varied subset
    count = min(len(items), random.randint(4, 7))
    selected = items[:count]
    rows = "\n".join(f"            <li><p>{item}</p></li>" for item in selected)
    return f"""        <ul>
{rows}
        </ul>"""


def _build_brands_html(service: str) -> str:
    """Build a brands list from the niche profile."""
    profile = NICHE_PROFILES.get(service)
    if not profile:
        return ""
    brands = profile.get("brands", [])
    if not brands:
        return ""
    return ", ".join(brands)


def _build_areas_served_html(city: str, service: str) -> str:
    """Build the Areas Served section with city-specific neighborhoods."""
    city_data = SERVICE_CITIES.get(city, {})
    hoods = city_data.get("neighborhoods", [])
    hood_text = ", ".join(hoods[:4]) if hoods else "all neighborhoods"

    serv_areas = [c for c in EXPAND_CITIES if c != city][:5]
    area_text = ", ".join(serv_areas)

    return f"""<h2>Areas We Serve</h2>
<p>We provide {service} throughout {city}, including {hood_text}. Our service area covers all of {EXPAND_CITIES[city].get('county', 'Kent County')} and extends up to {40} miles from Grand Rapids.</p>
<p>In addition to {city}, we proudly serve {area_text} and all of West Michigan.</p>"""


def _build_why_choose_us_html(service: str, city: str) -> str:
    """Build a Why Choose Us section with benefits."""
    benefits = BENEFITS.get(service, [])
    formatted = [b.format(city=city) for b in benefits]
    # Vary order
    random.shuffle(formatted)
    return f"""<h2>Why Choose Us for {service.capitalize()} in {city}</h2>
<p>When you choose Grand Rapids Home Services for your {service} needs in {city}, you get:</p>
<ul>
{"".join(f'<li>{b}</li>' for b in formatted)}
</ul>"""


def _build_faq_html(service: str, city: str, modifier: str) -> str:
    """Build FAQ section with service FAQs + city-specific questions."""
    profile = get_niche_profile(service)
    niche_faqs = profile.get("faqs", [])

    # City-specific FAQs
    city_faqs = [
        (f"Do you offer {service} in {city}?",
         f"Yes, we provide full {service} services in {city} and all surrounding neighborhoods. Our technicians serve {city} daily."),
        (f"How quickly can you get to {city} for {service}?",
         f"Our standard response time for {city} is within 2-4 hours. Emergency services are available within 1-2 hours."),
        (f"Are your {service} technicians licensed to work in {city}?",
         f"Yes, all our technicians are fully licensed, bonded, and insured in Michigan. We meet all {city} and {EXPAND_CITIES[city].get('county', 'Kent County')} requirements."),
    ]

    # Combine, deduplicate, limit to 6
    seen_qs = set()
    all_faqs = []
    for q, a in niche_faqs + city_faqs:
        q_lower = q.lower().strip()
        if q_lower not in seen_qs:
            seen_qs.add(q_lower)
            all_faqs.append((q, a))
        if len(all_faqs) >= 6:
            break

    if not all_faqs:
        return ""

    items = "\n".join(
        f"""<div class="faq-item">
<h3>{q}</h3>
<p>{a}</p>
</div>"""
        for q, a in all_faqs
    )

    return f"""<h2>Frequently Asked Questions About {service.capitalize()} in {city}</h2>
{items}"""


def _build_contact_html() -> str:
    """Build a contact section."""
    return f"""<h2>Contact Us</h2>
<p>Ready to get started? Call us at <strong>{BUSINESS_IDENTITY['phone']}</strong> or email <strong>{BUSINESS_IDENTITY['email']}</strong>.</p>
<p>Our office is located at {BUSINESS_IDENTITY['address']}, {BUSINESS_IDENTITY['city']}, {BUSINESS_IDENTITY['state']} {BUSINESS_IDENTITY['zip']}.</p>"""


def _build_pricing_html(service: str) -> str:
    """Build a pricing section for blueprints that include it."""
    profile = NICHE_PROFILES.get(service, {})
    items = profile.get("service_items", [])
    table_rows = ""
    for item in items[:4]:
        table_rows += f"""<tr><td>{item}</td><td>Call for estimate</td><td>Varies by scope</td></tr>
"""
    return f"""<h2>Pricing for {service.title()} in Grand Rapids</h2>
<div class="pricing-table-wrapper">
<table class="pricing-table">
<thead>
    <tr><th>Service</th><th>Service Call</th><th>Typical Cost</th></tr>
</thead>
<tbody>
{table_rows}</tbody>
</table>
<p style="font-size:0.85em;color:#666;">Contact us for a free, accurate quote tailored to your specific needs.</p>
</div>"""


def _pick_reviews_html(service: str, city: str) -> str:
    """Pick reviews for the article, preferring reviewers from the target city."""
    profile = get_niche_profile(service)
    niche = getattr(profile, "_niche", None) or service
    niche_reviews = REVIEWS.get(niche, [])

    if not niche_reviews:
        return ""

    # Score reviews by city relevance
    preferred_areas = CITY_REVIEW_PREFERENCE.get(city, [])
    def score_review(r: dict) -> int:
        area = r.get("area", "")
        for i, pa in enumerate(preferred_areas):
            if pa.lower() in area.lower():
                return len(preferred_areas) - i
        return 0

    scored = sorted(niche_reviews, key=score_review, reverse=True)
    # Take top 3, prefer city-matched
    selected = scored[:3]
    # If we have city-matched reviews, use those; otherwise use first 3
    if score_review(selected[0]) == 0 and len(niche_reviews) >= 3:
        selected = niche_reviews[:3]

    cards = []
    for r in selected:
        stars = "★" * int(r["rating"]) + "☆" * (5 - int(r["rating"]))
        card = f"""<div class="testimonial" style="background:#f9f9f9;border-left:4px solid #2b6cb0;padding:12px 16px;margin:12px 0;border-radius:4px;">
    <p style="margin:0 0 6px;font-size:1.05em;">"{r['text']}"</p>
    <p style="margin:0;font-size:0.85em;color:#555;">— {r['reviewer']}, {r['area']}</p>
    <p style="margin:0;font-size:0.85em;color:#e6a817;">{stars}</p>
</div>"""
        cards.append(card)

    return f"""<h2>What {city} Homeowners Say About Our Services</h2>
<p>Don't just take our word for it. Here's what real customers in West Michigan have experienced:</p>
{''.join(cards)}"""


def build_base_article(service: str, city: str, modifier: str) -> str:
    """Build a differentiated base article for a service × city × modifier combination."""
    # Seed RNG for deterministic variety per combination
    seed_str = f"{service}:{city}:{modifier}"
    rng = random.Random(seed_str)

    mod_label = MODIFIERS[modifier]["label"]
    h1 = f"{mod_label} {service.title()} in {city}, Michigan"
    meta_desc = f"Looking for {mod_label.lower()} {service} in {city}, MI? Grand Rapids Home Services offers professional, licensed {service} throughout {city} and West Michigan."

    # Pick blueprint for structural diversity
    bp = pick_blueprint(service, city, modifier)

    intro = _pick_intro(service, modifier, city)
    summary = SERVICE_SUMMARIES.get(service, "")
    brands_text = _build_brands_html(service)

    # Brand mention paragraph (if brands exist)
    brand_para = ""
    if brands_text:
        # Vary brand paragraph text
        brand_templates = [
            f"<p>We work with all leading brands including {brands_text}. No matter what brand you own, our technicians have the training and parts to get it working again.</p>",
            f"<p>Our technicians are trained on all major brands including {brands_text}. We carry common parts and can order specialized components quickly.</p>",
            f"<p>From {brands_text} — we service them all. Our factory-trained technicians know the ins and outs of every brand we work on.</p>",
        ]
        brand_para = rng.choice(brand_templates)

    # Build section content (keys match blueprint section names)
    section_content: dict[str, str] = {}

    # Intro
    section_content["intro"] = f"<p>{intro} {summary}</p>"

    # Brands (conditional per blueprint)
    if brand_para and bp.get("show_brands", True):
        section_content["brands"] = brand_para

    # Services list
    svc_list = _build_service_list_html(service)
    if svc_list:
        section_content["services"] = f"""<h2>Our {service.title()} Services in {city}</h2>
<p>We offer comprehensive {service} services for homes throughout {city}. Our capabilities include:</p>
{svc_list}"""

    # Why Choose Us (renamed to match blueprint key)
    section_content["why_us"] = _build_why_choose_us_html(service, city)

    # Areas Served (conditional per blueprint)
    if bp.get("show_areas", True):
        section_content["areas"] = _build_areas_served_html(city, service)

    # FAQ
    section_content["faq"] = _build_faq_html(service, city, modifier)

    # Reviews (conditional per blueprint review_count)
    if bp.get("review_count", 0) > 0:
        reviews_html = _pick_reviews_html(service, city)
        if reviews_html:
            section_content["reviews"] = reviews_html

    # Pricing (conditional per blueprint)
    if bp.get("show_pricing", False):
        section_content["pricing"] = _build_pricing_html(service)

    # Contact
    section_content["contact"] = _build_contact_html()

    # Build sections in blueprint order
    ordered = []
    for key in bp["sections"]:
        if key in section_content:
            ordered.append(section_content[key])
    # Append any remaining sections not in the blueprint
    for key in section_content:
        if key not in bp["sections"]:
            ordered.append(section_content[key])

    body = "\n\n".join(ordered)
    body = body.replace("Business Name", BUSINESS_IDENTITY["name"])

    return f"""<h1>{h1}</h1>
<meta name="description" content="{meta_desc}">
{body}"""


# ──────────────────────────────────────────────
# HTML CLEANER
# ──────────────────────────────────────────────

def _clean_final_html(html: str) -> str:
    """Fix HTML structural issues introduced by post-processor over-wrapping."""
    # Fix <li><p>text</p></li> -> <li>text</li>
    html = re.sub(r"<li>\s*<p>(.*?)</p>\s*</li>", r"<li>\1</li>", html, flags=re.DOTALL)
    # Fix <a ...><p>text</p></a> -> <a ...>text</a>
    html = re.sub(r"<a\s+([^>]+)>\s*<p>(.*?)</p>\s*</a>", r'<a \1>\2</a>', html, flags=re.DOTALL)
    # Fix <p><a ...><p>text</p></a></p> -> <p><a ...>text</a></p>
    html = re.sub(r"<p>\s*<a\s+([^>]+)>\s*<p>(.*?)</p>\s*</a>\s*</p>", r'<p><a \1>\2</a></p>', html, flags=re.DOTALL)
    # Fix <strong><p>text</p></strong> / <span style="..."><p>text</p></span> -> <strong>text</strong>
    html = re.sub(r"<(strong|span|em)([^>]*)>\s*<p>(.*?)</p>\s*</\1>", r"<\1\2>\3</\1>", html, flags=re.DOTALL)
    # Fix <p>...</p></p> (stray close after legitimate close)
    html = re.sub(r"</p>\s*</p>", "</p>", html)
    # Fix double opening <p[^>]*><p> -> single <p>
    html = re.sub(r"<p[^>]*>\s*<p>", "<p>", html)
    html = re.sub(r"<p[^>]*>\s*<p\s+([^>]+)>", r"<p \1>", html)
    # Fix double closing </p></p> -> single </p>
    html = re.sub(r"</p>\s*</p>", "</p>", html)
    # Fix <p style="..."><p> -> <p style="..."> (already handled above, but catch leftover)
    html = re.sub(r"<p([^>]*)>\s*<p>", r"<p\1>", html)
    # Remove empty <p></p>, <p> </p>, <p>&nbsp;</p>
    html = re.sub(r"<p>\s*(?:&nbsp;)?\s*</p>", "", html)
    # Remove generic quick-answer-box (irrelevant for local service pages)
    html = re.sub(r'<div class="quick-answer-box">.*?</div>', "", html, flags=re.DOTALL)
    # Remove stray </p> after </body> or </html>
    html = re.sub(r"(</(?:body|html)>\s*)\s*</?p>+", r"\1", html, flags=re.DOTALL)
    # Remove </p> at EOF
    html = re.sub(r"</p>\s*$", "", html)
    return html.strip()


# ──────────────────────────────────────────────
# HTML TEMPLATE WRAPPER
# ──────────────────────────────────────────────

def _wrap_html(body: str, keyword: str, slug: str, service: str = "") -> str:
    """Wrap article body in a complete HTML document with schemas."""
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", body)
    page_title = h1_match.group(1) if h1_match else keyword.title()
    # Use clean service name for schemas instead of the full keyword
    schema_kw = service if service else keyword
    today = datetime.now().strftime("%Y-%m-%d")

    # Build schemas
    article_schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": page_title,
        "description": f"Professional {keyword} services in Grand Rapids, MI",
        "author": {"@type": "Person", "name": "James Whitfield"},
        "publisher": {
            "@type": "Organization",
            "name": SITE_NAME,
            "url": SITE_URL,
        },
        "datePublished": today,
        "dateModified": today,
    }

    local_biz_schema = build_enriched_local_business_schema(schema_kw)
    faq_schema = build_local_faq_schema(schema_kw)

    schemas = [json.dumps(article_schema)]
    if local_biz_schema:
        schemas.append(local_biz_schema)
    if faq_schema:
        schemas.append(faq_schema)

    schema_html = "\n".join(
        f'<script type="application/ld+json">{s}</script>' for s in schemas
    )

    desc_kw = schema_kw if schema_kw else keyword
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{page_title}</title>
<meta name="description" content="Professional {desc_kw} services in Grand Rapids, MI and surrounding areas.">
<link rel="canonical" href="{SITE_URL}/{slug}/">
<meta name="geo.region" content="US-MI">
<meta name="geo.placename" content="Grand Rapids">
<meta name="geo.position" content="42.9634;-85.6681">
<meta name="ICBM" content="42.9634, -85.6681">
{schema_html}
</head>
<body itemscope itemtype="https://schema.org/Article">
<meta itemprop="headline" content="{page_title}">
<meta itemprop="author" content="James Whitfield">
<meta itemprop="datePublished" content="{today}">
{body}
</body>
</html>"""


# SIMILARITY GUARD — now uses content_fingerprint module


# ──────────────────────────────────────────────
# PAGE EMITTER
# ──────────────────────────────────────────────

def emit_page(html: str, slug: str, modifier: str = "") -> str:
    """Write a page HTML file into the project structure and return its path."""
    # Determine output directory based on modifier
    out_subdir = MODIFIER_DIRS.get(modifier, "generated") if modifier else "articles"
    out_dir = os.path.join(PROJECT_ROOT, out_subdir)
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{slug}_{timestamp}.html"
    filepath = os.path.join(out_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    log.info("Emitted: %s/%s", out_subdir, filename)
    return filepath


# ──────────────────────────────────────────────
# BATCH GENERATOR
# ──────────────────────────────────────────────

def generate_batch(limit: int = 25) -> list[dict[str, Any]]:
    """
    Generate a batch of programmatic SEO pages.

    Args:
        limit: Maximum number of pages to generate (default 25).

    Returns:
        List of dicts with page metadata: slug, keyword, service, city, modifier, filepath.
    """
    log.info("Building service × city × modifier matrix...")
    matrix = build_matrix()
    log.info("Matrix has %d total combinations (services=%d × cities=%d × modifiers=%d)",
             len(matrix), len(SERVICES), len(EXPAND_CITIES), len(MODIFIERS))

    batch = matrix[:limit]
    generated: list[dict[str, Any]] = []
    fingerprints: list[set[str]] = []

    for i, entry in enumerate(batch):
        service = entry["service"]
        city = entry["city"]
        modifier = entry["modifier"]
        keyword = entry["keyword"]
        slug = entry["slug"]

        log.info("[%d/%d] Generating: %s (%s × %s × %s)",
                 i + 1, len(batch), keyword, service, city, modifier)

        # Build base article
        article = build_base_article(service, city, modifier)

        # Run enhancement pipeline
        article = enhance_article(article, keyword, "LOCAL_SERVICE")

        # Wrap in full HTML
        html = _wrap_html(article, keyword, slug, service)

        # Post-process (cleanup, normalize)
        html = fix_article(html, keyword)

        # Clean structural issues from over-wrapping
        html = _clean_final_html(html)

        # Section-level fingerprint check (filtering schemas/boilerplate)
        clean = _strip_html_body(html)
        fp = _fingerprint_text(clean)
        for prev_slug, prev_fp in fingerprints:
            sim = jaccard_similarity(fp, prev_fp)
            if sim >= 0.70:
                log.warning("High similarity (%.2f) with %s — generating with new seed", sim, prev_slug)
                random.seed(hash(f"{slug}:{i}:retry"))
                article2 = build_base_article(service, city, modifier)
                article2 = enhance_article(article2, keyword, "LOCAL_SERVICE")
                html2 = _wrap_html(article2, keyword, slug, service)
                html2 = fix_article(html2, keyword)
                html2 = _clean_final_html(html2)
                fp2 = _fingerprint_text(_strip_html_body(html2))
                sim2 = jaccard_similarity(fp2, prev_fp)
                if sim2 < sim:
                    html = html2
                    fp = fp2
                    log.info("  Retry improved: %.2f -> %.2f", sim, sim2)
                random.seed()

        fingerprints.append((slug, fp))

        # Write page to modifier-specific directory
        filepath = emit_page(html, slug, modifier)

        generated.append({
            "slug": slug,
            "keyword": keyword,
            "service": service,
            "city": city,
            "modifier": modifier,
            "filepath": filepath,
        })

    # Report template bleed (find_template_bleed filters schemas internally)
    all_html = [{"slug": g["slug"], "html": open(g["filepath"], encoding="utf-8").read()} for g in generated]
    bleed = find_template_bleed(all_html)
    if bleed:
        log.warning("Template bleed detected: %d sentences shared across 2+ pages", len(bleed))
        for b in bleed[:5]:
            log.warning("  %d×: \"%s\"", b["count"], b["sentence"][:80])

    log.info("Batch complete: %d pages generated in %s", len(generated), PROJECT_ROOT)
    return generated


# ──────────────────────────────────────────────
# SITEMAP GENERATOR
# ──────────────────────────────────────────────

def generate_sitemap(pages: list[dict[str, Any]], output_path: str | None = None, project_root: str = "") -> str:
    """Generate a single flat XML sitemap (legacy, use generate_segmented_sitemaps instead)."""
    today = datetime.now().strftime("%Y-%m-%d")
    urls = []
    for p in pages:
        urls.append(f"""  <url>
    <loc>{SITE_URL}/{p['slug']}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>""")

    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""

    if not output_path:
        base = project_root if project_root else PROJECT_ROOT
        output_path = os.path.join(base, "sitemap", "sitemap.xml")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(sitemap)
    log.info("Sitemap written: %s", output_path)

    return sitemap


def _write_sitemap_file(urls: list[str], sitemap_name: str, base_dir: str) -> str:
    """Write a single sitemap file and return its path."""
    today = datetime.now().strftime("%Y-%m-%d")
    url_xml = "\n".join(f"""  <url>
    <loc>{SITE_URL}/{u}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>""" for u in urls)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{url_xml}
</urlset>"""
    filepath = os.path.join(base_dir, sitemap_name)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(xml)
    log.info("Sitemap segment written: %s (%d URLs)", sitemap_name, len(urls))
    return filepath


def generate_segmented_sitemaps(pages: list[dict[str, Any]], project_root: str = "",
                                include_neighborhoods: bool = False,
                                include_hubs: bool = False,
                                include_authority: bool = False) -> dict[str, str]:
    """Generate segmented sitemaps by modifier + optional neighborhoods/hubs/authority.

    Produces one sitemap per modifier group plus an index sitemap.
    Returns dict mapping segment name to filepath.
    """
    base = project_root if project_root else PROJECT_ROOT
    sitemap_dir = os.path.join(base, "sitemap")
    os.makedirs(sitemap_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    segments: dict[str, list[str]] = {}
    segment_files: dict[str, str] = {}

    # Group pages by modifier
    for p in pages:
        mod = p.get("modifier", "articles")
        if mod not in segments:
            segments[mod] = []
        segments[mod].append(p["slug"])

    # Write per-modifier sitemaps
    for mod, slugs in sorted(segments.items()):
        sitemap_name = f"sitemap-{mod}.xml"
        _write_sitemap_file(slugs, sitemap_name, sitemap_dir)
        segment_files[mod] = sitemap_name

    # Neighborhoods sitemap (scan neighborhoods dir)
    if include_neighborhoods:
        hood_dir = os.path.join(base, "neighborhoods")
        if os.path.isdir(hood_dir):
            hood_slugs = []
            for fname in os.listdir(hood_dir):
                if fname.endswith(".html"):
                    slug = fname.rsplit("_", 2)[0]
                    hood_slugs.append(slug)
            if hood_slugs:
                _write_sitemap_file(hood_slugs, "sitemap-neighborhoods.xml", sitemap_dir)
                segment_files["neighborhoods"] = "sitemap-neighborhoods.xml"

    # Hubs sitemap
    if include_hubs:
        hubs_dir = os.path.join(base, "hubs")
        if os.path.isdir(hubs_dir):
            hub_slugs = []
            for fname in os.listdir(hubs_dir):
                if fname.endswith(".html"):
                    slug = fname.replace(".html", "")
                    hub_slugs.append(slug)
            if hub_slugs:
                _write_sitemap_file(hub_slugs, "sitemap-hubs.xml", sitemap_dir)
                segment_files["hubs"] = "sitemap-hubs.xml"

    # Authority pages sitemap
    if include_authority:
        auth_dir = os.path.join(base, "authority")
        if os.path.isdir(auth_dir):
            auth_slugs = []
            for fname in os.listdir(auth_dir):
                if fname.endswith(".html"):
                    slug = fname.replace(".html", "")
                    auth_slugs.append(slug)
            if auth_slugs:
                _write_sitemap_file(auth_slugs, "sitemap-authority.xml", sitemap_dir)
                segment_files["authority"] = "sitemap-authority.xml"

    # Write sitemap index
    index_entries = []
    for name, sitemap_name in sorted(segment_files.items()):
        index_entries.append(f"""  <sitemap>
    <loc>{SITE_URL}/sitemap/{sitemap_name}</loc>
    <lastmod>{today}</lastmod>
  </sitemap>""")

    index_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(index_entries)}
</sitemapindex>"""

    index_path = os.path.join(sitemap_dir, "sitemap-index.xml")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_xml)
    log.info("Sitemap index written: %s (%d segments)", index_path, len(segment_files))

    return segment_files


# ──────────────────────────────────────────────
# HUB PAGE BUILDER
# ──────────────────────────────────────────────

def _scan_project_articles(project_root: str = "") -> dict[str, list[dict[str, str]]]:
    """Scan project directories for HTML articles grouped by service."""
    from internal_linking_engine import build_hub_page

    if not project_root:
        project_root = PROJECT_ROOT

    # Directories to scan for articles
    scan_dirs = ["articles", "emergency", "same_day", "affordable", "near_me", "24_hour"]
    services_map: dict[str, list[dict[str, str]]] = {s: [] for s in SERVICES}

    for subdir in scan_dirs:
        dirpath = os.path.join(project_root, subdir)
        if not os.path.isdir(dirpath):
            continue
        for fname in os.listdir(dirpath):
            if not fname.endswith(".html") and not fname.endswith(".md"):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                text = open(fpath, encoding="utf-8").read()
            except Exception:
                continue

            # Extract metadata
            title_m = re.search(r"<h1[^>]*>(.*?)</h1>", text)
            title = title_m.group(1) if title_m else fname.replace("_", " ").replace(".html", "").replace(".md", "")
            desc_m = re.search(r'<meta\s+name="description"\s+content="(.*?)"', text)
            description = desc_m.group(1) if desc_m else ""
            words = len(re.findall(r"\w+", text))

            # Determine which service this article belongs to
            lower = fname.lower() + " " + title.lower()
            matched_service = None
            for service in SERVICES:
                if service in lower:
                    matched_service = service
                    break

            if matched_service:
                slug = fname.rsplit("_", 2)[0]  # Remove timestamp
                services_map[matched_service].append({
                    "title": title,
                    "slug": slug,
                    "description": description,
                    "word_count": words,
                })

    return services_map


def build_hubs(project_root: str = "") -> list[str]:
    """Build hub pages for all services and save to projects/hubs/."""
    from internal_linking_engine import build_hub_page

    if not project_root:
        project_root = PROJECT_ROOT

    services_map = _scan_project_articles(project_root)
    hubs_dir = os.path.join(project_root, "hubs")
    os.makedirs(hubs_dir, exist_ok=True)

    # Map services to their hub slugs
    from internal_linking_engine import SERVICE_RELATIONS
    service_to_hub: dict[str, str] = {}
    for s, rel in SERVICE_RELATIONS.items():
        service_to_hub[s] = rel["hub_slug"]

    # Group articles by hub slug instead of service
    hub_groups: dict[str, dict[str, Any]] = {}
    service_by_hub: dict[str, str] = {}  # First service mapped to this hub
    for service, articles in services_map.items():
        if not articles:
            continue
        hub_slug = service_to_hub.get(service, f"{service.replace(' ', '-')}-grand-rapids")
        if hub_slug not in hub_groups:
            hub_groups[hub_slug] = {"articles": [], "service": service}
            service_by_hub[hub_slug] = service
        hub_groups[hub_slug]["articles"].extend(articles)

    generated = []
    for hub_slug, group in hub_groups.items():
        articles = group["articles"]
        service = group["service"]

        # Deduplicate by slug
        seen_slugs: set[str] = set()
        deduped = []
        for a in articles:
            if a["slug"] not in seen_slugs:
                seen_slugs.add(a["slug"])
                deduped.append(a)
        deduped.sort(key=lambda a: a.get("word_count", 0), reverse=True)

        hub_html = build_hub_page(service, deduped)
        if not hub_html:
            continue

        hub_filename = f"{hub_slug}.html"
        hub_path = os.path.join(hubs_dir, hub_filename)
        with open(hub_path, "w", encoding="utf-8") as f:
            f.write(hub_html)
        log.info("Hub page: hubs/%s (%d articles, %d total words)", hub_filename, len(deduped), sum(a.get("word_count", 0) for a in deduped))
        generated.append(hub_path)

    return generated


# ──────────────────────────────────────────────
# NEIGHBORHOOD PAGE GENERATOR
# ──────────────────────────────────────────────

NEIGHBORHOOD_DIRS = ["neighborhoods"]

def build_neighborhood_matrix() -> list[dict[str, Any]]:
    """Build service × neighborhood combinations sorted by priority."""
    pages = []
    for service in SERVICES:
        for hood in NEIGHBORHOODS:
            pages.append({
                "service": service,
                "neighborhood": hood,
                "keyword": f"{service} in {hood}, Grand Rapids".lower(),
                "slug": f"{service.replace(' ', '-')}-{hood.lower().replace(' ', '-')}-grand-rapids",
            })
    pages.sort(key=lambda p: (p["service"], p["neighborhood"]))
    return pages


def _build_neighborhood_page(service: str, neighborhood: str) -> str:
    """Build a single neighborhood × service page using page_blueprints."""
    hood_data = NEIGHBORHOOD_METADATA.get(neighborhood, {})
    kw = f"{service} in {neighborhood}, Grand Rapids"
    slug = f"{service.replace(' ', '-')}-{neighborhood.lower().replace(' ', '-')}-grand-rapids"
    h1 = f"{service.title()} in {neighborhood}, Grand Rapids"

    # Pick blueprint for structural diversity
    bp = pick_blueprint(service, neighborhood, "neighborhood")

    # Build service items
    profile = NICHE_PROFILES.get(service, {})
    items = profile.get("service_items", [])

    # Neighborhood-specific intro
    nearby = hood_data.get("nearby", ["surrounding Grand Rapids neighborhoods"])
    nearby_str = ", ".join(nearby[:3])
    main_streets = hood_data.get("main_streets", [])
    main_streets_str = ", ".join(main_streets[:3])
    zip_str = ", ".join(hood_data.get("zip", [])[:4])
    landmarks_near = hood_data.get("landmarks", [])
    lm_str = ", ".join(landmarks_near[:3])
    desc = hood_data.get("description", f"the {neighborhood} area of Grand Rapids")

    meta_desc = f"Looking for {service} in {neighborhood}, Grand Rapids? We serve all of {neighborhood} and nearby {nearby_str}. Licensed technicians, same-day service available."

    # Intro HTML
    intro = f"""<p>Need {service} in {neighborhood}? Our technicians serve {desc}. We're familiar with the homes along {main_streets_str} and throughout ZIP codes {zip_str} — so we know exactly what to expect when we arrive.</p>
<p>Whether you live near {lm_str} or anywhere else in the neighborhood, our team provides prompt, professional {service}. Same-day service available.</p>"""

    # Areas section with hyper-local detail
    areas_html = f"""<h2>Areas We Serve — {neighborhood} & Nearby</h2>
<p>We provide {service} throughout {neighborhood}, Grand Rapids, and the surrounding areas including {nearby_str}. Our {neighborhood} team covers all nearby neighborhoods and ZIP codes {zip_str}.</p>
<p>If you're on {main_streets_str} or in any of the surrounding blocks, we can have a technician at your door quickly. We know the streets and traffic patterns of {neighborhood} well.</p>"""

    # Service list with count from blueprint
    item_count = min(bp.get("service_item_count", 5), len(items))
    services_html = ""
    if items:
        lis = "\n".join(f"<li><p>{item}</p></li>" for item in items[:item_count])
        services_html = f"""<h2>{service.title()} Services We Offer in {neighborhood}</h2>
<ul>
{lis}
</ul>"""

    # Landmark-specific content
    landmark_html = ""
    if landmarks_near:
        landmark_html = f"""<h2>Conveniently Located Near {lm_str}</h2>
<p>Our {service} team serves the entire {neighborhood} area, including homes and businesses near {lm_str}. Being based in Grand Rapids means we can reach any part of {neighborhood} within minutes.</p>"""

    # FAQ
    faqs = profile.get("faqs", [])
    faq_count = min(bp.get("faq_count", 5), 6)
    faq_html = ""
    if faqs:
        items_faq = "\n".join(
            f"""<div class="faq-item">
<h3>{q}</h3>
<p>{a}</p>
</div>"""
            for q, a in faqs[:faq_count]
        )
        faq_html = f"""<h2>Frequently Asked Questions About {service.title()} in {neighborhood}</h2>
{items_faq}"""

    # Why-choose-us
    why_us_html = f"""<h2>Why Choose Us for {service.title()} in {neighborhood}</h2>
<ul>
<li>Licensed and insured in Michigan — serving {neighborhood} since 2015</li>
<li>Same-day service available throughout {neighborhood} and nearby areas</li>
<li>Upfront pricing — no hidden fees, no overtime charges</li>
<li>We know {neighborhood} — familiar with local homes, streets, and building styles</li>
<li>Satisfaction guaranteed on every {service} job</li>
</ul>"""

    # Brand section
    brand_html = ""
    brands = profile.get("brands", [])
    if brands:
        brands_str = ", ".join(brands)
        brand_html = f"""<h2>Brands We Work With</h2>
<p>{profile.get('cta_sub', 'Licensed technicians')}. We service all major brands including {brands_str}.</p>"""

    # Build context for blueprint renderer
    context = {
        "service": service,
        "city": neighborhood,
        "modifier": "neighborhood",
        "keyword": kw,
        "slug": slug,
        "keyword_title": h1,
        "blueprint": bp,
    }

    # Pre-rendered sections that override SECTION_RENDERERS
    context["intro_html"] = intro
    context["areas_html"] = areas_html
    context["services_html"] = services_html
    context["why_us_html"] = why_us_html
    context["brands_html"] = brand_html
    context["faq_html"] = faq_html

    # Wrap in full HTML template
    body_sections = render_blueprint(bp, context)
    body_sections += f"\n{landmark_html}" if landmark_html else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{h1}</title>
    <meta name="description" content="{meta_desc}">
    <link rel="canonical" href="https://yoursite.com/{slug}">
</head>
<body>
<h1>{h1}</h1>
{body_sections}
</body>
</html>"""

    return html


def generate_neighborhood_pages(limit: int = 0) -> list[dict[str, Any]]:
    """Generate neighborhood × service pages with structural diversity.

    Args:
        limit: Max pages (0 = all, default 391 = 23 services × 17 neighborhoods).

    Returns:
        List of dicts with page metadata.
    """
    log.info("Building neighborhood × service matrix...")
    matrix = build_neighborhood_matrix()
    total = len(matrix)
    log.info("Matrix has %d total combinations (services=%d × neighborhoods=%d)",
             total, len(SERVICES), len(NEIGHBORHOODS))

    batch = matrix[:limit] if limit > 0 else matrix
    generated = []

    out_dir = os.path.join(PROJECT_ROOT, "neighborhoods")
    os.makedirs(out_dir, exist_ok=True)

    for i, entry in enumerate(batch):
        service = entry["service"]
        hood = entry["neighborhood"]
        keyword = entry["keyword"]
        slug = entry["slug"]

        log.info("[%d/%d] Generating: %s", i + 1, len(batch), keyword)

        html = _build_neighborhood_page(service, hood)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{slug}_{timestamp}.html"
        filepath = os.path.join(out_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        log.info("Emitted: neighborhoods/%s", filename)
        generated.append({
            "service": service,
            "neighborhood": hood,
            "keyword": keyword,
            "slug": slug,
            "filepath": filepath,
        })

    log.info("Neighborhood batch complete: %d pages generated in %s",
             len(generated), out_dir)
    return generated


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    import argparse

    parser = argparse.ArgumentParser(description="Programmatic SEO Page Expander")
    parser.add_argument("--limit", type=int, default=25, help="Number of pages to generate")
    parser.add_argument("--sitemap", action="store_true", help="Generate flat sitemap after pages")
    parser.add_argument("--segmented-sitemap", action="store_true", help="Generate segmented sitemaps (per-modifier + neighborhoods + hubs)")
    parser.add_argument("--hubs", action="store_true", help="Build hub pages from existing articles")
    parser.add_argument("--neighborhoods", action="store_true", help="Generate neighborhood-specific pages")
    parser.add_argument("--project", type=str, default="grand_rapids", help="Project name (default: grand_rapids)")
    args = parser.parse_args()

    if args.hubs:
        hubs = build_hubs()
        print(f"Built {len(hubs)} hub pages")
        for h in hubs:
            print(f"  {os.path.relpath(h)}")
    elif args.neighborhoods:
        pages = generate_neighborhood_pages(limit=args.limit)
        print(f"Generated {len(pages)} neighborhood pages in {PROJECT_ROOT}")
        for p in pages:
            print(f"  /{p['slug']}/ → {os.path.relpath(p['filepath'])}")
    else:
        pages = generate_batch(limit=args.limit)

        if args.sitemap:
            sitemap_path = os.path.join(PROJECT_ROOT, "sitemap", "sitemap.xml")
            generate_sitemap(pages, sitemap_path)
            print(f"Sitemap: {sitemap_path}")

        if args.segmented_sitemap:
            segs = generate_segmented_sitemaps(pages, include_neighborhoods=True, include_hubs=True, include_authority=True)
            print(f"Segmented sitemaps ({len(segs)} segments):")
            for name, fname in sorted(segs.items()):
                print(f"  {name}: sitemap/{fname}")

        print(f"Generated {len(pages)} pages in {PROJECT_ROOT}")
        for p in pages:
            print(f"  /{p['slug']}/ → {os.path.relpath(p['filepath'])}")
