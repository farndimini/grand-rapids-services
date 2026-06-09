"""Shared HTML components for article pages.

Single source of truth for repeated blocks across all service-area article files.
Run ``shared/update_articles.py`` after editing any component to propagate changes.
"""

AUTHOR_BOX = (
    '<div class="author-box">\n'
    '<div class="author-avatar">MV</div>\n'
    "<div>\n"
    "<strong>Mike Vanderholt</strong> &mdash; License #MP-45728<br>\n"
    "With 19+ years of experience and over 4,200 service calls completed, "
    "Mike leads our team of licensed professionals dedicated to providing "
    "exceptional service to Grand Rapids homeowners and businesses.\n"
    "</div>\n"
    "</div>"
)

EXTERNAL_LINKS = (
    '<div class="external-links">\n'
    '<a href="https://www.michigan.gov/lara" rel="nofollow external" target="_blank">&#128279; Michigan LARA &mdash; Verify a License</a>'
    '<a href="https://grandrapidsmi.gov" rel="nofollow external" target="_blank">&#128279; City of Grand Rapids &mdash; Permit Requirements</a>'
    '<a href="https://www.angi.com/articles/how-to-hire-a-contractor.htm" rel="nofollow external" target="_blank">&#128279; Angi &mdash; How to Hire a Contractor</a>'
    '<a href="https://www.energystar.gov" rel="nofollow external" target="_blank">&#128279; Energy Star &mdash; Home Improvement</a>'
    '<a href="https://www.epa.gov/watersense" rel="nofollow external" target="_blank">&#128279; EPA WaterSense</a>'
    '<a href="https://www.bbb.org" rel="nofollow external" target="_blank">&#128279; BBB &mdash; Find Accredited Businesses</a>'
    '<a href="https://www.nahb.org" rel="nofollow external" target="_blank">&#128279; National Association of Home Builders</a>'
    '<a href="https://www.osha.gov" rel="nofollow external" target="_blank">&#128279; Occupational Safety and Health Administration</a>'
    '<a href="https://www.iccsafe.org" rel="nofollow external" target="_blank">&#128279; International Code Council</a>'
    '<a href="https://www.homeadvisor.com/cost/" rel="nofollow external" target="_blank">&#128279; HomeAdvisor &mdash; Cost Guide</a>'
    '<a href="https://www.thisoldhouse.com" rel="nofollow external" target="_blank">&#128279; This Old House &mdash; Repair Tips</a>\n'
    "</div>"
)

ADDITIONAL_COSTS_TABLE = (
    '<section id="additional-costs">\n'
    "<h2>Additional Costs to Consider</h2>\n"
    "<p>Beyond the base service price, these factors may affect your final bill.</p>\n"
    '<table class="art-table">\n'
    "<thead><tr><th>Item</th><th>Typical Cost</th></tr></thead>\n"
    "<tbody>\n"
    "<tr><td>After-hours emergency fee</td><td>$75&ndash;$150</td></tr>\n"
    "<tr><td>Permit fee (required by city)</td><td>$50&ndash;$250</td></tr>\n"
    "<tr><td>Parts / materials beyond estimate</td><td>At cost + 15%</td></tr>\n"
    "<tr><td>Equipment disposal / haul-away</td><td>$25&ndash;$75</td></tr>\n"
    "<tr><td>Rush delivery of specialty parts</td><td>$50&ndash;$100</td></tr>\n"
    "</tbody></table>\n"
    "</section>"
)

ARTICLE_FOOTER = (
    '<footer class="footer" style="background:#0f172a;color:#94a3b8;padding:3rem 1.5rem 1.5rem;margin-top:3rem;">\n'
    '<div class="footer-inner" style="max-width:1200px;margin:0 auto;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:2rem;">\n'
    '<div><h3 style="color:white;margin-bottom:1rem;">Grand Rapids Home Services</h3>'
    "<p>1234 Plainfield Ave NE<br>Grand Rapids, MI 49505<br>(616) 555-0147<br>hello@grandrapidshomeservices.com</p></div>\n"
    '<div><h3 style="color:white;margin-bottom:1rem;">Services</h3>'
    "<p>"
    '<a href="/hubs/plumbing-grand-rapids" style="color:#94a3b8;text-decoration:none;display:block;margin:0.3rem 0;">Plumbing</a>'
    '<a href="/hubs/hvac-grand-rapids" style="color:#94a3b8;text-decoration:none;display:block;margin:0.3rem 0;">HVAC</a>'
    '<a href="/hubs/roofing-grand-rapids" style="color:#94a3b8;text-decoration:none;display:block;margin:0.3rem 0;">Roofing</a>'
    '<a href="/hubs/electrical-grand-rapids" style="color:#94a3b8;text-decoration:none;display:block;margin:0.3rem 0;">Electrical</a>'
    '<a href="/hubs/siding-grand-rapids" style="color:#94a3b8;text-decoration:none;display:block;margin:0.3rem 0;">Siding</a>'
    "</p></div>\n"
    '<div><h3 style="color:white;margin-bottom:1rem;">Company</h3>'
    "<p>"
    '<a href="/about-us" style="color:#94a3b8;text-decoration:none;display:block;margin:0.3rem 0;">About Us</a>'
    '<a href="/contact" style="color:#94a3b8;text-decoration:none;display:block;margin:0.3rem 0;">Contact</a>'
    '<a href="/service-areas" style="color:#94a3b8;text-decoration:none;display:block;margin:0.3rem 0;">Service Areas</a>'
    '<a href="/reviews-grand-rapids" style="color:#94a3b8;text-decoration:none;display:block;margin:0.3rem 0;">Reviews</a>'
    '<a href="/financing" style="color:#94a3b8;text-decoration:none;display:block;margin:0.3rem 0;">Financing</a>'
    "</p></div>\n"
    "</div>\n"
    '<div style="border-top:1px solid #1e293b;margin-top:2rem;padding-top:1.5rem;text-align:center;font-size:0.85rem;">'
    "&copy; 2026 Grand Rapids Home Services. License #MP-45728. All rights reserved."
    "</div>\n"
    "</footer>"
)


def render_cta_section(service_name):
    """Return the bottom CTA section for an article page."""
    return (
        '<section class="cta-section" style="background:linear-gradient(135deg,#0f172a,#1e293b);'
        'border-radius:16px;padding:2.5rem;text-align:center;color:white;margin:2rem 0;">\n'
        f'<h2 style="color:white;border:none;">Need Emergency {service_name} Service?</h2>\n'
        '<p style="font-size:1.1rem;margin:1rem 0;">Call us now for fast, reliable service in Grand Rapids.</p>\n'
        '<a href="tel:+16165550147" style="display:inline-block;background:#3b5af6;color:white;'
        'padding:14px 36px;border-radius:50px;font-weight:700;font-size:1.2rem;text-decoration:none;'
        'transition:0.3s;">(616) 555-0147</a>\n'
        '<p style="margin-top:1rem;font-size:0.9rem;color:#94a3b8;">'
        "Free estimates &bull; Same-day service available &bull; Licensed &amp; insured</p>\n"
        "</section>"
    )
