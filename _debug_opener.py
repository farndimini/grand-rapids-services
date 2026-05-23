"""Debug _fix_opener targeting."""
import sys, re
sys.path.insert(0, '.')
from post_processor import _wrap_bare_paragraphs, _fix_opener

html = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Best Chrome Extension 2026 - Full Review</title>
<style>body { font-family: Arial; }</style>
</head>
<body>
<script type="application/ld+json">{"@type": "Article"}</script>
<h1>Best Chrome Extension 2026</h1>
<div class="meta">Published: May 21, 2026 | 8 min read</div>
<p>After two weeks of testing the top Chrome extensions, here is what I found.</p>
<h2>Introduction</h2>
<p>Chrome extensions can dramatically improve your browsing experience.</p>
</body>
</html>"""

wrapped = _wrap_bare_paragraphs(html)
print("=== All <p> tags after wrapping ===")
for i, m in enumerate(re.finditer(r'(<p[^>]*>)(.*?)(</p>)', wrapped, re.DOTALL | re.IGNORECASE)):
    txt = m.group(2).strip()
    prev = wrapped[max(0, m.start()-200):m.start()]
    has_meta = bool(re.search(r'class=["\']meta["\']', prev, re.I))
    is_published = bool(re.match(r'^(Published|Updated|By |Posted|Date)', txt, re.I))
    print(f"  #{i}: len={len(txt)}, meta_in_prev={has_meta}, starts_meta={is_published}")
    print(f"    text: {txt[:80]!r}")
    print(f"    prev (last 80): ...{prev[-80:]!r}")
    print()

fixed = _fix_opener(html, "best chrome extension 2026")
first_p = re.search(r'<p[^>]*>(.*?)</p>', fixed, re.DOTALL | re.IGNORECASE)
print("=== After _fix_opener, first <p>: ===")
if first_p:
    print(f"  {first_p.group(1)[:100]!r}")
