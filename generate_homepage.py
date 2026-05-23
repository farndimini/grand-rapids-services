"""
generate_homepage.py — Build projects/grand_rapids/index.html from live data

Run this after adding services/cities/modifiers to keep homepage in sync.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["SEO_AGENT_TEST_MODE"] = "1"

from programmatic_expander import SERVICES, MODIFIERS, EXPAND_CITIES, SITE_URL, SITE_NAME
from local_intelligence import BUSINESS_IDENTITY, REVIEWS

SITE = "https://yoursite.com"

service_categories = {
    "Home Appliance Services": ["appliance repair"],
    "Garage Door Services": ["garage door repair", "garage door installation"],
    "Home Remodeling": ["basement remodel", "shower remodel", "kitchen remodeling", "bathroom remodeling"],
    "Plumbing & Water Services": ["plumbing", "water damage restoration"],
    "Heating & Cooling": ["hvac"],
    "Electrical Services": ["electrical"],
    "Exterior Services": ["roofing", "siding", "window replacement"],
    "Restoration Services": ["water damage restoration", "mold remediation"],
    "Flooring & Surfaces": ["flooring"],
    "Concrete & Masonry": ["concrete"],
    "Outdoor Living": ["deck and patio", "landscaping"],
    "Painting & Finishing": ["painting"],
    "Fencing & Gates": ["fencing"],
    "Tree Care & Removal": ["tree service"],
    "Pest Management": ["pest control"],
}


def _make_slug(service: str) -> str:
    return service.replace(" ", "-")


def _service_url(service: str, modifier: str, city_slug: str) -> str:
    mod_key = modifier.lower().replace(" ", "-")
    svc = _make_slug(service)
    return f"{SITE}/{mod_key}-{svc}-{city_slug}/"


def _hub_url(service: str) -> str:
    from internal_linking_engine import _get_hub_data
    _, hub_slug, _ = _get_hub_data(service)
    return f"{SITE}/{hub_slug}"


def _authority_url(slug: str) -> str:
    return f"{SITE}/{slug}"


def build_homepage() -> str:
    biz = BUSINESS_IDENTITY
    cities = list(EXPAND_CITIES.keys())
    mods = list(MODIFIERS.keys())

    # Count total pages
    total_service = len(SERVICES) * len(cities) * len(mods)
    total_neighborhood = len(SERVICES) * 17
    total_hubs = len(SERVICES)
    total_authority = 7

    # Schema
    org_schema = {
        "@context": "https://schema.org",
        "@type": ["HomeAndConstructionBusiness", "LocalBusiness"],
        "name": biz["name"],
        "description": f"Professional home services in Grand Rapids, MI since {biz['founded_year']}. {total_service}+ service pages covering {len(SERVICES)} home services across {len(cities)} cities.",
        "url": SITE,
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
        "geo": {"@type": "GeoCoordinates", "latitude": 42.9634, "longitude": -85.6681},
        "areaServed": [{"@type": "City", "name": c} for c in cities],
        "foundingDate": f"{biz['founded_year']}-01-01",
        "priceRange": "$$",
    }
    schema_html = f'<script type="application/ld+json">{json.dumps(org_schema, ensure_ascii=False)}</script>'

    # Service category cards
    svc_cards = ""
    for cat, svcs in sorted(service_categories.items()):
        links = " · ".join(
            f'<a href="{_hub_url(s)}" class="svc-link">{s.title()}</a>'
            for s in svcs
        )
        svc_cards += f"""
        <div class="card">
            <h3>{cat}</h3>
            <p>{links}</p>
        </div>"""

    # City grid
    city_grid = ""
    for c in cities:
        slug = EXPAND_CITIES[c]["slug"]
        city_grid += f"""
        <a href="{SITE}/{slug}" class="city-card">{c}</a>"""

    # Modifier badges
    mod_badges = ""
    for m in mods:
        label = MODIFIERS[m]["label"]
        city_slug = EXPAND_CITIES[cities[0]]["slug"]
        svc_slug = _make_slug(SERVICES[0])
        url = f"{SITE}/{m}-{svc_slug}-{city_slug}/"
        mod_badges += f'<a href="{url}" class="mod-badge">{label}</a>'

    # Reviews
    all_reviews = []
    for niche_list in REVIEWS.values():
        if isinstance(niche_list, list):
            all_reviews.extend(niche_list)
    rev_html = ""
    for r in all_reviews[:3]:
        stars = "★" * int(r["rating"]) + "☆" * (5 - int(r["rating"]))
        rev_html += f"""
        <div class="review-card">
            <p>"{r['text']}"</p>
            <p class="review-meta">— {r['reviewer']}, {r['area']} <span class="stars">{stars}</span></p>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{biz['name']} — Professional Home Services in Grand Rapids, MI</title>
    <meta name="description" content="{biz['name']} offers professional {len(SERVICES)} home services across {len(cities)} West Michigan cities. Licensed, insured, same-day service since {biz['founded_year']}.">
    <link rel="canonical" href="{SITE}/">
    <meta name="geo.region" content="US-MI">
    <meta name="geo.placename" content="Grand Rapids">
    <meta name="geo.position" content="42.9634;-85.6681">
    <meta name="ICBM" content="42.9634, -85.6681">
    {schema_html}
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a202c; line-height: 1.6; }}
        .container {{ max-width: 1100px; margin: 0 auto; padding: 0 20px; }}
        header {{ background: linear-gradient(135deg, #2b6cb0, #2c5282); color: #fff; padding: 48px 0; text-align: center; }}
        header h1 {{ font-size: 2.2em; margin-bottom: 8px; }}
        header p {{ font-size: 1.1em; opacity: 0.9; }}
        .cta-banner {{ background: #edf2f7; text-align: center; padding: 32px 0; border-bottom: 3px solid #2b6cb0; }}
        .cta-banner h2 {{ color: #2b6cb0; }}
        .cta-banner a {{ color: #2b6cb0; font-size: 1.6em; font-weight: bold; text-decoration: none; }}
        .cta-banner a:hover {{ text-decoration: underline; }}
        section {{ padding: 40px 0; }}
        section:nth-child(even) {{ background: #f7fafc; }}
        h2 {{ font-size: 1.5em; margin-bottom: 20px; color: #2d3748; }}
        .card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 16px; }}
        .card h3 {{ color: #2b6cb0; margin-bottom: 8px; font-size: 1.1em; }}
        .svc-link {{ color: #4a5568; text-decoration: none; }}
        .svc-link:hover {{ color: #2b6cb0; text-decoration: underline; }}
        .city-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }}
        .city-card {{ display: block; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; text-align: center; color: #2d3748; text-decoration: none; font-weight: 500; }}
        .city-card:hover {{ border-color: #2b6cb0; color: #2b6cb0; }}
        .mod-badge {{ display: inline-block; background: #ebf8ff; color: #2b6cb0; border: 1px solid #bee3f8; border-radius: 20px; padding: 6px 16px; margin: 4px; text-decoration: none; font-size: 0.9em; }}
        .mod-badge:hover {{ background: #2b6cb0; color: #fff; }}
        .review-card {{ background: #fff; border-left: 4px solid #2b6cb0; padding: 16px; margin-bottom: 12px; border-radius: 0 8px 8px 0; }}
        .review-meta {{ font-size: 0.85em; color: #718096; margin-top: 8px; }}
        .stars {{ color: #e6a817; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 16px; text-align: center; }}
        .stat {{ background: #fff; padding: 24px; border-radius: 8px; border: 1px solid #e2e8f0; }}
        .stat-num {{ font-size: 2em; font-weight: bold; color: #2b6cb0; }}
        .stat-label {{ font-size: 0.85em; color: #718096; }}
        footer {{ background: #2d3748; color: #a0aec0; text-align: center; padding: 32px 0; font-size: 0.9em; }}
        footer a {{ color: #bee3f8; text-decoration: none; }}
        footer a:hover {{ text-decoration: underline; }}
        .auth-links {{ display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; padding: 12px 0; }}
        .auth-links a {{ color: #fff; text-decoration: none; padding: 4px 12px; border: 1px solid rgba(255,255,255,0.3); border-radius: 4px; font-size: 0.9em; }}
        .auth-links a:hover {{ background: rgba(255,255,255,0.1); }}
        @media (max-width: 600px) {{ header h1 {{ font-size: 1.6em; }} .city-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
    </style>
</head>
<body>

<header>
    <div class="container">
        <h1>{biz['name']}</h1>
        <p>Licensed & Insured Home Services in Grand Rapids, MI — Since {biz['founded_year']}</p>
        <div class="auth-links">
            <a href="{_authority_url('about-us')}">About</a>
            <a href="{_authority_url('service-areas')}">Service Areas</a>
            <a href="{_authority_url('contact')}">Contact</a>
            <a href="{_authority_url('reviews-grand-rapids')}">Reviews</a>
            <a href="{_authority_url('financing')}">Financing</a>
            <a href="{_authority_url('warranties')}">Warranties</a>
            <a href="{_authority_url('emergency-service')}">Emergency</a>
        </div>
    </div>
</header>

<div class="cta-banner">
    <div class="container">
        <h2>Need Service? We're Available 24/7</h2>
        <p><a href="tel:{biz['phone_link']}">{biz['phone']}</a></p>
        <p>Free Estimates · Licensed Technicians · Same-Day Service</p>
    </div>
</div>

<section>
    <div class="container">
        <h2>Our Services</h2>
        <p>We provide {len(SERVICES)} professional home services across all of West Michigan. Each service has detailed pages with pricing, FAQs, and local information.</p>
        {svc_cards}
    </div>
</section>

<section>
    <div class="container">
        <h2>Service Modifiers</h2>
        <p>Find the right service for your needs — every service is available in these formats:</p>
        <div style="text-align:center;">
            {mod_badges}
        </div>
        <p style="margin-top:12px;font-size:0.9em;color:#718096;">Each modifier × service × city combination has a unique, locally-optimized page with neighborhood info, FAQ, and pricing.</p>
    </div>
</section>

<section>
    <div class="container">
        <h2>Cities We Serve</h2>
        <p>Click a city to see all services available in your area.</p>
        <div class="city-grid">
            {city_grid}
        </div>
    </div>
</section>

<section>
    <div class="container">
        <h2>By the Numbers</h2>
        <div class="stats">
            <div class="stat"><div class="stat-num">{len(SERVICES)}</div><div class="stat-label">Services</div></div>
            <div class="stat"><div class="stat-num">{len(cities)}</div><div class="stat-label">Cities</div></div>
            <div class="stat"><div class="stat-num">{len(mods)}</div><div class="stat-label">Modifiers</div></div>
            <div class="stat"><div class="stat-num">{total_service + total_neighborhood + total_hubs + total_authority}</div><div class="stat-label">Total Pages</div></div>
        </div>
    </div>
</section>

<section>
    <div class="container">
        <h2>What Our Customers Say</h2>
        {rev_html}
        <p style="margin-top:12px;"><a href="{_authority_url('reviews-grand-rapids')}">Read all {len(all_reviews)} reviews →</a></p>
    </div>
</section>

<section>
    <div class="container">
        <h2>Emergency Service Available 24/7</h2>
        <p>For urgent plumbing, HVAC, electrical, water damage, or garage door emergencies, our team is on standby around the clock. No overtime charges for nights, weekends, or holidays.</p>
        <p style="text-align:center;margin-top:16px;"><a href="{_authority_url('emergency-service')}" style="background:#e53e3e;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;display:inline-block;font-weight:bold;">24/7 Emergency Service — Call {biz['phone']}</a></p>
    </div>
</section>

<footer>
    <div class="container">
        <p><strong>{biz['name']}</strong> · {biz['address']}, {biz['city']}, {biz['state']} {biz['zip']}</p>
        <p>Phone: <a href="tel:{biz['phone_link']}">{biz['phone']}</a> · Email: {biz['email']}</p>
        <p>Hours: Mon-Fri 7:00 AM - 7:00 PM · Sat 8:00 AM - 5:00 PM · Emergency 24/7</p>
        <p style="margin-top:8px;font-size:0.85em;">&copy; {biz['founded_year']}–2026 {biz['name']}. All rights reserved. | <a href="{SITE}/sitemap/sitemap-index.xml">Sitemap</a></p>
    </div>
</footer>

</body>
</html>"""


if __name__ == "__main__":
    html = build_homepage()
    out_path = os.path.join(os.path.dirname(__file__), "projects", "grand_rapids", "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Homepage written: {out_path} ({len(html)} bytes)")
