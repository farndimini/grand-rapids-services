"""
internal_linking_engine.py — Internal Linking Engine

Builds a connected topical network: service links, geo links, hub pages, sitemaps.
Transforms isolated articles into a crawlable authority cluster.
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Any

log = logging.getLogger("linking_engine")

SITE_URL = os.environ.get("SEO_AGENT_SITE_URL", "https://yoursite.com")
CITY = "Grand Rapids"
STATE = "MI"

# ──────────────────────────────────────────────
# 1. SERVICE RELATION GRAPH
# ──────────────────────────────────────────────

SERVICE_RELATIONS: dict[str, dict[str, Any]] = {
    "appliance repair": {
        "hub_slug": "appliance-repair-grand-rapids",
        "hub_title": "Appliance Repair Services in Grand Rapids, MI",
        "category": "Home Appliance Services",
        "cross_services": ["refrigerator repair", "washer repair", "dryer repair", "dishwasher repair", "oven repair", "microwave repair"],
        "related": [
            {"slug": "refrigerator-repair-grand-rapids", "label": "Refrigerator Repair", "keywords": ["refrigerator repair", "fridge repair", "refrigerator service"]},
            {"slug": "washer-repair-grand-rapids", "label": "Washer & Dryer Repair", "keywords": ["washer repair", "dryer repair", "washing machine repair"]},
            {"slug": "dishwasher-repair-grand-rapids", "label": "Dishwasher Repair", "keywords": ["dishwasher repair", "dishwasher service"]},
            {"slug": "oven-repair-grand-rapids", "label": "Oven & Stove Repair", "keywords": ["oven repair", "stove repair", "range repair", "cooktop repair"]},
            {"slug": "microwave-repair-grand-rapids", "label": "Microwave Repair", "keywords": ["microwave repair", "microwave service"]},
        ],
    },
    "garage door repair": {
        "hub_slug": "garage-door-services-grand-rapids",
        "hub_title": "Garage Door Services in Grand Rapids, MI",
        "category": "Garage Door Services",
        "cross_services": ["garage door installation", "garage door opener", "fencing", "concrete"],
        "related": [
            {"slug": "garage-door-installation-grand-rapids", "label": "Garage Door Installation", "keywords": ["garage door installation", "new garage door", "garage door replacement"]},
            {"slug": "emergency-garage-door-repair-grand-rapids", "label": "Emergency Garage Door Repair", "keywords": ["emergency garage door", "24/7 garage door", "urgent garage door repair"]},
            {"slug": "garage-door-opener-repair-grand-rapids", "label": "Garage Door Opener Repair", "keywords": ["opener repair", "garage door opener", "motor repair"]},
            {"slug": "broken-garage-door-spring-grand-rapids", "label": "Broken Spring Replacement", "keywords": ["broken spring", "spring replacement", "garage door spring"]},
        ],
    },
    "garage door installation": {
        "hub_slug": "garage-door-services-grand-rapids",
        "hub_title": "Garage Door Installation in Grand Rapids, MI",
        "category": "Garage Door Services",
        "cross_services": ["garage door repair", "concrete", "electrical", "fencing"],
        "related": [
            {"slug": "garage-door-repair-grand-rapids", "label": "Garage Door Repair", "keywords": ["garage door repair", "garage door service", "door repair"]},
            {"slug": "emergency-garage-door-repair-grand-rapids", "label": "Emergency Garage Door Services", "keywords": ["emergency repair", "urgent garage door"]},
            {"slug": "garage-door-opener-repair-grand-rapids", "label": "Opener Installation & Repair", "keywords": ["garage door opener", "smart opener"]},
        ],
    },
    "basement remodel": {
        "hub_slug": "basement-remodeling-grand-rapids",
        "hub_title": "Basement Remodeling Services in Grand Rapids, MI",
        "category": "Home Remodeling",
        "cross_services": ["plumbing", "electrical", "flooring", "concrete", "water damage restoration", "painting"],
        "related": [
            {"slug": "basement-finishing-grand-rapids", "label": "Basement Finishing", "keywords": ["basement finishing", "finish basement"]},
            {"slug": "basement-bathroom-grand-rapids", "label": "Basement Bathroom Installation", "keywords": ["basement bathroom", "basement shower"]},
            {"slug": "home-theater-construction-grand-rapids", "label": "Home Theater Construction", "keywords": ["home theater", "media room"]},
            {"slug": "shower-remodel-grand-rapids", "label": "Shower & Bath Remodeling", "keywords": ["shower remodel", "bathroom remodel", "bath renovation"]},
        ],
    },
    "shower remodel": {
        "hub_slug": "bathroom-remodeling-grand-rapids",
        "hub_title": "Bathroom & Shower Remodeling in Grand Rapids, MI",
        "category": "Home Remodeling",
        "cross_services": ["plumbing", "flooring", "painting", "bathroom remodeling"],
        "related": [
            {"slug": "basement-remodel-grand-rapids", "label": "Basement Remodeling", "keywords": ["basement remodel", "basement renovation"]},
            {"slug": "tub-to-shower-conversion-grand-rapids", "label": "Tub to Shower Conversion", "keywords": ["tub to shower", "shower conversion"]},
            {"slug": "tile-installation-grand-rapids", "label": "Tile Installation", "keywords": ["tile installation", "tile work", "custom tile"]},
            {"slug": "bathroom-remodel-grand-rapids", "label": "Full Bathroom Remodeling", "keywords": ["bathroom remodel", "bath renovation"]},
        ],
    },
    # ── Plumbing ──
    "plumbing": {
        "hub_slug": "plumbing-services-grand-rapids",
        "hub_title": "Plumbing Services in Grand Rapids, MI",
        "category": "Plumbing & Water Services",
        "cross_services": ["water damage restoration", "water heater repair", "drain cleaning", "kitchen remodeling", "bathroom remodeling", "hvac"],
        "related": [
            {"slug": "water-heater-repair-grand-rapids", "label": "Water Heater Repair", "keywords": ["water heater repair", "water heater replacement", "tankless water heater"]},
            {"slug": "drain-cleaning-grand-rapids", "label": "Drain Cleaning", "keywords": ["drain cleaning", "clogged drain", "drain unclogging"]},
            {"slug": "sewer-line-repair-grand-rapids", "label": "Sewer Line Repair", "keywords": ["sewer line repair", "sewer replacement", "sewer camera inspection"]},
            {"slug": "leak-detection-grand-rapids", "label": "Leak Detection", "keywords": ["leak detection", "water leak", "slab leak", "pipe leak repair"]},
            {"slug": "frozen-pipe-repair-grand-rapids", "label": "Frozen Pipe Repair", "keywords": ["frozen pipe", "burst pipe", "pipe thawing"]},
        ],
    },
    # ── HVAC ──
    "hvac": {
        "hub_slug": "hvac-services-grand-rapids",
        "hub_title": "HVAC Services in Grand Rapids, MI",
        "category": "Heating & Cooling",
        "cross_services": ["electrical", "plumbing", "duct cleaning", "thermostat installation", "indoor air quality"],
        "related": [
            {"slug": "ac-repair-grand-rapids", "label": "AC Repair", "keywords": ["ac repair", "air conditioning repair", "central ac service"]},
            {"slug": "furnace-repair-grand-rapids", "label": "Furnace Repair", "keywords": ["furnace repair", "furnace replacement", "heating repair"]},
            {"slug": "heat-pump-service-grand-rapids", "label": "Heat Pump Service", "keywords": ["heat pump repair", "heat pump installation", "mini split service"]},
            {"slug": "duct-cleaning-grand-rapids", "label": "Duct Cleaning", "keywords": ["duct cleaning", "air duct cleaning", "dryer vent cleaning"]},
            {"slug": "boiler-repair-grand-rapids", "label": "Boiler Repair", "keywords": ["boiler repair", "boiler replacement", "steam boiler service"]},
        ],
    },
    # ── Electrical ──
    "electrical": {
        "hub_slug": "electrical-services-grand-rapids",
        "hub_title": "Electrical Services in Grand Rapids, MI",
        "category": "Electrical Services",
        "cross_services": ["hvac", "kitchen remodeling", "bathroom remodeling", "landscaping", "deck and patio"],
        "related": [
            {"slug": "panel-upgrade-grand-rapids", "label": "Electrical Panel Upgrade", "keywords": ["electrical panel upgrade", "breaker panel", "fuse box upgrade"]},
            {"slug": "wiring-repair-grand-rapids", "label": "Wiring Repair", "keywords": ["electrical wiring", "home rewiring", "wiring repair"]},
            {"slug": "generator-installation-grand-rapids", "label": "Generator Installation", "keywords": ["generator installation", "standby generator", "whole house generator"]},
            {"slug": "ev-charger-installation-grand-rapids", "label": "EV Charger Installation", "keywords": ["ev charger installation", "tesla charger", "electric car charger"]},
        ],
    },
    # ── Roofing ──
    "roofing": {
        "hub_slug": "roofing-services-grand-rapids",
        "hub_title": "Roofing Services in Grand Rapids, MI",
        "category": "Exterior Services",
        "cross_services": ["siding", "window replacement", "gutter installation", "tree service", "water damage restoration"],
        "related": [
            {"slug": "roof-repair-grand-rapids", "label": "Roof Repair", "keywords": ["roof repair", "leaky roof repair", "shingle repair", "roof leak"]},
            {"slug": "roof-replacement-grand-rapids", "label": "Roof Replacement", "keywords": ["roof replacement", "new roof", "reroofing"]},
            {"slug": "metal-roofing-grand-rapids", "label": "Metal Roofing", "keywords": ["metal roofing", "steel roof", "standing seam"]},
            {"slug": "storm-damage-roof-repair-grand-rapids", "label": "Storm Damage Repair", "keywords": ["storm damage repair", "hail damage roof", "wind damage roof"]},
        ],
    },
    # ── Water Damage Restoration ──
    "water damage restoration": {
        "hub_slug": "water-damage-restoration-grand-rapids",
        "hub_title": "Water Damage Restoration in Grand Rapids, MI",
        "category": "Restoration Services",
        "cross_services": ["plumbing", "roofing", "mold remediation", "basement remodel", "flooring"],
        "related": [
            {"slug": "water-extraction-grand-rapids", "label": "Water Extraction", "keywords": ["water extraction", "water removal", "standing water removal"]},
            {"slug": "basement-waterproofing-grand-rapids", "label": "Basement Waterproofing", "keywords": ["basement waterproofing", "wet basement repair"]},
            {"slug": "flood-damage-repair-grand-rapids", "label": "Flood Damage Repair", "keywords": ["flood damage repair", "flood restoration", "flooded basement cleanup"]},
            {"slug": "sewage-cleanup-grand-rapids", "label": "Sewage Cleanup", "keywords": ["sewage cleanup", "sewer backup cleanup", "biohazard cleanup"]},
        ],
    },
    # ── Mold Remediation ──
    "mold remediation": {
        "hub_slug": "mold-remediation-grand-rapids",
        "hub_title": "Mold Remediation Services in Grand Rapids, MI",
        "category": "Restoration Services",
        "cross_services": ["water damage restoration", "basement remodel", "hvac", "painting", "bathroom remodeling"],
        "related": [
            {"slug": "mold-inspection-grand-rapids", "label": "Mold Inspection", "keywords": ["mold inspection", "mold testing", "mold detection"]},
            {"slug": "black-mold-removal-grand-rapids", "label": "Black Mold Removal", "keywords": ["black mold removal", "toxic mold removal", "mold abatement"]},
            {"slug": "attic-mold-remediation-grand-rapids", "label": "Attic Mold Remediation", "keywords": ["attic mold removal", "attic mold remediation"]},
            {"slug": "crawlspace-mold-treatment-grand-rapids", "label": "Crawlspace Mold Treatment", "keywords": ["crawlspace mold", "crawlspace remediation"]},
        ],
    },
    # ── Flooring ──
    "flooring": {
        "hub_slug": "flooring-services-grand-rapids",
        "hub_title": "Flooring Services in Grand Rapids, MI",
        "category": "Flooring & Surfaces",
        "cross_services": ["basement remodel", "kitchen remodeling", "bathroom remodeling", "concrete", "painting"],
        "related": [
            {"slug": "hardwood-flooring-grand-rapids", "label": "Hardwood Flooring", "keywords": ["hardwood flooring", "solid hardwood", "engineered hardwood"]},
            {"slug": "laminate-flooring-grand-rapids", "label": "Laminate Flooring", "keywords": ["laminate flooring", "laminate installation", "waterproof laminate"]},
            {"slug": "luxury-vinyl-plank-grand-rapids", "label": "Luxury Vinyl Plank", "keywords": ["luxury vinyl plank", "lvp flooring", "vinyl plank flooring"]},
            {"slug": "carpet-installation-grand-rapids", "label": "Carpet Installation", "keywords": ["carpet installation", "carpet replacement", "carpet padding"]},
        ],
    },
    # ── Window Replacement ──
    "window replacement": {
        "hub_slug": "window-replacement-grand-rapids",
        "hub_title": "Window Replacement in Grand Rapids, MI",
        "category": "Exterior Services",
        "cross_services": ["siding", "roofing", "painting", "concrete"],
        "related": [
            {"slug": "vinyl-window-installation-grand-rapids", "label": "Vinyl Window Installation", "keywords": ["vinyl windows", "vinyl window replacement"]},
            {"slug": "energy-efficient-windows-grand-rapids", "label": "Energy Efficient Windows", "keywords": ["energy efficient windows", "low-e windows", "energy star windows"]},
            {"slug": "bay-window-installation-grand-rapids", "label": "Bay Window Installation", "keywords": ["bay window installation", "bow window", "garden window"]},
            {"slug": "storm-window-installation-grand-rapids", "label": "Storm Window Installation", "keywords": ["storm windows", "storm window installation", "impact windows"]},
        ],
    },
    # ── Siding ──
    "siding": {
        "hub_slug": "siding-services-grand-rapids",
        "hub_title": "Siding Services in Grand Rapids, MI",
        "category": "Exterior Services",
        "cross_services": ["roofing", "window replacement", "painting", "concrete"],
        "related": [
            {"slug": "vinyl-siding-installation-grand-rapids", "label": "Vinyl Siding Installation", "keywords": ["vinyl siding", "vinyl siding installation", "insulated vinyl siding"]},
            {"slug": "fiber-cement-siding-grand-rapids", "label": "Fiber Cement Siding", "keywords": ["fiber cement siding", "hardie board", "cement board siding"]},
            {"slug": "siding-repair-grand-rapids", "label": "Siding Repair", "keywords": ["siding repair", "siding replacement", "damaged siding repair"]},
            {"slug": "soffit-fascia-installation-grand-rapids", "label": "Soffit & Fascia Installation", "keywords": ["soffit installation", "fascia repair", "soffit replacement"]},
        ],
    },
    # ── Concrete ──
    "concrete": {
        "hub_slug": "concrete-services-grand-rapids",
        "hub_title": "Concrete Services in Grand Rapids, MI",
        "category": "Concrete & Masonry",
        "cross_services": ["deck and patio", "landscaping", "garage door installation", "basement remodel"],
        "related": [
            {"slug": "concrete-driveway-grand-rapids", "label": "Concrete Driveway", "keywords": ["concrete driveway", "driveway replacement", "driveway installation"]},
            {"slug": "stamped-concrete-grand-rapids", "label": "Stamped Concrete", "keywords": ["stamped concrete", "decorative concrete", "patterned concrete"]},
            {"slug": "concrete-patio-grand-rapids", "label": "Concrete Patio", "keywords": ["concrete patio", "patio installation", "outdoor concrete"]},
            {"slug": "foundation-repair-grand-rapids", "label": "Foundation Repair", "keywords": ["foundation repair", "foundation crack repair", "foundation leveling"]},
        ],
    },
    # ── Deck & Patio ──
    "deck and patio": {
        "hub_slug": "deck-patio-services-grand-rapids",
        "hub_title": "Deck & Patio Services in Grand Rapids, MI",
        "category": "Outdoor Living",
        "cross_services": ["concrete", "landscaping", "fencing", "painting", "electrical"],
        "related": [
            {"slug": "deck-building-grand-rapids", "label": "Deck Building", "keywords": ["deck builder", "deck construction", "custom deck", "wood deck"]},
            {"slug": "composite-decking-grand-rapids", "label": "Composite Decking", "keywords": ["composite decking", "trex decking", "timbertech deck"]},
            {"slug": "patio-installation-grand-rapids", "label": "Patio Installation", "keywords": ["patio installation", "paver patio", "flagstone patio"]},
            {"slug": "pergola-construction-grand-rapids", "label": "Pergola Construction", "keywords": ["pergola", "pergola construction", "outdoor covering"]},
        ],
    },
    # ── Kitchen Remodeling ──
    "kitchen remodeling": {
        "hub_slug": "kitchen-remodeling-grand-rapids",
        "hub_title": "Kitchen Remodeling in Grand Rapids, MI",
        "category": "Home Remodeling",
        "cross_services": ["plumbing", "electrical", "flooring", "painting", "bathroom remodeling"],
        "related": [
            {"slug": "cabinet-installation-grand-rapids", "label": "Cabinet Installation", "keywords": ["kitchen cabinets", "cabinet installation", "custom cabinets"]},
            {"slug": "countertop-replacement-grand-rapids", "label": "Countertop Replacement", "keywords": ["countertop replacement", "granite countertops", "quartz countertops"]},
            {"slug": "backsplash-installation-grand-rapids", "label": "Backsplash Installation", "keywords": ["backsplash installation", "kitchen backsplash", "tile backsplash"]},
            {"slug": "kitchen-design-grand-rapids", "label": "Kitchen Design", "keywords": ["kitchen design", "kitchen remodel design", "custom kitchen design"]},
        ],
    },
    # ── Bathroom Remodeling ──
    "bathroom remodeling": {
        "hub_slug": "bathroom-remodeling-grand-rapids",
        "hub_title": "Bathroom Remodeling in Grand Rapids, MI",
        "category": "Home Remodeling",
        "cross_services": ["plumbing", "flooring", "shower remodel", "painting", "electrical"],
        "related": [
            {"slug": "full-bathroom-remodel-grand-rapids", "label": "Full Bathroom Remodel", "keywords": ["bathroom remodel", "full bathroom renovation", "bathroom makeover"]},
            {"slug": "bathtub-replacement-grand-rapids", "label": "Bathtub Replacement", "keywords": ["bathtub replacement", "soaking tub", "freestanding tub"]},
            {"slug": "vanity-installation-grand-rapids", "label": "Vanity Installation", "keywords": ["bathroom vanity", "vanity installation", "double vanity"]},
            {"slug": "accessible-bathroom-grand-rapids", "label": "Accessibility Bathroom Updates", "keywords": ["walk in tub", "accessible bathroom", "grab bar installation"]},
        ],
    },
    # ── Painting ──
    "painting": {
        "hub_slug": "painting-services-grand-rapids",
        "hub_title": "Painting Services in Grand Rapids, MI",
        "category": "Painting & Finishing",
        "cross_services": ["drywall repair", "flooring", "deck and patio", "kitchen remodeling", "bathroom remodeling"],
        "related": [
            {"slug": "interior-painting-grand-rapids", "label": "Interior Painting", "keywords": ["interior painting", "interior house painter", "room painting"]},
            {"slug": "exterior-painting-grand-rapids", "label": "Exterior Painting", "keywords": ["exterior painting", "house exterior painting", "siding painting"]},
            {"slug": "cabinet-painting-grand-rapids", "label": "Cabinet Painting", "keywords": ["cabinet painting", "cabinet refinishing", "kitchen cabinet painting"]},
            {"slug": "drywall-repair-grand-rapids", "label": "Drywall Repair", "keywords": ["drywall repair", "drywall installation", "hole in wall repair"]},
        ],
    },
    # ── Fencing ──
    "fencing": {
        "hub_slug": "fencing-services-grand-rapids",
        "hub_title": "Fencing Services in Grand Rapids, MI",
        "category": "Fencing & Gates",
        "cross_services": ["landscaping", "concrete", "deck and patio", "garage door installation"],
        "related": [
            {"slug": "privacy-fence-grand-rapids", "label": "Privacy Fence", "keywords": ["privacy fence", "privacy fencing", "private fence installation"]},
            {"slug": "wood-fence-grand-rapids", "label": "Wood Fence", "keywords": ["wood fence", "cedar fence", "picket fence", "wood privacy fence"]},
            {"slug": "vinyl-fence-grand-rapids", "label": "Vinyl Fence", "keywords": ["vinyl fence", "pvc fence", "white vinyl fence", "maintenance free fence"]},
            {"slug": "fence-repair-grand-rapids", "label": "Fence Repair", "keywords": ["fence repair", "fence replacement", "gate repair"]},
        ],
    },
    # ── Landscaping ──
    "landscaping": {
        "hub_slug": "landscaping-services-grand-rapids",
        "hub_title": "Landscaping Services in Grand Rapids, MI",
        "category": "Outdoor Living",
        "cross_services": ["tree service", "concrete", "deck and patio", "fencing", "irrigation"],
        "related": [
            {"slug": "landscape-design-grand-rapids", "label": "Landscape Design", "keywords": ["landscape design", "landscape architecture", "garden design"]},
            {"slug": "retaining-walls-grand-rapids", "label": "Retaining Walls", "keywords": ["retaining wall", "segmental retaining wall", "block wall"]},
            {"slug": "irrigation-system-installation-grand-rapids", "label": "Irrigation System Installation", "keywords": ["irrigation system", "sprinkler system", "lawn sprinklers"]},
            {"slug": "outdoor-lighting-grand-rapids", "label": "Outdoor Lighting", "keywords": ["outdoor lighting", "landscape lighting", "path lighting"]},
        ],
    },
    # ── Tree Service ──
    "tree service": {
        "hub_slug": "tree-services-grand-rapids",
        "hub_title": "Tree Services in Grand Rapids, MI",
        "category": "Tree Care & Removal",
        "cross_services": ["landscaping", "roofing", "water damage restoration", "fencing"],
        "related": [
            {"slug": "tree-removal-grand-rapids", "label": "Tree Removal", "keywords": ["tree removal", "dangerous tree removal", "large tree removal"]},
            {"slug": "stump-grinding-grand-rapids", "label": "Stump Grinding", "keywords": ["stump grinding", "stump removal", "tree stump grinding"]},
            {"slug": "storm-damage-cleanup-grand-rapids", "label": "Storm Damage Cleanup", "keywords": ["storm damage cleanup", "fallen tree removal", "storm tree removal"]},
            {"slug": "tree-trimming-grand-rapids", "label": "Tree Trimming & Pruning", "keywords": ["tree trimming", "tree pruning", "branch trimming"]},
        ],
    },
    # ── Pest Control ──
    "pest control": {
        "hub_slug": "pest-control-grand-rapids",
        "hub_title": "Pest Control in Grand Rapids, MI",
        "category": "Pest Management",
        "cross_services": ["mold remediation", "landscaping", "tree service", "water damage restoration"],
        "related": [
            {"slug": "termite-control-grand-rapids", "label": "Termite Control", "keywords": ["termite control", "termite treatment", "termite inspection"]},
            {"slug": "rodent-removal-grand-rapids", "label": "Rodent Removal", "keywords": ["rodent removal", "mouse exterminator", "rat control"]},
            {"slug": "bed-bug-treatment-grand-rapids", "label": "Bed Bug Treatment", "keywords": ["bed bug treatment", "bed bug exterminator", "bed bug heat treatment"]},
            {"slug": "mosquito-control-grand-rapids", "label": "Mosquito Control", "keywords": ["mosquito control", "mosquito treatment", "yard mosquito spray"]},
        ],
    },
}

DEFAULT_SERVICE = {
    "hub_slug": "home-services-grand-rapids",
    "hub_title": "Home Services in Grand Rapids, MI",
    "category": "Home Services",
    "related": [],
}

# ──────────────────────────────────────────────
# 2. CITY-SERVICE MATRIX
# ──────────────────────────────────────────────

SERVICE_CITIES = {
    "Grand Rapids": {"slug": "grand-rapids", "neighborhoods": ["East Hills", "Heritage Hill", "Belknap Lookout", "Midtown"]},
    "Kentwood": {"slug": "kentwood", "neighborhoods": ["South Kent", "Paris Ridge"]},
    "Wyoming": {"slug": "wyoming-mi", "neighborhoods": ["Rogers Plaza", "Godfrey-Lee"]},
    "East Grand Rapids": {"slug": "east-grand-rapids", "neighborhoods": ["Gaslight Village", "Wealthy Street"]},
    "Walker": {"slug": "walker-mi", "neighborhoods": ["Standale", "Walker Station"]},
    "Ada": {"slug": "ada-mi", "neighborhoods": ["Ada Village"]},
    "Cascade": {"slug": "cascade-mi", "neighborhoods": ["Cascade Township"]},
    "Rockford": {"slug": "rockford-mi", "neighborhoods": ["Rockford Village"]},
    "Grandville": {"slug": "grandville-mi", "neighborhoods": ["Grandville Village"]},
}

# Modifiers for service anchor variety
MODIFIERS = [
    "professional", "same-day", "emergency", "local", "expert",
    "affordable", "quality", "licensed", "reliable", "trusted",
    "fast", "full-service", "residential", "commercial",
]

# ──────────────────────────────────────────────
# 3. ANCHOR GENERATOR
# ──────────────────────────────────────────────

def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-")


def generate_anchors(service_label: str, city: str = CITY) -> list[str]:
    """Generate varied anchor text for a given service + city."""
    kw = service_label.lower()
    anchors = [
        f"{kw} in {city}",
        f"{kw} {city}",
        f"{city} {kw}",
        f"local {kw}",
        f"{kw} services in {city}",
        f"{kw} near me",
    ]
    # Add 2 random modifiers
    import random
    mods = random.sample(MODIFIERS, min(2, len(MODIFIERS)))
    anchors.append(f"{mods[0]} {kw} in {city}")
    anchors.append(f"{mods[1]} {kw}")
    return anchors


def get_city_anchors(city_name: str, city_slug: str) -> list[str]:
    """Generate anchor variations for a city page."""
    return [
        f"in {city_name}",
        f"{city_name}, {STATE}",
        f"serving {city_name}",
        f"{city_name} area",
        f"near {city_name}",
    ]


# ──────────────────────────────────────────────
# 4. CONTEXTUAL LINK INJECTOR
# ──────────────────────────────────────────────

def _detect_service_from_keyword(keyword: str) -> str | None:
    """Detect which service a keyword belongs to."""
    kw = keyword.lower()
    for service in SERVICE_RELATIONS:
        if service in kw:
            return service
    return None


def inject_contextual_links(article: str, keyword: str, max_links: int = 4) -> str:
    """
    Inject contextual internal links into article HTML.
    Finds mentions of related services and links them.
    """
    service = _detect_service_from_keyword(keyword)
    if not service or service not in SERVICE_RELATIONS:
        return article

    rel = SERVICE_RELATIONS[service]
    related = rel.get("related", [])
    if not related:
        return article

    # Gather all linkable keywords from related services
    link_targets: list[tuple[str, str, str]] = []  # (keyword, slug, display_label)
    for r in related:
        for kw in r.get("keywords", []):
            link_targets.append((kw.lower(), r["slug"], r["label"]))

    # Inject links contextually into paragraph text
    links_added = 0
    used_anchors: set[str] = set()

    def _link_replacer(m: re.Match) -> str:
        nonlocal links_added
        if links_added >= max_links:
            return m.group(0)

        matched_text = m.group(0).strip()
        matched_lower = matched_text.lower()

        for target_kw, target_slug, target_label in link_targets:
            if target_kw in used_anchors:
                continue
            # Check if this mention matches the target keyword
            if target_kw in matched_lower and matched_lower not in used_anchors:
                # Don't link if already a link
                if m.group(0).startswith("<a ") or "<a href" in m.group(0):
                    continue

                # Choose anchor text — prefer the matched text, but keep it natural
                anchor_text = matched_text
                # Truncate if too long
                if len(anchor_text) > 80:
                    anchor_text = target_label

                url = f"{SITE_URL}/{target_slug}"
                replacement = f'<a href="{url}" rel="nofollow">{anchor_text}</a>'
                used_anchors.add(matched_lower)
                used_anchors.add(target_kw)
                links_added += 1
                return replacement

        return m.group(0)

    # Process only paragraph text (not headings, not existing links, not scripts)
    paragraphs = re.finditer(r'(<p[^>]*>)(.*?)(</p>)', article, re.DOTALL | re.IGNORECASE)
    for p_match in paragraphs:
        if links_added >= max_links:
            break
        open_tag = p_match.group(1)
        body = p_match.group(2)
        close_tag = p_match.group(3)

        # Skip if body already has links to our targets
        if any(target_slug in body for _, target_slug, _ in link_targets):
            continue

        # Try to match keyword phrases in the paragraph body
        new_body = body
        for target_kw, target_slug, target_label in link_targets:
            if target_kw in used_anchors:
                continue
            if links_added >= max_links:
                break

            # Find keyword occurrence
            idx = new_body.lower().find(target_kw)
            if idx < 0:
                continue

            # Don't link inside existing HTML tags
            before = new_body[:idx]
            if before.rfind("<") > before.rfind(">"):
                continue

            # Don't link if already near a link
            nearby = new_body[max(0, idx - 50):idx + len(target_kw) + 50]
            if 'href="' in nearby or '</a>' in nearby:
                continue

            # Extract the actual text for anchor
            anchor_text = new_body[idx:idx + len(target_kw)]
            # Title-case for better readability
            words = anchor_text.split()
            if words and words[0][0].islower() and new_body[idx - 1:idx] in ("", " "):
                pass  # keep case as-is for flow

            url = f"{SITE_URL}/{target_slug}"
            linked = f'<a href="{url}" rel="nofollow">{anchor_text}</a>'
            new_body = new_body[:idx] + linked + new_body[idx + len(target_kw):]
            used_anchors.add(target_kw.lower())
            links_added += 1
            log.info("[LINKS] Injected: %s → %s", anchor_text, target_slug)

        # Replace paragraph body
        article = article[:p_match.start(2)] + new_body + article[p_match.end(2):]

    log.info("[LINKS] Total links injected: %d/%d for '%s'", links_added, max_links, keyword)
    return article


# ──────────────────────────────────────────────
# 5. RELATED SERVICES SECTION INJECTOR
# ──────────────────────────────────────────────

def inject_related_services_section(article: str, keyword: str) -> str:
    """Inject a 'Related Services' section at the end of the article."""
    service = _detect_service_from_keyword(keyword)
    if not service or service not in SERVICE_RELATIONS:
        return article

    rel = SERVICE_RELATIONS[service]
    related = rel.get("related", [])
    if not related:
        return article

    # Check if already present
    if "related services" in article.lower() or "related service" in article.lower():
        return article

    items_html = ""
    for r in related[:5]:
        url = f"{SITE_URL}/{r['slug']}"
        items_html += f'<li><a href="{url}" rel="nofollow">{r["label"]} in {CITY}</a></li>\n'

    # Also link to hub
    hub_url = f"{SITE_URL}/{rel['hub_slug']}"
    section_html = f"""<h2>Related {rel['category']} Services in {CITY}</h2>
<p>Explore our full range of {rel['category'].lower()} in the {CITY} area:</p>
<ul>
{items_html}</ul>
<p>Or visit our <a href="{hub_url}" rel="nofollow">{rel['hub_title']}</a> page for complete service details.</p>
<hr>"""

    # Inject before </body>
    body_end = article.rfind("</body>")
    if body_end >= 0:
        article = article[:body_end] + section_html + "\n" + article[body_end:]

    return article


# ──────────────────────────────────────────────
# 6. GEOGRAPHIC LINK INJECTOR
# ──────────────────────────────────────────────

def inject_geo_links(article: str, keyword: str) -> str:
    """Inject links to city/neighborhood service pages from Areas Served section."""
    service = _detect_service_from_keyword(keyword)
    if not service:
        return article

    service_slug = _slugify(service)

    # Find "Areas We Serve" section
    areas_match = re.search(
        r'<h2[^>]*>.*?(?:areas?\s*(?:we\s*)?serve|service\s*area).*?</h2>\s*(.*?)(?=<h2|<script|</body>)',
        article, re.IGNORECASE | re.DOTALL,
    )
    if not areas_match:
        return article

    section_body = areas_match.group(1)
    new_body = section_body

    for city_name, city_info in SERVICE_CITIES.items():
        city_slug = city_info["slug"]
        if city_name.lower() in new_body.lower():
            url = f"{SITE_URL}/{service_slug}-{city_slug}"
            linked = f'<a href="{url}" rel="nofollow">{city_name}</a>'
            # Replace first plain-text occurrence only
            pattern = re.compile(re.escape(city_name), re.IGNORECASE)
            new_body = pattern.sub(linked, new_body, count=1)

    if new_body != section_body:
        article = article.replace(section_body, new_body, 1)
        log.info("[GEO_LINKS] City links injected for '%s'", keyword)

    return article


# ──────────────────────────────────────────────
# 7. HUB PAGE BUILDER
# ──────────────────────────────────────────────

def _get_hub_data(service: str) -> tuple:
    """Get hub title and slug for a service, falling back to SERVICE_TAXONOMY."""
    if service in SERVICE_RELATIONS:
        rel = SERVICE_RELATIONS[service]
        return rel["hub_title"], rel["hub_slug"], rel.get("category", "Home Services")

    # Try SERVICE_TAXONOMY
    try:
        from service_taxonomy import SERVICE_TAXONOMY
        tax = SERVICE_TAXONOMY.get(service)
        if tax:
            hub_title = tax.get("hub_title", f"{tax['label']} Services in {CITY}, {STATE}")
            hub_slug = tax.get("hub_slug", f"{service.replace(' ', '-')}-{CITY.lower().replace(' ', '-')}")
            return hub_title, hub_slug, tax.get("category", "Home Services")
    except ImportError:
        pass

    # Generic fallback
    label = service.replace("-", " ").replace("_", " ").title()
    hub_title = f"{label} Services in {CITY}, {STATE}"
    hub_slug = f"{service.replace(' ', '-').replace('_', '-')}-{CITY.lower().replace(' ', '-')}"
    return hub_title, hub_slug, "Home Services"


def build_hub_page(service: str, articles: list[dict[str, str]]) -> str:
    """
    Build a hub/pillar page for a service category.
    articles: list of dicts with keys: title, slug, description, word_count
    """
    hub_title, hub_slug, category = _get_hub_data(service)

    today = datetime.now().strftime("%Y-%m-%d")

    service_items_html = ""
    for a in articles:
        url = f"{SITE_URL}/{a['slug']}"
        desc = a.get("description", f"Professional {a['title'].lower()} in {CITY}, {STATE}.")
        service_items_html += f"""
<div class="service-card" style="border:1px solid #ddd;border-radius:8px;padding:16px;margin:12px 0;">
    <h3><a href="{url}" rel="nofollow">{a['title']}</a></h3>
    <p>{desc}</p>
    <p style="font-size:0.85em;color:#666;">Approx. {a.get('word_count', 'N/A')} words</p>
</div>"""

    # Build schema for the hub page
    hub_schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": hub_title,
        "description": f"Complete guide to {service} services in {CITY}, {STATE}.",
        "hasPart": [
            {"@type": "Article", "name": a["title"], "url": f"{SITE_URL}/{a['slug']}"}
            for a in articles
        ],
    }

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{hub_title}</title>
    <meta name="description" content="Professional {service} in {CITY}, {STATE}. Same-day service, licensed technicians, free estimates. Serving all West Michigan.">
    <link rel="canonical" href="{SITE_URL}/{hub_slug}">
    <script type="application/ld+json">{json.dumps(hub_schema, ensure_ascii=False)}</script>
</head>
<body itemscope itemtype="https://schema.org/CollectionPage">
<h1>{hub_title}</h1>
<p>Welcome to our complete guide to {service} services in {CITY}, {STATE}. Below you will find detailed service pages covering every aspect of {service} in our service area.</p>

<h2>Our {category} Services</h2>
{service_items_html}

<h2>Service Areas</h2>
<p>We provide {service} throughout {CITY} and all surrounding communities including:</p>
<ul>
{''.join(f'<li>{name}</li>' for name in SERVICE_CITIES.keys())}
</ul>

<h2>Why Choose Us</h2>
<p>With years of experience serving {CITY} homeowners, our licensed and insured technicians provide same-day service, upfront pricing, and a satisfaction guarantee on all work.</p>

<h2>Contact Us</h2>
<p>Call <a href="tel:+16165550147">(616) 555-0147</a> for a free estimate or same-day service.</p>
</body>
</html>"""
    return html


# ──────────────────────────────────────────────
# 8. SITEMAP EMITTER
# ──────────────────────────────────────────────

def build_sitemap(pages: list[dict[str, Any]]) -> str:
    """
    Build sitemap.xml from all pages.
    pages: list of dicts with keys: slug, lastmod (optional), priority (optional)
    """
    today = datetime.now().strftime("%Y-%m-%d")

    urls = ""
    for page in pages:
        slug = page["slug"]
        lastmod = page.get("lastmod", today)
        priority = page.get("priority", 0.8)
        changefreq = page.get("changefreq", "weekly")
        urls += f"""  <url>
    <loc>{SITE_URL}/{slug}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>
  </url>
"""

    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}</urlset>"""
    return sitemap


# ──────────────────────────────────────────────
# 9. MAIN ENHANCE FUNCTION (for pipeline integration)
# ──────────────────────────────────────────────

def enhance_with_links(article: str, keyword: str, intent: str) -> str:
    """
    Main entry point: apply all internal linking enhancements to an article.
    Called from local_intelligence.enhance_article() or directly from modules.py.
    """
    if intent != "LOCAL_SERVICE":
        return article

    article = inject_contextual_links(article, keyword)
    article = inject_geo_links(article, keyword)
    article = inject_related_services_section(article, keyword)

    return article
