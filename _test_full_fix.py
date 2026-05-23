"""Test the full post-processor fix with realistic article HTML."""
import sys, re
sys.path.insert(0, '.')
from post_processor import fix_article

# Simulate realistic LLM output with proper tags
html = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Best Chrome Extension 2026 - Full Review</title>
<meta name="description" content="Review of the best Chrome extensions for productivity.">
<style>
body { font-family: Arial; line-height: 1.6; }
h1 { color: #333; }
</style>
</head>
<body>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Article","name":"Best Chrome Extension 2026"}</script>
<h1>Best Chrome Extension 2026</h1>
<div class="meta">Published: May 21, 2026 | 8 min read</div>
<p>After two weeks of testing the top Chrome extensions, here is what I found.</p>
<h2>Introduction</h2>
<p>Chrome extensions can dramatically improve your browsing experience.</p>
<h2>Top Picks</h2>
<h3>Extension One</h3>
<p>This is the best extension for productivity. It costs $29/year.</p>
<h3>Extension Two</h3>
<p>Great for focus and time management. Pricing: Free.</p>
<h2>Comparison Table</h2>
<table>
<tr><th>Feature</th><th>Ext One</th><th>Ext Two</th></tr>
<tr><td>Price</td><td>$29/yr</td><td>Free</td></tr>
</table>
<h2>FAQ</h2>
<div class="faq-item"><div class="faq-q">Q: Is Extension One worth it?</div><div class="faq-a">A: Yes, for most users.</div></div>
<div class="faq-item"><div class="faq-q">Q: Is Extension Two free?</div><div class="faq-a">A: Yes, completely free.</div></div>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":"Is Extension One worth it?","acceptedAnswer":{"@type":"Answer","text":"Yes"}}]}</script>
</body>
</html>"""

fixed = fix_article(html, "best chrome extension 2026")

# Check head/title/style/script integrity
title = re.search(r'<title>(.*?)</title>', fixed, re.DOTALL | re.IGNORECASE)
print('Title:', repr(title.group(1)[:80]) if title else 'MISSING!')
assert title, 'Title MISSING'
assert '<p>' not in title.group(1), f'Title corrupted with <p>: {title.group(1)[:80]}'

style = re.search(r'<style>(.*?)</style>', fixed, re.DOTALL | re.IGNORECASE)
assert style, 'Style MISSING'
assert '<p>' not in style.group(1), 'Style corrupted with <p>'

head_script = re.search(r'<script type="application/ld\+json">(\{.*?"@type":\s*"Article".*?\})</script>', fixed, re.DOTALL | re.IGNORECASE)
# The Article schema might have been moved but should exist
has_article = '"@type": "Article"' in fixed or '"@type":"Article"' in fixed
assert has_article, 'Article schema MISSING'

# Check banned opener was replaced
first_p = re.search(r'<p[^>]*>(.*?)</p>', fixed, re.DOTALL | re.IGNORECASE)
assert first_p, 'No first paragraph found'
opener = first_p.group(1)
banned = any(re.search(pat, opener.lower()) for pat in [
    r'after (two|three|four|five|six|one|\d+) (weeks?|days?|months?) of testing',
])
assert not banned, f'Banned opener still present: {opener[:80]}'
print('First paragraph (banned replaced):', opener[:80])

# Check H1 count
h1_count = len(re.findall(r'<h1[^>]*>', fixed, re.I))
assert h1_count == 1, f'H1 count: {h1_count}'
print('H1 count:', h1_count)

# Check FAQ schema matches FAQ items
faq_qs = re.findall(r'class="faq-q"[^>]*>(.*?)</div>', fixed, re.DOTALL)
faq_schema = re.findall(r'"name":\s*"([^"]+)"', fixed)
print('FAQ items:', len(faq_qs))
print('Word count:', len(re.sub(r'<[^>]+>', '', fixed).split()))

# Check external links have proper attrs
links = re.findall(r'<a\s[^>]*href="https?://[^"]*"[^>]*>', fixed, re.I)
bad_links = [l for l in links if 'rel="nofollow noopener"' not in l.lower() or 'target="_blank"' not in l]
print('Links with proper attrs:', len(links) - len(bad_links), '/', len(links))

print()
print('ALL ASSERTIONS PASSED')
