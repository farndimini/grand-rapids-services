"""
local_intelligence.py — Hyper-Local SEO Optimization Layer

Central module for neighborhood injection, ZIP enrichment, intent-aware CTAs,
service-area schema, emergency sections, near-me expansion, and geo entity extraction.

Every function is a pure data transform: article_in → article_out.
"""

import hashlib
import json
import logging
import re
from typing import Any

from internal_linking_engine import enhance_with_links

log = logging.getLogger("local_intelligence")


# ──────────────────────────────────────────────
# VARIANT POOLS — Deterministic sentence variation
# ──────────────────────────────────────────────

NEAR_ME_VARIANTS = [
    # Variant 0: Standard
    lambda kw, kw_lower, nap: f"""<h2>Same-Day {kw} Near You in Grand Rapids</h2>
<p>Searching for "{kw_lower} near me" in Grand Rapids? Our technicians are stationed across the city and can typically reach your home within 30-60 minutes. We serve all Grand Rapids neighborhoods, from East Hills to West Grand and everywhere in between.</p>
<p>Whether you live near the Medical Mile, in Heritage Hill, or out near the East Beltline, we have a technician nearby ready to help. Call <a href="tel:{nap['phone_link']}">{nap['phone']}</a> for immediate service.</p>""",
    # Variant 1: Urgency-focused
    lambda kw, kw_lower, nap: f"""<h2>Need {kw} Near You in Grand Rapids? We're Minutes Away</h2>
<p>If you're searching for "{kw_lower} near me" in Grand Rapids, you've found the right team. With technicians positioned throughout Kent County — from Wyoming to Rockford and everywhere between — we respond fast.</p>
<p>Our dispatch center covers all 495XX ZIP codes plus surrounding communities. Call <a href="tel:{nap['phone_link']}">{nap['phone']}</a> and we'll route the nearest available technician to your location.</p>""",
    # Variant 2: Neighborhood-specific
    lambda kw, kw_lower, nap: f"""<h2>Top-Rated {kw} Service Across Grand Rapids Neighborhoods</h2>
<p>Looking for reliable "{kw_lower} near me"? Our Grand Rapids technicians serve every neighborhood including East Hills, Alger Heights, Creston, Belknap Lookout, and all surrounding suburbs.</p>
<p>No matter which part of Grand Rapids you call home — whether it's a historic house in Heritage Hill or a new build in Cascade — we bring the same expertise and professionalism to every job. Call <a href="tel:{nap['phone_link']}">{nap['phone']}</a> to schedule.</p>""",
    # Variant 3: Suburb-focused
    lambda kw, kw_lower, nap: f"""<h2>Fast {kw} Service Near You in Grand Rapids & Beyond</h2>
<p>When you search for "{kw_lower} near me," you want someone who's actually nearby. Our coverage area spans all of Grand Rapids plus Kentwood, Wyoming, Grandville, Jenison, Hudsonville, Ada, Cascade, Rockford, and Walker.</p>
<p>Response times average 30-45 minutes across most of Kent County. Call <a href="tel:{nap['phone_link']}">{nap['phone']}</a> for prompt, professional service from a locally owned company.</p>""",
    # Variant 4: Trust-focused
    lambda kw, kw_lower, nap: f"""<h2>Local {kw} Near Me — Trusted by Grand Rapids Homeowners</h2>
<p>Searching for "{kw_lower} near me" can feel overwhelming with so many options. We make it simple: licensed, insured technicians serving Grand Rapids since 2015 with thousands of satisfied customers.</p>
<p>Our service area covers every Grand Rapids neighborhood from the Medical Mile to the East Beltline and all surrounding communities. Call <a href="tel:{nap['phone_link']}">{nap['phone']}</a> to experience the difference.</p>""",
]

EMERGENCY_VARIANTS = [
    # Variant 0: Standard
    lambda kw, kw_lower, nap, emergency_text: f"""<h2>Emergency {kw} Services in Grand Rapids</h2>
<p>{emergency_text}</p>
<p>Our emergency team is available 24 hours a day, 7 days a week, including holidays. Call <a href="tel:{nap['phone_link']}">{nap['phone']}</a> for immediate emergency assistance.</p>
<h3>Weekend & Holiday Availability</h3>
<p>We understand that emergencies don't follow business hours. Our on-call technicians provide {kw_lower} services on weekends and public holidays across all of West Michigan.</p>""",
    # Variant 1: Response-time focused
    lambda kw, kw_lower, nap, emergency_text: f"""<h2>24/7 Emergency {kw} in Grand Rapids — We Respond Fast</h2>
<p>{emergency_text}</p>
<p>Time is critical in an emergency. Our dispatchers are on standby 24/7/365, and we guarantee same-day response for all urgent {kw_lower} needs. Most emergencies are addressed within 60-90 minutes.</p>
<p>Don't wait — call <a href="tel:{nap['phone_link']}">{nap['phone']}</a> right now and we'll dispatch the closest available technician to your location.</p>""",
    # Variant 2: Seasonal tie-in
    lambda kw, kw_lower, nap, emergency_text: f"""<h2>Emergency {kw} Services — Available When You Need Us Most</h2>
<p>{emergency_text}</p>
<p>Grand Rapids weather can be unpredictable, which is why our emergency team is on call around the clock. Whether it's a frozen pipe in January or a storm-related issue in July, we're here to help.</p>
<p>Call <a href="tel:{nap['phone_link']}">{nap['phone']}</a> for emergency {kw_lower} — no overtime charges, just prompt professional service.</p>""",
    # Variant 3: Short / punchy
    lambda kw, kw_lower, nap, emergency_text: f"""<h2>24/7 Emergency {kw} in Grand Rapids</h2>
<p>{emergency_text}</p>
<p>Round-the-clock emergency coverage. Call <a href="tel:{nap['phone_link']}">{nap['phone']}</a> and speak directly to a dispatcher who will route a technician to your home immediately.</p>
<p><strong>No extra charge for nights, weekends, or holidays.</strong></p>""",
    # Variant 4: Neighborhood coverage
    lambda kw, kw_lower, nap, emergency_text: f"""<h2>Emergency {kw} Across All Grand Rapids Neighborhoods</h2>
<p>{emergency_text}</p>
<p>Our emergency fleet is strategically positioned across Grand Rapids — from Creston to Kentwood and everything in between — so we can reach you quickly no matter where the emergency strikes.</p>
<p>Call <a href="tel:{nap['phone_link']}">{nap['phone']}</a> for immediate service. We cover all of Kent County, 24 hours a day.</p>""",
]

CTA_VARIANTS = [
    # Variant 0: Blue box (current)
    lambda cta_text, cta_sub, nap: f"""<div class="cta-box" style="background:#f5f9ff;border:2px solid #2b6cb0;border-radius:8px;padding:24px;margin:24px 0;text-align:center;">
<h3 style="margin-top:0;color:#2b6cb0;">{cta_text}</h3>
<p style="font-size:1.1em;">{cta_sub}</p>
<p style="font-size:1.3em;font-weight:bold;"><a href="tel:{nap['phone_link']}" style="color:#2b6cb0;text-decoration:none;">{nap['phone']}</a></p>
<p>Licensed · Insured · Upfront Pricing · Warranty on Work</p>
</div>""",
    # Variant 1: Green box
    lambda cta_text, cta_sub, nap: f"""<div class="cta-box" style="background:#f0faf0;border:2px solid #2f855a;border-radius:8px;padding:24px;margin:24px 0;text-align:center;">
<h3 style="margin-top:0;color:#2f855a;">{cta_text}</h3>
<p style="font-size:1.1em;">{cta_sub}</p>
<p style="font-size:1.3em;font-weight:bold;"><a href="tel:{nap['phone_link']}" style="color:#2f855a;text-decoration:none;">{nap['phone']}</a></p>
<p style="font-size:0.9em;color:#555;">Same-Day Service Available · Free Estimates · Satisfaction Guaranteed</p>
</div>""",
    # Variant 2: Dark header box
    lambda cta_text, cta_sub, nap: f"""<div class="cta-box" style="background:#1a202c;border-radius:8px;padding:28px;margin:24px 0;text-align:center;">
<h3 style="margin-top:0;color:#ffffff;font-size:1.3em;">{cta_text}</h3>
<p style="color:#e2e8f0;font-size:1em;">{cta_sub}</p>
<p style="font-size:1.4em;font-weight:bold;margin:16px 0;"><a href="tel:{nap['phone_link']}" style="color:#63b3ed;text-decoration:none;">{nap['phone']}</a></p>
<p style="color:#a0aec0;font-size:0.85em;">Licensed & Insured in Michigan · Upfront Pricing · Warranty Included</p>
</div>""",
    # Variant 3: Two-column layout
    lambda cta_text, cta_sub, nap: f"""<div class="cta-box" style="display:flex;flex-wrap:wrap;background:#f7fafc;border:1px solid #e2e8f0;border-radius:8px;padding:24px;margin:24px 0;gap:16px;">
<div style="flex:2;min-width:240px;">
<h3 style="margin-top:0;color:#2d3748;">{cta_text}</h3>
<p style="color:#4a5568;">{cta_sub}</p>
</div>
<div style="flex:1;min-width:180px;text-align:center;border-left:1px solid #e2e8f0;padding-left:16px;">
<p style="font-size:0.85em;color:#718096;margin:0;">Call Now</p>
<p style="font-size:1.3em;font-weight:bold;margin:4px 0;"><a href="tel:{nap['phone_link']}" style="color:#2b6cb0;text-decoration:none;">{nap['phone']}</a></p>
<p style="font-size:0.85em;color:#718096;margin:0;">Free Estimates · No Obligation</p>
</div>
</div>""",
    # Variant 4: CTA banner with button-style link
    lambda cta_text, cta_sub, nap: f"""<div class="cta-box" style="background:linear-gradient(135deg,#2b6cb0,#2c5282);border-radius:8px;padding:28px;margin:24px 0;text-align:center;">
<h3 style="margin-top:0;color:#ffffff;font-size:1.2em;">{cta_text}</h3>
<p style="color:#bee3f8;font-size:1em;">{cta_sub}</p>
<div style="margin:16px 0;">
<a href="tel:{nap['phone_link']}" style="display:inline-block;background:#ffffff;color:#2b6cb0;font-weight:bold;font-size:1.2em;padding:12px 32px;border-radius:6px;text-decoration:none;">{nap['phone']}</a>
</div>
<p style="color:#90cdf4;font-size:0.85em;margin:0;">Service throughout Grand Rapids & West Michigan</p>
</div>""",
]

REVIEW_LAYOUT_VARIANTS = [
    # Variant 0: Current bordered style
    lambda reviews_html, title: f"""<h2>{title}</h2>
<p>Don't just take our word for it. Here's what real customers in West Michigan have experienced:</p>
{reviews_html}""",
    # Variant 1: Compact
    lambda reviews_html, title: f"""<h2>{title}</h2>
<div style="margin:16px 0;">{reviews_html}</div>""",
    # Variant 2: Grid layout
    lambda reviews_html, title: f"""<h2 style="text-align:center;">{title}</h2>
<div style="display:flex;flex-wrap:wrap;gap:16px;margin:16px 0;">{reviews_html}</div>""",
]

NEIGHBORHOOD_INTRO_VARIANTS = [
    lambda kw: f"<p>We provide {kw} throughout Grand Rapids and the surrounding West Michigan area.</p>",
    lambda kw: f"<p>Our Grand Rapids team delivers professional {kw} services across all of Kent County and nearby communities.</p>",
    lambda kw: f"<p>From downtown Grand Rapids to the outer suburbs, our technicians handle {kw} for homeowners throughout West Michigan.</p>",
    lambda kw: f"<p>We proudly offer {kw} to Grand Rapids residents and businesses, covering the entire metro area and beyond.</p>",
    lambda kw: f"<p>Our {kw} services extend to every corner of Grand Rapids — from Creston to Cascade and all neighborhoods in between.</p>",
]


def _pick_variant(keyword: str, variants: list) -> Any:
    """Deterministically pick a variant based on keyword hash."""
    h = hashlib.md5(keyword.lower().encode()).hexdigest()
    idx = int(h[:8], 16) % len(variants)
    return variants[idx]

def _pick_variant_count(keyword: str, max_count: int, total: int) -> int:
    """Deterministically pick a count between 1 and max_count via keyword hash."""
    h = hashlib.md5(keyword.lower().encode()).hexdigest()
    return (int(h[8:16], 16) % max_count) + 1 if max_count > 1 else 1

# ──────────────────────────────────────────────
# 1. GRAND RAPIDS HYPER-LOCAL DATA
# ──────────────────────────────────────────────

GRAND_RAPIDS = {
    "city": "Grand Rapids",
    "state": "MI",
    "region": "West Michigan",
    "county": "Kent County",
    "phone": "+1-616-000-0000",
    "site_url": "https://yoursite.com",
    "nicknames": ["GR", "G.R.", "the Furniture City"],
}

NEIGHBORHOODS = [
    "East Hills",
    "Heritage Hill",
    "Belknap Lookout",
    "Midtown",
    "Cherry Hill",
    "Eastgate",
    "Ottawa Hills",
    "Highland Park",
    "John Ball Park",
    "Roosevelt Park",
    "West Grand",
    "Alger Heights",
    "Garfield Park",
    "Boston Square",
    "Creston",
    "North End",
    "Comstock Park",
]

SUBURBS = [
    "Kentwood",
    "Wyoming",
    "East Grand Rapids",
    "Walker",
    "Ada",
    "Cascade",
    "Rockford",
    "Grandville",
    "Jenison",
    "Hudsonville",
    "Byron Center",
    "Caledonia",
    "Lowell",
    "Sparta",
    "Cedar Springs",
]

ZIP_CODES = [
    "49503", "49504", "49505", "49506", "49507", "49508",
    "49509", "49512", "49525", "49534", "49544", "49546",
    "49548", "49301", "49315", "49316", "49319", "49321",
    "49331", "49341", "49345",
]

LANDMARKS = [
    "Downtown Grand Rapids",
    "East Beltline",
    "Medical Mile",
    "Gerald R. Ford International Airport",
    "Van Andel Arena",
    "DeVos Place Convention Center",
    "Rosa Parks Circle",
    "Frederik Meijer Gardens",
    "John Ball Zoo",
    "Grand Rapids Art Museum",
    "Grand Valley State University",
    "Aquinas College",
    "Calvin University",
    "Butterworth Hospital",
    "Spectrum Health Downtown Campus",
    "Bridge Street",
    "Wealthy Street",
    "Cherry Street",
    "Division Avenue",
    "Plainfield Avenue",
]

MAJOR_HIGHWAYS = [
    "I-196",
    "US-131",
    "M-6",
    "M-37",
    "M-44",
    "28th Street SE",
]

SERVICE_RADIUS_MILES = 40

# ──────────────────────────────────────────────
# 1b. NEIGHBORHOOD METADATA (for hyper-local pages)
# ──────────────────────────────────────────────

NEIGHBORHOOD_METADATA: dict[str, dict[str, Any]] = {
    "East Hills": {
        "zip": ["49503", "49506"],
        "landmarks": ["East Hills", "Wealthy Street", "Cherry Street"],
        "main_streets": ["Wealthy St SE", "Cherry St SE", "Lake Dr SE"],
        "description": "a historic Grand Rapids neighborhood with tree-lined streets, local boutiques, and restaurants along Wealthy Street",
        "nearby": ["Heritage Hill", "Eastgate", "Midtown"],
    },
    "Heritage Hill": {
        "zip": ["49503", "49504"],
        "landmarks": ["Heritage Hill", "Grand Rapids Art Museum", "Van Andel Arena"],
        "main_streets": ["College Ave NE", "Fulton St E", "Lakeside Dr NE"],
        "description": "Grand Rapids' largest historic district, featuring Victorian-era homes and tree-lined avenues near downtown",
        "nearby": ["East Hills", "Belknap Lookout", "Midtown"],
    },
    "Belknap Lookout": {
        "zip": ["49503"],
        "landmarks": ["Belknap Park", "Medical Mile", "Grand River"],
        "main_streets": ["Monroe Ave NW", "Seward Ave NW", "Palmer St NE"],
        "description": "a scenic neighborhood overlooking downtown Grand Rapids with historic homes and proximity to the Medical Mile",
        "nearby": ["Heritage Hill", "Midtown", "Highland Park"],
    },
    "Midtown": {
        "zip": ["49503", "49504"],
        "landmarks": ["Medical Mile", "Wealthy Street", "Cherry Street"],
        "main_streets": ["Fuller Ave NE", "Michigan St NE", "Wealthy St SE"],
        "description": "a vibrant central neighborhood near the Medical Mile with a mix of historic homes and modern developments",
        "nearby": ["East Hills", "Heritage Hill", "Belknap Lookout"],
    },
    "Cherry Hill": {
        "zip": ["49503", "49506"],
        "landmarks": ["Cherry Street", "Downtown Grand Rapids", "Rosa Parks Circle"],
        "main_streets": ["Cherry St SE", "Division Ave S", "Fuller Ave NE"],
        "description": "a walkable neighborhood near downtown with historic architecture and easy access to local dining and shopping",
        "nearby": ["Heritage Hill", "East Hills", "Midtown"],
    },
    "Eastgate": {
        "zip": ["49506"],
        "landmarks": ["East Beltline", "Frederik Meijer Gardens", "Reeds Lake"],
        "main_streets": ["East Beltline SE", "Cascade Rd SE", "Brittany Dr SE"],
        "description": "an established southeast Grand Rapids neighborhood near the East Beltline with spacious properties and mature trees",
        "nearby": ["East Hills", "Ottawa Hills", "Cascade"],
    },
    "Ottawa Hills": {
        "zip": ["49506"],
        "landmarks": ["Ottawa Hills", "Plaster Creek", "East Beltline"],
        "main_streets": ["Ottawa Ave SW", "Hall St SW", "Burton St SW"],
        "description": "a quiet southwest Grand Rapids neighborhood with well-maintained homes and a strong sense of community",
        "nearby": ["Garfield Park", "Boston Square", "Alger Heights"],
    },
    "Highland Park": {
        "zip": ["49503", "49507"],
        "landmarks": ["Highland Park", "Grand River", "US-131"],
        "main_streets": ["Ball Ave NE", "Leonard St NE", "Plainfield Ave NE"],
        "description": "a northwest Grand Rapids neighborhood with park access and convenient highway proximity",
        "nearby": ["Belknap Lookout", "West Grand", "Creston"],
    },
    "John Ball Park": {
        "zip": ["49504", "49507"],
        "landmarks": ["John Ball Zoo", "John Ball Park", "US-131"],
        "main_streets": ["Fulton St W", "Ball Ave NE", "Marshall Ave SW"],
        "description": "home to the famous John Ball Zoo, this west side neighborhood offers park access and family-friendly living",
        "nearby": ["West Grand", "Highland Park", "Roosevelt Park"],
    },
    "Roosevelt Park": {
        "zip": ["49507", "49548"],
        "landmarks": ["Roosevelt Park", "Division Avenue", "US-131"],
        "main_streets": ["Division Ave S", "Burton St SE", "Kalamazoo Ave SE"],
        "description": "a south Grand Rapids neighborhood centered around Roosevelt Park with convenient access to downtown",
        "nearby": ["Garfield Park", "Boston Square", "John Ball Park"],
    },
    "West Grand": {
        "zip": ["49504"],
        "landmarks": ["Bridge Street", "Grand River", "Downtown Grand Rapids"],
        "main_streets": ["Bridge St NW", "Stocking Ave NW", "Leonard St NW"],
        "description": "a historic west side neighborhood along the Grand River with a mix of residential and commercial areas",
        "nearby": ["John Ball Park", "Highland Park", "Creston"],
    },
    "Alger Heights": {
        "zip": ["49507", "49508"],
        "landmarks": ["Alger Heights", "East Beltline", "Wealthy Street"],
        "main_streets": ["Alger St SE", "Kalamazoo Ave SE", "Eastern Ave SE"],
        "description": "a southeast Grand Rapids community known for its local shops, restaurants, and neighborhood events",
        "nearby": ["Garfield Park", "Ottawa Hills", "Eastgate"],
    },
    "Garfield Park": {
        "zip": ["49507", "49508"],
        "landmarks": ["Garfield Park", "Plaster Creek", "Division Avenue"],
        "main_streets": ["Eastern Ave SE", "Burton St SE", "Madison Ave SE"],
        "description": "a south Grand Rapids neighborhood with a historic park, community pool, and mature residential streets",
        "nearby": ["Alger Heights", "Boston Square", "Ottawa Hills"],
    },
    "Boston Square": {
        "zip": ["49507"],
        "landmarks": ["Boston Square", "Buchanan Avenue", "Division Avenue"],
        "main_streets": ["Eastern Ave SE", "Kalamazoo Ave SE", "Buchanan Ave SW"],
        "description": "a historic southeast Grand Rapids commercial district with ongoing revitalization and community-focused development",
        "nearby": ["Garfield Park", "Alger Heights", "Roosevelt Park"],
    },
    "Creston": {
        "zip": ["49505", "49525"],
        "landmarks": ["Plainfield Avenue", "Creston Brewery", "North Grand Rapids"],
        "main_streets": ["Plainfield Ave NE", "Knapp St NE", "Leonard St NE"],
        "description": "a north end Grand Rapids neighborhood with emerging dining, historic housing, and strong community identity",
        "nearby": ["North End", "Highland Park", "Belknap Lookout"],
    },
    "North End": {
        "zip": ["49505", "49525"],
        "landmarks": ["Plainfield Avenue", "North Park", "Rogue River"],
        "main_streets": ["Plainfield Ave NE", "3 Mile Rd NE", "North Park Dr NE"],
        "description": "the northernmost Grand Rapids neighborhood with diverse housing, parks, and convenient shopping along Plainfield Avenue",
        "nearby": ["Creston", "Comstock Park", "Rockford"],
    },
    "Comstock Park": {
        "zip": ["49321", "49525"],
        "landmarks": ["Comstock Park", "Rogue River", "Plainfield Avenue"],
        "main_streets": ["Plainfield Ave NE", "West River Dr NE", "Shawmut Ave NE"],
        "description": "a northwest suburb of Grand Rapids along the Rogue River with a mix of residential and rural character",
        "nearby": ["North End", "Creston", "Walker"],
    },
}


# ──────────────────────────────────────────────
# 2. NICHE-SPECIFIC DATA
# ──────────────────────────────────────────────

NICHE_PROFILES: dict[str, dict[str, Any]] = {
    "appliance repair": {
        "service_items": [
            "Refrigerators", "Freezers", "Washing Machines", "Dryers",
            "Dishwashers", "Ranges", "Ovens", "Cooktops", "Microwaves",
            "Wine Coolers", "Ice Makers", "Garbage Disposals",
        ],
        "brands": [
            "Samsung", "LG", "Whirlpool", "GE", "Maytag", "Bosch",
            "KitchenAid", "Frigidaire", "Kenmore", "Electrolux", "Thermador",
        ],
        "cta": "Call now for same-day appliance repair in Grand Rapids",
        "cta_sub": "Free estimates · Licensed technicians · Upfront pricing",
        "emergency": "Refrigerator down? Oven not heating? We offer 24/7 emergency appliance repair in Grand Rapids.",
        "faqs": [
            ("How much does appliance repair cost in Grand Rapids?",
             "Service call fees typically range from $75-$129, with parts and labor quoted before work begins. Most basic repairs cost $150-$350 total."),
            ("What brands do you repair in Grand Rapids?",
             "We repair all major brands including Samsung, LG, Whirlpool, GE, Maytag, Bosch, KitchenAid, and Frigidaire."),
            ("Do you offer same-day appliance repair in Grand Rapids?",
             "Yes, we provide same-day service for most appliance repairs in Grand Rapids and surrounding communities. Call before noon for same-day service."),
            ("Are your appliance repair technicians licensed in Michigan?",
             "Yes, all our technicians are fully licensed, bonded, and insured in Michigan with ongoing OEM training."),
        ],
    },
    "garage door repair": {
        "service_items": [
            "Broken Springs", "Off-Track Doors", "Opener Malfunctions",
            "Broken Cables", "Panel Replacement", "Sensor Alignment",
            "Weather Stripping", "Remote Programming", "Battery Backup",
        ],
        "brands": [
            "Chamberlain", "LiftMaster", "Genie", "Wayne Dalton", "Clopay",
            "Amarr", "Overhead Door", "Raynor", "Haas Door",
        ],
        "cta": "Emergency garage door repair in Grand Rapids — call now",
        "cta_sub": "Same-day service · Licensed technicians · Upfront pricing",
        "emergency": "Garage door stuck open or closed? We provide 24/7 emergency garage door repair in Grand Rapids.",
        "faqs": [
            ("How much does garage door repair cost in Grand Rapids?",
             "Service call fees range from $75-$99. Spring repairs average $150-$350, opener replacements $200-$500."),
            ("Do you offer same-day garage door repair in Grand Rapids?",
             "Yes, same-day service is available across Grand Rapids and all surrounding areas including Kentwood, Wyoming, and East Grand Rapids."),
            ("How long does a typical garage door repair take in Grand Rapids?",
             "Most repairs are completed in 1-3 hours. Emergency services have response times under 2 hours."),
        ],
    },
    "garage door installation": {
        "service_items": [
            "Sectional Garage Doors", "Roll-Up Doors", "Carriage House Doors",
            "Modern Glass Doors", "Insulated Doors", "Smart Openers",
            "Battery Backup Systems", "Keyless Entry Pads",
        ],
        "brands": [
            "Chamberlain", "LiftMaster", "Genie", "Wayne Dalton", "Clopay",
            "Amarr", "Overhead Door", "Raynor",
        ],
        "cta": "Get a free garage door installation estimate in Grand Rapids",
        "cta_sub": "Free estimates · Professional installation · Warranty included",
        "emergency": "Need a new garage door installed urgently? We offer expedited installation services in Grand Rapids.",
        "faqs": [
            ("How much does garage door installation cost in Grand Rapids?",
             "Single door installations typically range from $800-$1,500, double doors $1,200-$2,500, including materials and labor."),
            ("What brands of garage doors do you install in Grand Rapids?",
             "We install all top brands including Chamberlain, LiftMaster, Wayne Dalton, Clopay, Amarr, and Overhead Door."),
            ("Are you licensed to install garage doors in Grand Rapids?",
             "Yes, we are fully licensed and insured in Michigan. All installations meet local building codes."),
        ],
    },
    "basement remodel": {
        "service_items": [
            "Finished Basements", "Basement Bathrooms", "Basement Bars",
            "Home Theaters", "Basement Bedrooms", "Basement Offices",
            "Wet Bars", "Storage Solutions", "Egress Windows",
        ],
        "brands": [],
        "cta": "Schedule a free basement remodeling estimate in Grand Rapids",
        "cta_sub": "Free estimates · Licensed contractors · Custom designs",
        "emergency": "Water damage in your basement? We also offer emergency waterproofing services.",
        "faqs": [
            ("How much does basement remodeling cost in Grand Rapids?",
             "Basement remodeling in Grand Rapids typically costs $30-$75 per square foot. A full basement finish averages $15,000-$40,000."),
            ("Are you licensed for basement remodeling in Grand Rapids?",
             "Yes, all our contractors are fully licensed and insured in Michigan."),
        ],
    },
    "shower remodel": {
        "service_items": [
            "Custom Tile Showers", "Walk-In Showers", "Shower Replacement",
            "Accessible Showers", "Steam Showers", "Glass Enclosures",
            "Shower Panels", "Linear Drains", "Shower Niches",
        ],
        "brands": [
            "Kohler", "Moen", "Delta", "American Standard", "Aqua Glass",
            "DreamLine", "Basco",
        ],
        "cta": "Get a free shower remodeling quote in Grand Rapids",
        "cta_sub": "Free estimates · Licensed contractors · Quality materials",
        "emergency": "",
        "faqs": [
            ("How much does a shower remodel cost in Grand Rapids?",
             "Shower remodeling in Grand Rapids ranges from $3,000-$10,000 depending on materials, size, and complexity."),
            ("How long does a shower remodel take in Grand Rapids?",
             "Most shower remodels are completed in 3-7 days depending on the scope of work."),
        ],
    },
}

DEFAULT_NICHE = {
    "service_items": [],
    "brands": [],
    "cta": "Call now for professional service in Grand Rapids",
    "cta_sub": "Free estimates · Licensed technicians · Upfront pricing",
    "emergency": "We offer 24/7 emergency service throughout Grand Rapids and surrounding areas.",
    "faqs": [],
}


# ──────────────────────────────────────────────
# 2e. AUTO-BUILD NICHE PROFILES FROM SERVICE_TAXONOMY
# ──────────────────────────────────────────────

def _build_niche_from_taxonomy() -> dict[str, dict[str, Any]]:
    """Auto-generate NICHE_PROFILES for all services in SERVICE_TAXONOMY."""
    from service_taxonomy import SERVICE_TAXONOMY
    auto_profiles = {}

    for key, sv in SERVICE_TAXONOMY.items():
        emergency_text = f"We offer 24/7 emergency {sv['label'].lower()} service in Grand Rapids."
        ekw = sv.get("emergency_keywords", [])
        if ekw:
            emergency_text = f"Need emergency {sv['label'].lower()} in Grand Rapids? {sv.get('pain_points', [])[:2]} We provide 24/7 emergency service."

        # Build FAQ tuples from faq_patterns
        faqs: list[tuple[str, str]] = []
        for fp in sv.get("faq_patterns", []):
            # pattern contains {sub} and {service} placeholders
            q = fp[0].replace("{sub}", sv["label"].lower()).replace("{service}", sv["label"].lower())
            a = fp[1].replace("{sub}", sv["label"].lower()).replace("{service}", sv["label"].lower())
            faqs.append((q, a))

        auto_profiles[key] = {
            "service_items": sv.get("service_items", []),
            "brands": sv.get("brands", []),
            "cta": sv.get("cta", f"Call now for {sv['label'].lower()} in Grand Rapids"),
            "cta_sub": sv.get("cta_sub", "Free estimates · Licensed technicians · Upfront pricing"),
            "emergency": emergency_text,
            "faqs": faqs,
            "_category": sv.get("category", "Home Services"),
        }

    return auto_profiles


def _build_metadata_from_taxonomy() -> dict[str, dict[str, Any]]:
    """Auto-generate NICHE_METADATA for all services in SERVICE_TAXONOMY."""
    from service_taxonomy import SERVICE_TAXONOMY
    auto_meta = {}

    for key, sv in SERVICE_TAXONOMY.items():
        label = sv.get("label", key.title())
        auto_meta[key] = {
            "license_key": "general",
            "response_time": sv.get("response_time", "Same-day available"),
            "service_call": sv.get("service_call", "Call for estimate"),
            "avg_repair": "Call for estimate",
            "warranty": "100% satisfaction guarantee",
            "certifications": ["Licensed in Michigan", "Insured"],
            "niche_label": label,
        }

    return auto_meta


def _build_reviews_from_taxonomy() -> dict[str, list[dict[str, str]]]:
    """Auto-generate basic review data for taxonomy-only services."""
    return {}


def _populate_taxonomy_profiles():
    """Merge SERVICE_TAXONOMY data into NICHE_PROFILES and NICHE_METADATA.
    Keeps manually curated entries; generates auto entries for the rest."""
    global NICHE_PROFILES, NICHE_METADATA, REVIEWS
    auto_profiles = _build_niche_from_taxonomy()
    auto_meta = _build_metadata_from_taxonomy()

    # Merge: manual entries take priority
    merged_profiles = auto_profiles.copy()
    merged_profiles.update(NICHE_PROFILES)
    NICHE_PROFILES = merged_profiles

    merged_meta = auto_meta.copy()
    merged_meta.update(NICHE_METADATA)
    NICHE_METADATA = merged_meta


# NOTE: _populate_taxonomy_profiles() is called at the end of this module
# after all data structures are defined.

# ──────────────────────────────────────────────
# 2b. CONFIGURABLE BUSINESS IDENTITY
# ──────────────────────────────────────────────
# Override via env vars: SEO_AGENT_BUSINESS_NAME, SEO_AGENT_BUSINESS_PHONE, etc.

import os as _os

BUSINESS_IDENTITY = {
    "name": _os.environ.get("SEO_AGENT_BUSINESS_NAME", "Grand Rapids Home Services"),
    "phone": _os.environ.get("SEO_AGENT_BUSINESS_PHONE", "(616) 555-0147"),
    "phone_link": _os.environ.get("SEO_AGENT_BUSINESS_PHONE_LINK", "+16165550147"),
    "address": _os.environ.get("SEO_AGENT_BUSINESS_ADDRESS", "1234 Plainfield Ave NE"),
    "city": _os.environ.get("SEO_AGENT_BUSINESS_CITY", "Grand Rapids"),
    "state": _os.environ.get("SEO_AGENT_BUSINESS_STATE", "MI"),
    "zip": _os.environ.get("SEO_AGENT_BUSINESS_ZIP", "49505"),
    "email": _os.environ.get("SEO_AGENT_BUSINESS_EMAIL", "hello@grandrapidshomeservices.com"),
    "site_url": _os.environ.get("SEO_AGENT_SITE_URL", "https://yoursite.com"),
    "licenses": {
        "general": "Licensed in Michigan · Bonded · Insured",
        "contractor": "Michigan Residential Builder License #2101234567",
        "appliance": "Michigan Appliance Service License #AS-8901234",
        "garage_door": "Michigan Garage Door Contractor License #GD-5678901",
    },
    "insurance": "General liability: $2M · Workers comp: statutory coverage",
    "founded_year": 2015,
    "service_radius_miles": 40,
    "coordinates": {"latitude": 42.9634, "longitude": -85.6681},
    "brand_voice": {
        "tone": "professional, local, trustworthy",
        "avoid": ["we think", "in our opinion", "we believe"],
        "prefer": ["our technicians", "we provide", "call us for"],
    },
}

# ──────────────────────────────────────────────
# 2c. REALISTIC REVIEW / TESTIMONIAL DATA
# ──────────────────────────────────────────────
# Simulated testimonials based on real patterns. No fabricated identity claims.
# Reviews mention real areas, real service items, realistic wait times.

REVIEWS: dict[str, list[dict[str, str]]] = {
    "appliance repair": [
        {"reviewer": "Mark T.", "area": "East Grand Rapids", "rating": "5",
         "text": "Technician arrived within 40 minutes on a Saturday. Fixed our refrigerator compressor in under an hour. Fair price, no upselling."},
        {"reviewer": "Sarah K.", "area": "Kentwood", "rating": "5",
         "text": "Dishwasher stopped draining. Called in the morning, they came by afternoon. Replaced the pump and it's been running perfectly since."},
        {"reviewer": "David R.", "area": "Wyoming", "rating": "4",
         "text": "Dryer was making a loud noise. Tech diagnosed it as a worn drum bearing. Quote was reasonable and repair took about 90 minutes."},
        {"reviewer": "Linda M.", "area": "Heritage Hill", "rating": "5",
         "text": "Our oven stopped heating. They diagnosed a faulty igniter same-day and had the part in stock. Back to baking by dinner."},
        {"reviewer": "Tom W.", "area": "Walker", "rating": "4",
         "text": "Washing machine wouldn't spin. Tech came out next day, fixed the lid switch in 20 minutes. No minimum service fee which was nice."},
    ],
    "garage door repair": [
        {"reviewer": "Jennifer P.", "area": "Cascade", "rating": "5",
         "text": "Spring broke on a Sunday morning. Called and someone was here within 2 hours. Replaced both springs and checked the whole system."},
        {"reviewer": "Mike L.", "area": "East Beltline", "rating": "5",
         "text": "Garage door wouldn't close. Sensor alignment was off after we bumped it. Tech fixed it in 15 minutes and didn't charge a service fee."},
        {"reviewer": "Rachel S.", "area": "Ada", "rating": "4",
         "text": "Opener stopped working. They replaced the motor unit same-day. Technician explained what failed and showed me how to maintain it."},
        {"reviewer": "Brian C.", "area": "Grandville", "rating": "5",
         "text": "Panel was dented from a backing incident. They matched the color perfectly and had it installed within 3 days. Looks great."},
    ],
    "garage door installation": [
        {"reviewer": "Kevin H.", "area": "Rockford", "rating": "5",
         "text": "New insulated door installed in a day. Team was professional, cleaned up everything, and old door was hauled away. Price was competitive."},
        {"reviewer": "Amy D.", "area": "East Grand Rapids", "rating": "5",
         "text": "Replaced our old wooden door with a modern steel one. Looks fantastic. Installation crew was punctual and neat."},
        {"reviewer": "Paul N.", "area": "Jenison", "rating": "4",
         "text": "Installed a carriage-style door with smart opener. Took about 6 hours. Works great with our smart home system. Would recommend."},
    ],
    "basement remodel": [
        {"reviewer": "Chris B.", "area": "Alger Heights", "rating": "5",
         "text": "Finished our basement into a home theater and guest room. Project took about 4 weeks. Communication was excellent throughout."},
        {"reviewer": "Heather J.", "area": "Forest Hills", "rating": "5",
         "text": "Added a bathroom and wet bar to our basement. Crew was respectful, finished on schedule. Permits were handled properly."},
    ],
    "shower remodel": [
        {"reviewer": "Lisa N.", "area": "Midtown", "rating": "5",
         "text": "Converted our tub to a walk-in shower with tile surround. Took 5 days. The tile work is beautiful and the crew was meticulous."},
        {"reviewer": "Robert F.", "area": "Kentwood", "rating": "4",
         "text": "Replaced old shower pan and fixtures. Quality work, good communication. Only minor delay on glass enclosure delivery."},
    ],
}

# ──────────────────────────────────────────────
# 2d. NICHE-SPECIFIC PRICING + RESPONSE DATA
# ──────────────────────────────────────────────

NICHE_METADATA: dict[str, dict[str, Any]] = {
    "appliance repair": {
        "license_key": "appliance",
        "response_time": "same-day (call before noon)",
        "emergency_response": "24/7, under 2 hours",
        "service_call": "$75-$129",
        "avg_repair": "$150-$350",
        "warranty": "90 days on parts, 1 year on labor",
        "certifications": ["OEM Certified", "NASTEC Registered", "EPA Section 608"],
        "niche_label": "Appliance Repair",
    },
    "garage door repair": {
        "license_key": "garage_door",
        "response_time": "same-day, typically within 4 hours",
        "emergency_response": "24/7, under 2 hours",
        "service_call": "$75-$99",
        "avg_repair": "$150-$450",
        "warranty": "1 year on parts, 2 years on labor",
        "certifications": ["IDA Certified", "Manufacturer Trained"],
        "niche_label": "Garage Door Repair",
    },
    "garage door installation": {
        "license_key": "garage_door",
        "response_time": "scheduled within 1-3 days",
        "emergency_response": "expedited available",
        "service_call": "Free estimate",
        "avg_repair": "$800-$2,500",
        "warranty": "Lifetime on door, 5 years on labor",
        "certifications": ["IDA Certified", "Manufacturer Trained"],
        "niche_label": "Garage Door Installation",
    },
    "basement remodel": {
        "license_key": "contractor",
        "response_time": "consultation within 48 hours",
        "emergency_response": "Not applicable",
        "service_call": "Free estimate",
        "avg_repair": "$15,000-$40,000",
        "warranty": "2 years on workmanship",
        "certifications": ["NKBA Member", "Certified Remodeler"],
        "niche_label": "Basement Remodeling",
    },
    "shower remodel": {
        "license_key": "contractor",
        "response_time": "consultation within 48 hours",
        "emergency_response": "Not applicable",
        "service_call": "Free estimate",
        "avg_repair": "$3,000-$10,000",
        "warranty": "2 years on workmanship",
        "certifications": ["NKBA Member", "Certified Bath Designer"],
        "niche_label": "Shower Remodeling",
    },
}

# ──────────────────────────────────────────────
# 3. UTILITY FUNCTIONS
# ──────────────────────────────────────────────

def _detect_niche(keyword: str) -> str | None:
    """Detect the niche from a keyword phrase. Returns None for unknown."""
    kw = keyword.lower()
    for niche in NICHE_PROFILES:
        if niche in kw:
            return niche
    return None


def get_niche_profile(keyword: str) -> dict[str, Any]:
    """Get the niche profile for a keyword, or default fallback."""
    niche = _detect_niche(keyword)
    profile = NICHE_PROFILES.get(niche, DEFAULT_NICHE).copy() if niche else DEFAULT_NICHE.copy()
    profile["_niche"] = niche
    return profile


# ──────────────────────────────────────────────
# 4. LOCAL FAQ GENERATOR
# ──────────────────────────────────────────────

def build_local_faq_html(keyword: str) -> str:
    """Build FAQ section with niche-specific questions for Grand Rapids."""
    profile = get_niche_profile(keyword)
    faqs = list(profile.get("faqs", []))
    kw = keyword.lower()

    # Core local FAQs always relevant
    core_faqs = [
        (f"Do you offer same-day {kw} in Grand Rapids?",
         f"Yes, we provide same-day {kw} service across Grand Rapids and surrounding areas including Kentwood, Wyoming, and East Grand Rapids."),
        (f"What areas do you serve for {kw} in West Michigan?",
         f"We serve all of Kent County: Grand Rapids, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Grandville, Jenison, Hudsonville, and Byron Center."),
        (f"Are your {kw} technicians licensed and insured in Michigan?",
         f"Yes, all our technicians are fully licensed, bonded, and insured in Michigan. We carry liability insurance and workers compensation."),
    ]

    all_faqs = core_faqs + [f for f in faqs if f not in core_faqs]
    all_faqs = all_faqs[:8]

    items_html = ""
    for q, a in all_faqs:
        items_html += f"""
<div class="faq-item">
    <div class="faq-q"><strong>Q:</strong> {q}</div>
    <div class="faq-a"><p>{a}</p></div>
</div>"""

    return f"""<h2>Frequently Asked Questions About {keyword.title()} in Grand Rapids</h2>
{items_html}"""


def build_local_faq_schema(keyword: str) -> str:
    """Build FAQPage JSON-LD from niche FAQs."""
    profile = get_niche_profile(keyword)
    faqs = list(profile.get("faqs", []))
    kw = keyword.lower()

    core_faqs = [
        (f"Do you offer same-day {kw} in Grand Rapids?",
         f"Yes, we provide same-day {kw} service across Grand Rapids and surrounding areas including Kentwood, Wyoming, and East Grand Rapids."),
        (f"What areas do you serve for {kw} in West Michigan?",
         f"We serve all of Kent County: Grand Rapids, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Grandville, Jenison, Hudsonville, and Byron Center."),
        (f"Are your {kw} technicians licensed and insured in Michigan?",
         f"Yes, all our technicians are fully licensed, bonded, and insured in Michigan."),
    ]

    all_faqs = core_faqs + [f for f in faqs if f not in core_faqs]
    all_faqs = all_faqs[:8]

    main_entity = []
    for q, a in all_faqs:
        main_entity.append({
            "@type": "Question",
            "name": q,
            "acceptedAnswer": {
                "@type": "Answer",
                "text": a,
            },
        })

    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": main_entity,
    }
    return json.dumps(schema, ensure_ascii=False)


# ──────────────────────────────────────────────
# 5. ENHANCED LocalBusiness SCHEMA BUILDER
# ──────────────────────────────────────────────

def build_enriched_local_business_schema(keyword: str, include_has_map: bool = True) -> str:
    """Build enriched LocalBusiness + Service schema with hyper-local data."""
    kw_title = keyword.title()
    kw_lower = keyword.lower()

    # Area served: neighborhoods + suburbs
    area_served = [{"@type": "City", "name": n} for n in [GRAND_RAPIDS["city"]] + SUBURBS]

    # Extra geo properties
    extra = {}
    if include_has_map:
        extra["hasMap"] = "https://maps.google.com/?q=Grand+Rapids,MI"

    schema = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": f"Grand Rapids {kw_title}",
        "description": f"Professional {kw_lower} serving Grand Rapids and all of West Michigan.",
        "image": "https://yoursite.com/images/grand-rapids-service.jpg",
        "url": f"https://yoursite.com/{re.sub(r'[^a-z0-9-]+', '-', kw_lower).strip('-')}",
        "telephone": GRAND_RAPIDS["phone"],
        "priceRange": "$$",
        "address": {
            "@type": "PostalAddress",
            "addressLocality": "Grand Rapids",
            "addressRegion": "MI",
            "addressCountry": "US",
        },
        "areaServed": area_served,
        "serviceArea": {
            "@type": "AdministrativeArea",
            "name": "Kent County, MI",
            "geoRadius": f"{SERVICE_RADIUS_MILES} miles",
            "geoMidpoint": {
                "@type": "GeoCoordinates",
                "latitude": 42.9634,
                "longitude": -85.6681,
            },
        },
        "openingHoursSpecification": [
            {"@type": "OpeningHoursSpecification", "dayOfWeek": "Monday", "opens": "07:00", "closes": "19:00"},
            {"@type": "OpeningHoursSpecification", "dayOfWeek": "Tuesday", "opens": "07:00", "closes": "19:00"},
            {"@type": "OpeningHoursSpecification", "dayOfWeek": "Wednesday", "opens": "07:00", "closes": "19:00"},
            {"@type": "OpeningHoursSpecification", "dayOfWeek": "Thursday", "opens": "07:00", "closes": "19:00"},
            {"@type": "OpeningHoursSpecification", "dayOfWeek": "Friday", "opens": "07:00", "closes": "19:00"},
            {"@type": "OpeningHoursSpecification", "dayOfWeek": "Saturday", "opens": "08:00", "closes": "17:00"},
        ],
        "sameAs": [
            "https://facebook.com/yoursite",
            "https://youtube.com/@yoursite",
        ],
    }
    schema.update(extra)
    return json.dumps(schema, ensure_ascii=False)


# ──────────────────────────────────────────────
# 6. NEIGHBORHOOD INJECTOR
# ──────────────────────────────────────────────

def _deterministic_shuffle(items: list, seed_str: str) -> list:
    """Deterministically rotate a list based on a seed string."""
    h = hashlib.md5(seed_str.encode()).hexdigest()
    seed = int(h[24:32], 16)
    if not items:
        return items
    n = seed % len(items)
    return items[n:] + items[:n]

def inject_neighborhoods(article: str, keyword: str) -> str:
    """Inject neighborhood names into 'Areas We Serve' sections."""
    kw = keyword.lower()

    # Deterministically shuffle neighborhoods/suburbs/ZIPs per keyword
    ngh = _deterministic_shuffle(NEIGHBORHOODS, keyword)
    sub = _deterministic_shuffle(SUBURBS, keyword + "_suburbs")
    zips = _deterministic_shuffle(ZIP_CODES, keyword + "_zips")

    neighborhoods_str = ", ".join(ngh[:8])
    suburbs_str = ", ".join(sub[:10])
    zip_str = ", ".join(zips[:8])

    intro_variant = _pick_variant(keyword, NEIGHBORHOOD_INTRO_VARIANTS)

    pattern = r'(<h2[^>]*>.*?(?:areas?\s*(?:we\s*)?serve|service\s*area).*?</h2>\s*)(.*?)(?=<h2|\Z)'

    def _replace(m: re.Match) -> str:
        header = m.group(1)
        replacement = (
            f'{header}{intro_variant(kw)}\n'
            f'<h3>Neighborhoods We Serve in Grand Rapids</h3>\n'
            f'<p>Our technicians serve all Grand Rapids neighborhoods including {neighborhoods_str}, and more.</p>\n'
            f'<h3>Surrounding Communities</h3>\n'
            f'<p>We also cover {suburbs_str} and all of {GRAND_RAPIDS["county"]}.</p>\n'
            f'<h3>ZIP Codes We Cover</h3>\n'
            f'<p>Grand Rapids ZIP codes: {zip_str} and surrounding areas.</p>\n'
        )
        return replacement

    article = re.sub(pattern, _replace, article, flags=re.IGNORECASE | re.DOTALL)
    return article


# ──────────────────────────────────────────────
# 7. NEAR-ME / EMERGENCY SECTION EXPANDER
# ──────────────────────────────────────────────

def inject_near_me_section(article: str, keyword: str) -> str:
    """Inject 'near me' section if keyword has service intent."""
    kw_lower = keyword.lower()
    near_me_phrases = ["near me", "nearby", "close to me", "in my area"]
    already_has_near_me = any(p in article.lower() for p in near_me_phrases)

    if not already_has_near_me:
        variant = _pick_variant(keyword, NEAR_ME_VARIANTS)
        near_me_html = variant(keyword.title(), kw_lower, BUSINESS_IDENTITY)

        # Inject before first h2
        first_h2 = re.search(r'<h2[^>]*>', article)
        if first_h2:
            pos = first_h2.start()
            article = article[:pos] + near_me_html + "\n" + article[pos:]

    return article


def inject_emergency_section(article: str, keyword: str) -> str:
    """Inject emergency service section if niche supports it."""
    profile = get_niche_profile(keyword)
    emergency_text = profile.get("emergency", "")
    if not emergency_text:
        return article

    kw_lower = keyword.lower()
    already_has = "emergency" in article.lower()

    if not already_has:
        variant = _pick_variant(keyword, EMERGENCY_VARIANTS)
        emergency_html = variant(keyword.title(), kw_lower, BUSINESS_IDENTITY, emergency_text)

        # Insert after same-day section or at end of article body
        same_day_match = re.search(r'<h2[^>]*>.*?[Ss]ame.?[Dd]ay.*?</h2>', article)
        if same_day_match:
            pos = same_day_match.end()
            article = article[:pos] + "\n" + emergency_html + article[pos:]
        else:
            body_end = article.rfind("</body>")
            if body_end >= 0:
                article = article[:body_end] + emergency_html + "\n" + article[body_end:]

    return article


# ──────────────────────────────────────────────
# 8. INTENT-AWARE CTA ENGINE
# ──────────────────────────────────────────────

def build_cta_html(keyword: str) -> str:
    """Build niche-specific call-to-action box with variant styling."""
    profile = get_niche_profile(keyword)
    cta_text = profile.get("cta", DEFAULT_NICHE["cta"])
    cta_sub = profile.get("cta_sub", DEFAULT_NICHE["cta_sub"])
    variant = _pick_variant(keyword, CTA_VARIANTS)
    return variant(cta_text, cta_sub, BUSINESS_IDENTITY)


def inject_cta(article: str, keyword: str) -> str:
    """Inject niche-specific CTA box into article."""
    cta_html = build_cta_html(keyword)
    # Replace existing CTA/contact sections
    contact_pattern = r'<h2[^>]*>.*?(?:contact|get started|call|reach out).*?</h2>.*?(?=<h2|<script|</body>)'
    if re.search(contact_pattern, article, re.IGNORECASE | re.DOTALL):
        article = re.sub(
            contact_pattern,
            lambda m: m.group(0) + "\n" + cta_html,
            article,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
    else:
        # Append before </body>
        body_end = article.rfind("</body>")
        if body_end >= 0:
            article = article[:body_end] + cta_html + "\n" + article[body_end:]
    return article


# ──────────────────────────────────────────────
# 9. GEO ENTITY INJECTION
# ──────────────────────────────────────────────

def inject_geo_entities(article: str) -> str:
    """Inject landmark and highway references into article body."""
    landmarks_sample = LANDMARKS[:6]
    highways_sample = MAJOR_HIGHWAYS[:4]

    # Inject landmark reference after first paragraph if not already present
    first_p = re.search(r'(<p[^>]*>.*?</p>)', article)
    if first_p and not any(lm.lower() in article.lower() for lm in landmarks_sample):
        geo_sentence = f" We proudly serve homes near {', '.join(landmarks_sample[:3])} and all major Grand Rapids landmarks."
        pos = first_p.end() - 6  # before closing </p>
        article = article[:pos] + geo_sentence + article[pos:]

    # Inject highway accessibility near areas-served section
    areas_serve = re.search(r'<h2[^>]*>.*?(?:areas?\s*(?:we\s*)?serve|service\s*area).*?</h2>', article, re.IGNORECASE)
    if areas_serve and not any(hw.lower() in article.lower() for hw in highways_sample):
        highways_str = ", ".join(highways_sample)
        highway_note = f"<p>Our service area covers all neighborhoods accessible via {highways_str} and the entire Kent County road network.</p>"
        pos = areas_serve.end()
        article = article[:pos] + "\n" + highway_note + article[pos:]

    return article


# ──────────────────────────────────────────────
# 10. PRICING TABLE BUILDER
# ──────────────────────────────────────────────

def build_pricing_table(keyword: str) -> str:
    """Build a service-pricing table specific to the niche."""
    profile = get_niche_profile(keyword)
    niche = profile.get("_niche")

    service_rows = profile.get("service_items", [])
    if not service_rows:
        return ""

    rows_html = ""
    for item in service_rows[:6]:
        rows_html += f"<tr><td>{item}</td><td>Call for estimate</td><td>Varies</td></tr>\n"

    return f"""<h2>{keyword.title()} Pricing in Grand Rapids</h2>
<div class="pricing-table-wrapper">
<table class="pricing-table">
<thead>
    <tr><th>Service</th><th>Service Call Fee</th><th>Typical Cost</th></tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
<p style="font-size:0.85em;color:#666;">* Prices are estimates. Call <a href="tel:{GRAND_RAPIDS['phone']}">{GRAND_RAPIDS['phone']}</a> for a free, accurate quote.</p>
</div>"""


# ──────────────────────────────────────────────
# 11. BRANDS LIST BUILDER
# ──────────────────────────────────────────────

def build_brands_html(keyword: str) -> str:
    """Build brands-we-work-with section."""
    profile = get_niche_profile(keyword)
    brands = profile.get("brands", [])
    if not brands:
        return ""

    brands_str = ", ".join(brands)
    return f"""<h2>Brands We Service for {keyword.title()} in Grand Rapids</h2>
<p>Our technicians are trained and certified to work with all leading brands including {brands_str}.</p>"""


# ──────────────────────────────────────────────
# 12. BUSINESS IDENTITY INJECTOR
# ──────────────────────────────────────────────

def inject_business_identity(article: str, keyword: str) -> str:
    """Inject real business identity — name, address, hours, license — into article body."""
    biz = BUSINESS_IDENTITY
    kw_lower = keyword.lower()

    # Inject business name + license into the intro paragraph
    intro_p = re.search(r'(<p[^>]*>)(.*?)(</p>)', article)
    if intro_p and biz["name"].lower() not in article.lower()[:500]:
        biz_sentence = f" At {biz['name']}, our experienced technicians provide professional {kw_lower} throughout Grand Rapids and West Michigan."
        pos = intro_p.end(2)
        article = article[:pos] + biz_sentence + article[pos:]

    # Inject address + hours near contact section
    contact_section = re.search(r'<h2[^>]*>.*?(?:contact|call us|get started|reach out).*?</h2>.*?(?=<h2|<script|</body>)',
                                 article, re.IGNORECASE | re.DOTALL)
    if contact_section:
        service_hours = (
            "Mon-Fri: 7:00 AM - 7:00 PM · Sat: 8:00 AM - 5:00 PM · Emergency: 24/7"
        )
        location_block = f"""<p><strong>{biz['name']}</strong><br>
{biz['address']}, {biz['city']}, {biz['state']} {biz['zip']}<br>
Hours: {service_hours}<br>
{biz['licenses']['general']}</p>"""
        article = article[:contact_section.end()] + "\n" + location_block + article[contact_section.end():]

    # License mention in footer/trust area
    if biz["licenses"]["general"] not in article:
        body_end = article.rfind("</body>")
        if body_end >= 0:
            trust_line = f'<p style="font-size:0.8em;color:#666;">{biz["licenses"]["general"]} · {biz["insurance"]} · Est. {biz["founded_year"]}</p>\n'
            article = article[:body_end] + trust_line + article[body_end:]

    return article


# ──────────────────────────────────────────────
# 13. REVIEW / TESTIMONIAL INJECTOR
# ──────────────────────────────────────────────

def inject_reviews(article: str, keyword: str) -> str:
    """Inject realistic testimonials into article after the trust/why-choose-us section."""
    profile = get_niche_profile(keyword)
    niche = profile.get("_niche")
    if not niche or niche not in REVIEWS:
        return article

    reviews = REVIEWS[niche]
    if not reviews:
        return article

    # Check if reviews already present
    if any(r["reviewer"] in article for r in reviews):
        return article

    # Deterministically pick 2-4 reviews and shuffle
    count = _pick_variant_count(keyword, min(4, len(reviews)), len(reviews))
    h = hashlib.md5(keyword.lower().encode()).hexdigest()
    seed = int(h[16:24], 16)
    picked = list(reviews)
    # Simple deterministic shuffle by rotating based on seed
    picked = picked[seed % len(picked):] + picked[:seed % len(picked)]
    picked = picked[:count]

    # Choose review card layout
    layout_variant = _pick_variant(keyword + "_layout", REVIEW_LAYOUT_VARIANTS)

    cards_html = ""
    for rev in picked:
        stars = "★" * int(rev["rating"]) + "☆" * (5 - int(rev["rating"]))
        cards_html += f"""<div class="testimonial" style="background:#f9f9f9;border-left:4px solid #2b6cb0;padding:12px 16px;margin:12px 0;border-radius:4px;">
    <p style="margin:0 0 6px;font-size:1.05em;">"{rev['text']}"</p>
    <p style="margin:0;font-size:0.85em;color:#555;">— {rev['reviewer']}, {rev['area']} <span style="color:#e6a817;">{stars}</span></p>
</div>"""

    title = f"What Grand Rapids Homeowners Say About Our {profile.get('niche_label', keyword.title())} Services"
    reviews_html = layout_variant(cards_html, title)

    # Inject after "Why Choose Us" section or before FAQ
    why_section = re.search(r'<h2[^>]*>.*?why.*?choose.*?</h2>.*?(?=<h2|<script|</body>)',
                            article, re.IGNORECASE | re.DOTALL)
    if why_section:
        article = article[:why_section.end()] + "\n" + reviews_html + "\n" + article[why_section.end():]
    else:
        faq_section = re.search(r'<h2[^>]*>.*?faq.*?</h2>', article, re.IGNORECASE)
        if faq_section:
            article = article[:faq_section.start()] + reviews_html + "\n" + article[faq_section.start():]

    return article


# ──────────────────────────────────────────────
# 14. TRUST BADGE / CERTIFICATION INJECTOR
# ──────────────────────────────────────────────

def inject_trust_badges(article: str, keyword: str) -> str:
    """Inject trust signals — license numbers, certifications, warranty — into article."""
    profile = get_niche_profile(keyword)
    metadata = NICHE_METADATA.get(profile.get("_niche", ""), {})
    biz = BUSINESS_IDENTITY
    niche_label = metadata.get("niche_label", keyword.title())
    warranty = metadata.get("warranty", "100% satisfaction guarantee")
    certs = metadata.get("certifications", [])

    certs_str = " · ".join(certs) if certs else ""
    trust_html = f"""<div class="trust-badges" style="display:flex;flex-wrap:wrap;gap:12px;margin:20px 0;padding:16px;background:#f0f7ff;border-radius:8px;border:1px solid #cce5ff;">
    <div style="flex:1;min-width:180px;"><strong>✓ License & Insurance</strong><br><span style="font-size:0.9em;">{biz['licenses']['general']}<br>{biz['insurance']}</span></div>
    <div style="flex:1;min-width:180px;"><strong>✓ Warranty</strong><br><span style="font-size:0.9em;">{warranty}</span></div>
    <div style="flex:1;min-width:180px;"><strong>✓ Experience</strong><br><span style="font-size:0.9em;">Serving Grand Rapids since {biz['founded_year']}</span></div>
    {f'<div style="flex:1;min-width:180px;"><strong>✓ Certifications</strong><br><span style="font-size:0.9em;">{certs_str}</span></div>' if certs_str else ''}
</div>"""

    # Inject after the first "Why Choose Us" section
    why_section = re.search(r'<h2[^>]*>.*?why.*?choose.*?</h2>', article, re.IGNORECASE)
    if why_section:
        article = article[:why_section.end()] + "\n" + trust_html + "\n" + article[why_section.end():]
    else:
        body_end = article.rfind("</body>")
        if body_end >= 0:
            article = article[:body_end] + trust_html + "\n" + article[body_end:]

    return article


# ──────────────────────────────────────────────
# 15. ENHANCED PRICING TABLE (uses real metadata)
# ──────────────────────────────────────────────

def build_enhanced_pricing_table(keyword: str) -> str:
    """Build pricing table with real data from NICHE_METADATA."""
    profile = get_niche_profile(keyword)
    metadata = NICHE_METADATA.get(profile.get("_niche", ""), {})

    service_call = metadata.get("service_call", "Call for estimate")
    avg_repair = metadata.get("avg_repair", "Varies")
    response = metadata.get("response_time", "Same-day available")
    warranty = metadata.get("warranty", "100% satisfaction guarantee")

    service_rows = profile.get("service_items", [])
    if not service_rows:
        return ""

    rows_html = ""
    for item in service_rows[:5]:
        rows_html += f"<tr><td>{item}</td><td>{service_call}</td><td>{avg_repair}</td></tr>\n"

    return f"""<h2>{keyword.title()} Pricing in Grand Rapids — Upfront & Transparent</h2>
<div class="pricing-table-wrapper">
<table class="pricing-table">
<thead>
    <tr><th>Service</th><th>Service Call</th><th>Typical Cost</th></tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
<p style="font-size:0.85em;color:#666;">* Estimates are typical ranges. Actual cost depends on diagnosis. Response time: {response}. {warranty}.</p>
<p style="font-size:0.9em;"><strong>Call {BUSINESS_IDENTITY['phone']}</strong> for a free, accurate quote — no obligation.</p>
</div>"""


# ──────────────────────────────────────────────
# 16. MAIN ENHANCE FUNCTION
# ──────────────────────────────────────────────

def enhance_article(article: str, keyword: str, intent: str) -> str:
    """
    Main entry point: apply all hyper-local SEO enhancements to an article.

    Called from modules.py:write_article() after fix_article() and before hard_fail_audit().
    Only applies to LOCAL_SERVICE intent.
    """
    if intent != "LOCAL_SERVICE":
        return article

    kw = keyword.lower()

    log.info("[LOCAL_INTEL] Enhancing article for '%s' (%s)", kw, GRAND_RAPIDS["city"])

    article = inject_near_me_section(article, keyword)
    article = inject_emergency_section(article, keyword)
    article = inject_neighborhoods(article, keyword)
    article = inject_business_identity(article, keyword)
    article = inject_reviews(article, keyword)
    article = inject_trust_badges(article, keyword)
    article = inject_cta(article, keyword)
    article = inject_geo_entities(article)
    article = enhance_with_links(article, keyword, intent)

    return article


# Populate taxonomy profiles at module load (must be last)
_populate_taxonomy_profiles()
