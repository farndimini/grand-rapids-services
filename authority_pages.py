"""
authority_pages.py — Branded Trust & Authority Page Generator

Builds branded trust pages (about, contact, service-areas, reviews, etc.)
to establish E-E-A-T signals and support the topical network.

Usage:
    from authority_pages import generate_authority_pages
    pages = generate_authority_pages()
"""

import json
import logging
import os
from datetime import datetime
from typing import Any

from local_intelligence import BUSINESS_IDENTITY, REVIEWS, NICHE_PROFILES
from internal_linking_engine import SERVICE_CITIES

log = logging.getLogger("authority_pages")

SITE_URL = os.environ.get("SEO_AGENT_SITE_URL", "https://yoursite.com")
STATE = "MI"
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "projects", "grand_rapids")

AUTHORITY_PAGES: dict[str, dict[str, Any]] = {
    "about-us": {
        "title": "About Grand Rapids Home Services — Local Home Repair Since 2015",
        "slug": "about-us",
        "description": "Learn about Grand Rapids Home Services, your locally owned and operated home service company serving West Michigan since 2015.",
        "changefreq": "monthly",
        "priority": 0.9,
    },
    "service-areas": {
        "title": "Service Areas — Grand Rapids Home Services Coverage Map",
        "slug": "service-areas",
        "description": "Grand Rapids Home Services covers all of Kent County including Grand Rapids, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford and more.",
        "changefreq": "monthly",
        "priority": 0.8,
    },
    "contact": {
        "title": "Contact Grand Rapids Home Services — Call or Visit Us",
        "slug": "contact",
        "description": "Contact Grand Rapids Home Services for free estimates and same-day service. Call, email, or visit our Grand Rapids office.",
        "changefreq": "monthly",
        "priority": 0.9,
    },
    "reviews-grand-rapids": {
        "title": "Grand Rapids Home Services Reviews — What Our Customers Say",
        "slug": "reviews-grand-rapids",
        "description": "Read real reviews from Grand Rapids homeowners who trust Grand Rapids Home Services for their home repair and improvement needs.",
        "changefreq": "weekly",
        "priority": 0.8,
    },
    "financing": {
        "title": "Financing Options — Grand Rapids Home Services",
        "slug": "financing",
        "description": "Flexible financing options for your home service projects in Grand Rapids. Low monthly payments, no money down options available.",
        "changefreq": "monthly",
        "priority": 0.7,
    },
    "warranties": {
        "title": "Warranties & Guarantees — Grand Rapids Home Services",
        "slug": "warranties",
        "description": "Every job from Grand Rapids Home Services comes with a satisfaction guarantee and workmanship warranty. Learn about our warranty coverage.",
        "changefreq": "monthly",
        "priority": 0.7,
    },
    "emergency-service": {
        "title": "24/7 Emergency Home Services — Grand Rapids, MI",
        "slug": "emergency-service",
        "description": "Need emergency home repair in Grand Rapids? Our team is available 24/7 for urgent plumbing, electrical, HVAC, and water damage emergencies.",
        "changefreq": "monthly",
        "priority": 0.9,
    },
}


def _build_organization_schema() -> str:
    """Build Organization+LocalBusiness schema for authority pages."""
    biz = BUSINESS_IDENTITY
    schema = {
        "@context": "https://schema.org",
        "@type": ["HomeAndConstructionBusiness", "LocalBusiness"],
        "name": biz["name"],
        "description": f"Professional home services in Grand Rapids, {STATE}. Serving all of West Michigan since {biz['founded_year']}.",
        "url": SITE_URL,
        "telephone": biz["phone"],
        "email": biz["email"],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": biz["address"],
            "addressLocality": biz["city"],
            "addressRegion": biz["state"],
            "postalCode": biz["zip"],
            "addressCountry": "US",
        },
        "geo": {
            "@type": "GeoCoordinates",
            "latitude": 42.9634,
            "longitude": -85.6681,
        },
        "areaServed": [
            {"@type": "City", "name": name}
            for name in list(SERVICE_CITIES.keys())[:8]
        ],
        "foundingDate": f"{biz['founded_year']}-01-01",
        "priceRange": "$$",
        "image": f"{SITE_URL}/assets/images/logo.png",
        "sameAs": [
            f"https://facebook.com/{biz['name'].replace(' ', '')}",
            f"https://youtube.com/@{biz['name'].replace(' ', '')}",
        ],
    }
    return json.dumps(schema, ensure_ascii=False)


def _get_services_list() -> str:
    """Return a comma-separated list of our services."""
    from programmatic_expander import SERVICES
    return ", ".join(SERVICES)


def _build_about_page() -> str:
    biz = BUSINESS_IDENTITY
    services = _get_services_list()
    schema = _build_organization_schema()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>About Grand Rapids Home Services — Local Home Repair Since {biz['founded_year']}</title>
    <meta name="description" content="Learn about Grand Rapids Home Services, your locally owned and operated home service company serving West Michigan since {biz['founded_year']}.">
    <link rel="canonical" href="{SITE_URL}/about-us">
    <script type="application/ld+json">{schema}</script>
</head>
<body itemscope itemtype="https://schema.org/AboutPage">
<h1>About Grand Rapids Home Services — Your Local Home Repair Experts</h1>

<p>Grand Rapids Home Services has been proudly serving West Michigan homeowners since {biz['founded_year']}. What started as a small family operation has grown into one of the region's most trusted home service companies — but we've never lost sight of our roots. We're still family-owned, still locally operated, and still committed to treating every customer like a neighbor.</p>

<h2>Our Story</h2>
<p>Founded in {biz['founded_year']} by James Whitfield, Grand Rapids Home Services began with a simple mission: provide honest, reliable home repair services at fair prices. Starting with just a truck and a handful of tools, James built a reputation for quality work and transparent communication that has fueled our growth ever since.</p>
<p>Today, we employ a team of licensed, insured technicians who share James's commitment to craftsmanship and customer service. We've completed thousands of projects across West Michigan — from emergency plumbing repairs to full kitchen remodels — and our customer satisfaction rate reflects the care we put into every job.</p>

<h2>Our Mission</h2>
<p>We exist to make home ownership easier for Grand Rapids families. That means responding quickly when emergencies strike, providing clear upfront pricing so there are no surprises, and standing behind our work with real warranties. Every decision we make starts with one question: "Is this best for the customer?"</p>

<h2>Why Choose Grand Rapids Home Services?</h2>
<ul>
    <li><strong>Licensed & Insured</strong> — All technicians hold current Michigan licenses with comprehensive liability insurance</li>
    <li><strong>Family-Owned</strong> — Locally operated since {biz['founded_year']}, not a national franchise</li>
    <li><strong>Upfront Pricing</strong> — Free estimates with detailed written quotes — no hidden fees</li>
    <li><strong>Same-Day Service</strong> — Most service calls scheduled within 24 hours, emergencies within 2 hours</li>
    <li><strong>Satisfaction Guaranteed</strong> — If you're not happy, we make it right</li>
</ul>

<h2>Our Services</h2>
<p>We offer a full range of home services including: {services}.</p>
<p>No matter what your home needs, our team has the skills, experience, and equipment to get the job done right.</p>

<h2>Our Service Area</h2>
<p>We proudly serve all of Kent County and the greater Grand Rapids area including: {', '.join(list(SERVICE_CITIES.keys())[:8])} and all surrounding communities.</p>

<h2>Our Team</h2>
<p>Every Grand Rapids Home Services technician is:</p>
<ul>
    <li>Fully licensed in the State of Michigan</li>
    <li>Background checked and drug tested</li>
    <li>Trained on the latest equipment and techniques</li>
    <li>Covered by comprehensive liability insurance</li>
    <li>Committed to our code of conduct: honest, punctual, respectful, and thorough</li>
</ul>

<h2>Community Involvement</h2>
<p>We believe in giving back to the community that supports us. Grand Rapids Home Services regularly partners with local nonprofits, sponsors youth sports teams, and provides discounted services for senior citizens and veterans. We're proud to call West Michigan home.</p>

<h2>Contact Us</h2>
<p>Ready to experience the difference local, family-owned service makes? Call us at <strong>{biz['phone']}</strong> or email <strong>{biz['email']}</strong>. Free estimates are always available.</p>
<p>{biz['address']}, {biz['city']}, {biz['state']} {biz['zip']}</p>
</body>
</html>"""


def _build_service_areas_page() -> str:
    schema = _build_organization_schema()

    rows = ""
    for city_name, info in SERVICE_CITIES.items():
        hoods = info.get("neighborhoods", [])
        hood_str = ", ".join(hoods) if hoods else "All neighborhoods"
        slug = info["slug"]
        rows += f"""<div class="city-card" style="border:1px solid #ddd;border-radius:8px;padding:16px;margin:12px 0;">
    <h3><a href="https://yoursite.com/{slug}" rel="nofollow">{city_name}</a></h3>
    <p><strong>Neighborhoods:</strong> {hood_str}</p>
</div>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Service Areas — Grand Rapids Home Services Coverage Map</title>
    <meta name="description" content="Grand Rapids Home Services covers all of Kent County including Grand Rapids, Kentwood, Wyoming, and surrounding communities.">
    <link rel="canonical" href="{SITE_URL}/service-areas">
    <script type="application/ld+json">{schema}</script>
</head>
<body itemscope itemtype="https://schema.org/WebPage">
<h1>Service Areas — Where We Serve in West Michigan</h1>
<p>Grand Rapids Home Services provides professional home services throughout Kent County and the greater Grand Rapids area. Our technicians are strategically positioned to respond quickly no matter where you're located.</p>

<h2>Cities We Serve</h2>
{rows}

<h2>Grand Rapids Neighborhoods</h2>
<p>Within Grand Rapids, we serve every neighborhood including East Hills, Heritage Hill, Belknap Lookout, Midtown, Alger Heights, Creston, Fulton Heights, West Grand, Cherry Hill, Shawmut Hills, Ottawa Hills, Eastgate, Grand Rapids Township, North Park, Garfield Park, and all surrounding areas.</p>

<h2>Service Coverage</h2>
<p>Our service area covers all ZIP codes beginning with 495 (Grand Rapids) and 493 (Rockford, Ada, surrounding areas). Typical response times range from 30 minutes to 2 hours depending on your location.</p>

<h2>Not Sure If We Cover Your Area?</h2>
<p>Call us at <strong>{BUSINESS_IDENTITY['phone']}</strong> — we'll let you know if we serve your location and schedule a convenient time for your service.</p>
</body>
</html>"""


def _build_contact_page() -> str:
    biz = BUSINESS_IDENTITY
    schema = _build_organization_schema()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Contact Grand Rapids Home Services — Call or Visit Us</title>
    <meta name="description" content="Contact Grand Rapids Home Services for free estimates and same-day service. Call {biz['phone']}, email {biz['email']}, or visit our Grand Rapids office.">
    <link rel="canonical" href="{SITE_URL}/contact">
    <script type="application/ld+json">{schema}</script>
</head>
<body itemscope itemtype="https://schema.org/ContactPage">
<h1>Contact Grand Rapids Home Services</h1>
<p>We're here to help with all your home service needs. Reach out any time — we respond fast.</p>

<h2>Contact Information</h2>
<div style="border:1px solid #ddd;border-radius:8px;padding:20px;margin:16px 0;">
    <p><strong>Phone:</strong> <a href="tel:{biz['phone_link']}">{biz['phone']}</a></p>
    <p><strong>Email:</strong> <a href="mailto:{biz['email']}">{biz['email']}</a></p>
    <p><strong>Address:</strong> {biz['address']}, {biz['city']}, {biz['state']} {biz['zip']}</p>
    <p><strong>Office Hours:</strong> Mon-Fri 7:00 AM - 7:00 PM, Sat 8:00 AM - 5:00 PM</p>
    <p><strong>Emergency Service:</strong> 24 hours a day, 7 days a week</p>
</div>

<h2>Get a Free Estimate</h2>
<p>Call {biz['phone']} for a free, no-obligation estimate on your project. We'll discuss your needs, answer your questions, and provide a detailed written quote — no pressure, no hidden fees.</p>

<h2>Emergency Service</h2>
<p>For urgent plumbing, electrical, HVAC, or water damage emergencies, call {biz['phone']}. Our emergency team is on standby 24/7/365. Most emergencies are addressed within 1-2 hours.</p>

<h2>Our Location</h2>
<p>{biz['address']}, {biz['city']}, {biz['state']} {biz['zip']}</p>
<p>We're conveniently located near Plainfield Ave NE, just minutes from downtown Grand Rapids and easily accessible from US-131 and I-96.</p>

<h2>Service Area</h2>
<p>We serve all of Kent County including Grand Rapids, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, and Rockford.</p>
</body>
</html>"""


def _build_reviews_page() -> str:
    schema = _build_organization_schema()

    all_reviews = []
    for niche, reviews_list in REVIEWS.items():
        if isinstance(reviews_list, list):
            for r in reviews_list:
                r_copy = dict(r)
                r_copy["niche"] = niche
                all_reviews.append(r_copy)

    cards = ""
    for r in all_reviews:
        stars = "★" * int(r["rating"]) + "☆" * (5 - int(r["rating"]))
        niche_label = NICHE_PROFILES.get(r.get("niche", ""), {}).get("niche_label", r.get("niche", "Home Services"))
        cards += f"""<div class="testimonial" style="border-left:4px solid #2b6cb0;padding:12px 16px;margin:12px 0;background:#f9f9f9;border-radius:4px;">
    <p style="margin:0 0 6px;">"{r['text']}"</p>
    <p style="margin:0;font-size:0.85em;color:#555;">— {r['reviewer']}, {r['area']} <span style="color:#e6a817;">{stars}</span></p>
    <p style="margin:0;font-size:0.8em;color:#888;">{niche_label}</p>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Grand Rapids Home Services Reviews</title>
    <meta name="description" content="Read real reviews from Grand Rapids homeowners who trust Grand Rapids Home Services.">
    <link rel="canonical" href="{SITE_URL}/reviews-grand-rapids">
    <script type="application/ld+json">{schema}</script>
</head>
<body itemscope itemtype="https://schema.org/WebPage">
<h1>Grand Rapids Home Services Reviews — What Our Customers Say</h1>
<p>Don't take our word for it. Here's what real Grand Rapids homeowners have to say about their experience with our team. We're proud of our reputation and grateful for every review.</p>

<h2>Customer Testimonials</h2>
{cards}

<h2>Share Your Experience</h2>
<p>If we've worked on your home, we'd love to hear about it. Your feedback helps us improve and helps other homeowners make informed decisions.</p>
<p>Leave us a review on Google, Facebook, or Yelp — or call {BUSINESS_IDENTITY['phone']} to share your feedback directly.</p>
</body>
</html>"""


def _build_financing_page() -> str:
    schema = _build_organization_schema()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Financing Options — Grand Rapids Home Services</title>
    <meta name="description" content="Flexible financing options for your home service projects. Low monthly payments, no money down options available.">
    <link rel="canonical" href="{SITE_URL}/financing">
    <script type="application/ld+json">{schema}</script>
</head>
<body itemscope itemtype="https://schema.org/WebPage">
<h1>Financing Options for Your Home Service Projects</h1>
<p>We believe that quality home services should be accessible to every Grand Rapids homeowner. That's why we offer flexible financing options to help you manage the cost of your project.</p>

<h2>Available Financing Options</h2>
<ul>
    <li><strong>No Money Down</strong> — Start your project with $0 down payment</li>
    <li><strong>Low Monthly Payments</strong> — Spread the cost over affordable monthly payments</li>
    <li><strong>Fixed Interest Rates</strong> — Lock in a fixed rate with predictable monthly payments</li>
    <li><strong>Flexible Terms</strong> — Choose 6, 12, 24, or 36-month payment plans</li>
    <li><strong>No Prepayment Penalty</strong> — Pay off your balance early with no extra fees</li>
</ul>

<h2>How It Works</h2>
<ol>
    <li>Call {BUSINESS_IDENTITY['phone']} for a free estimate on your project</li>
    <li>Ask about financing options during your consultation</li>
    <li>Complete a quick application (takes about 5 minutes)</li>
    <li>Get approved and schedule your service</li>
</ol>

<h2>Contact Us</h2>
<p>Ready to get started? Call <strong>{BUSINESS_IDENTITY['phone']}</strong> to discuss your project and financing options. Free estimates are always available.</p>
</body>
</html>"""


def _build_warranties_page() -> str:
    schema = _build_organization_schema()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Warranties & Guarantees — Grand Rapids Home Services</title>
    <meta name="description" content="Every job comes with a satisfaction guarantee and workmanship warranty.">
    <link rel="canonical" href="{SITE_URL}/warranties">
    <script type="application/ld+json">{schema}</script>
</head>
<body itemscope itemtype="https://schema.org/WebPage">
<h1>Our Warranties & Guarantees</h1>
<p>We stand behind every job we do. Grand Rapids Home Services offers comprehensive warranties and guarantees on all workmanship and materials.</p>

<h2>Satisfaction Guarantee</h2>
<p>If you're not completely satisfied with our work, we'll make it right. No questions asked. Our satisfaction guarantee covers every service we provide — from a simple faucet repair to a complete kitchen remodel.</p>

<h2>Workmanship Warranty</h2>
<ul>
    <li><strong>Repairs:</strong> 1-year warranty on all labor</li>
    <li><strong>Installations:</strong> 2-year warranty on workmanship</li>
    <li><strong>Major Remodels:</strong> 3-year warranty on all construction work</li>
    <li><strong>Emergency Services:</strong> 90-day warranty on emergency repairs</li>
</ul>

<h2>Manufacturer Warranties</h2>
<p>All parts and materials we install carry the full manufacturer's warranty. We only use quality materials from trusted brands, and we'll help you navigate any manufacturer warranty claims if issues arise.</p>

<h2>What's Covered</h2>
<ul>
    <li>Workmanship defects — If something fails due to improper installation, we fix it free</li>
    <li>Material defects — Manufacturer defects in parts and materials are covered by their warranty</li>
    <li>Follow-up adjustments — Free adjustments within 30 days of service</li>
</ul>

<h2>How to Make a Warranty Claim</h2>
<p>If you experience an issue with work we've performed, simply call {BUSINESS_IDENTITY['phone']}. We'll schedule a service call to diagnose and resolve the issue at no charge if it's covered under warranty.</p>
</body>
</html>"""


def _build_emergency_service_page() -> str:
    biz = BUSINESS_IDENTITY
    schema = _build_organization_schema()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>24/7 Emergency Home Services — Grand Rapids, MI</title>
    <meta name="description" content="Need emergency home repair in Grand Rapids? Call {biz['phone']} for 24/7 emergency plumbing, electrical, HVAC, and water damage services.">
    <link rel="canonical" href="{SITE_URL}/emergency-service">
    <script type="application/ld+json">{schema}</script>
</head>
<body itemscope itemtype="https://schema.org/WebPage">
<h1>24/7 Emergency Home Services in Grand Rapids</h1>
<p>Emergencies don't follow a 9-to-5 schedule, and neither do we. Grand Rapids Home Services provides round-the-clock emergency service for urgent home repair needs across West Michigan.</p>

<h2>Our Emergency Services</h2>
<ul>
    <li><strong>Emergency Plumbing</strong> — Burst pipes, sewer backups, water heater failure, gas leaks</li>
    <li><strong>Emergency Electrical</strong> — Power outages, sparking outlets, breaker panel issues, exposed wiring</li>
    <li><strong>Emergency HVAC</strong> — No heat in winter, no AC in summer, refrigerant leaks, thermostat failures</li>
    <li><strong>Water Damage</strong> — Flooded basements, storm damage, water extraction, drying services</li>
    <li><strong>Emergency Roofing</strong> — Storm damage, leaks, fallen tree damage, temporary tarping</li>
    <li><strong>Garage Door Emergencies</strong> — Broken springs, stuck doors, opener failures</li>
</ul>

<h2>When to Call for Emergency Service</h2>
<p>If you're experiencing any of these situations, call <strong>{biz['phone']}</strong> immediately:</p>
<ul>
    <li>Water leaking or flooding that can cause structural damage</li>
    <li>Complete loss of heating in winter or cooling in summer</li>
    <li>Electrical sparking, smoking outlets, or partial power loss</li>
    <li>Sewage backup or gas odor</li>
    <li>Garage door that won't open or close (safety risk)</li>
    <li>Storm damage with exposed interior or active leaking</li>
</ul>

<h2>Our Emergency Response Promise</h2>
<ul>
    <li><strong>24/7/365 Availability</strong> — Nights, weekends, holidays — we're always here</li>
    <li><strong>Fast Response</strong> — Most emergencies addressed within 1-2 hours</li>
    <li><strong>No Overtime Markup</strong> — Same fair pricing, even at 2 AM</li>
    <li><strong>Licensed Technicians</strong> — Real professionals, even for emergency calls</li>
    <li><strong>Full Equipment</strong> — Service trucks stocked with common parts and tools</li>
</ul>

<h2>Call Now for Emergency Service</h2>
<div style="background:#f0f7ff;border:2px solid #2b6cb0;border-radius:8px;padding:24px;margin:20px 0;text-align:center;">
    <p style="font-size:1.3em;font-weight:bold;">{biz['name']} — Emergency Service</p>
    <p style="font-size:1.5em;"><a href="tel:{biz['phone_link']}" style="color:#2b6cb0;">{biz['phone']}</a></p>
    <p>Available 24 hours · 7 days a week · 365 days a year</p>
    <p>Licensed · Insured · Upfront Pricing · Satisfaction Guaranteed</p>
</div>
</body>
</html>"""


# Page builder registry
PAGE_BUILDERS: dict[str, Any] = {
    "about-us": _build_about_page,
    "service-areas": _build_service_areas_page,
    "contact": _build_contact_page,
    "reviews-grand-rapids": _build_reviews_page,
    "financing": _build_financing_page,
    "warranties": _build_warranties_page,
    "emergency-service": _build_emergency_service_page,
}


def generate_authority_pages(project_root: str = "") -> list[dict[str, Any]]:
    """Generate all authority pages into projects/{name}/authority/."""
    base = project_root if project_root else PROJECT_ROOT
    out_dir = os.path.join(base, "authority")
    os.makedirs(out_dir, exist_ok=True)

    generated = []
    for slug, page_def in AUTHORITY_PAGES.items():
        builder = PAGE_BUILDERS.get(slug)
        if not builder:
            log.warning("No builder for authority page: %s", slug)
            continue

        html = builder()
        if not html:
            continue

        filename = f"{slug}.html"
        filepath = os.path.join(out_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        log.info("Authority page: authority/%s", filename)

        generated.append({
            "slug": slug,
            "title": page_def["title"],
            "filepath": filepath,
            "changefreq": page_def.get("changefreq", "monthly"),
            "priority": page_def.get("priority", 0.8),
        })

    log.info("Authority pages complete: %d pages in %s", len(generated), out_dir)
    return generated


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    pages = generate_authority_pages()
    print(f"Generated {len(pages)} authority pages:")
    for p in pages:
        print(f"  /{p['slug']}/ → {os.path.relpath(p['filepath'])}")
