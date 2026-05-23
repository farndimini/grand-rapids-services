"""Check if banned opener still present after fix_article."""
import sys, re
sys.path.insert(0, '.')
from post_processor import fix_article

html = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>Best Chrome Extension 2026 - Full Review</title>
<style>body { font-family: Arial; }</style>
</head><body>
<script type="application/ld+json">{"@type": "Article"}</script>
<h1>Best Chrome Extension 2026</h1>
<div class="meta">Published: May 21, 2026 | 8 min read</div>
<p>After two weeks of testing the top Chrome extensions, here is what I found.</p>
<h2>Introduction</h2>
<p>Chrome extensions can dramatically improve your browsing experience.</p>
</body></html>"""

fixed = fix_article(html, 'best chrome extension 2026')
banned_pattern = r'after (two|three|four|five|six|one|\d+) (weeks?|days?|months?) of testing'
found = re.search(banned_pattern, fixed, re.IGNORECASE)
if found:
    print('BANNED OPENER STILL PRESENT:', found.group())
else:
    print('Banned opener successfully removed')

# Check paragraphs
for i, m in enumerate(re.finditer(r'<p[^>]*>(.*?)</p>', fixed, re.DOTALL | re.I)):
    txt = m.group(1).strip()
    print(f'  <p> #{i}: {txt[:100]}')
