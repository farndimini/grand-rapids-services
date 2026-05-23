"""Debug first paragraph detection in post-processor."""
import sys, re
sys.path.insert(0, '.')
from post_processor import _wrap_bare_paragraphs, _fix_opener

html = """<!DOCTYPE html>
<html>
<head>
<title>Best Test Tool 2026 - Full Review</title>
<meta charset="utf-8">
<style>
body { font-family: Arial; }
h1 { color: blue; }
</style>
</head>
<body>
<script type="application/ld+json">{"@type": "Article", "name": "Test"}</script>
<h1>Best Test Tool 2026</h1>
<div class="meta">Published: May 21, 2026 | By Author</div>
<p>After two weeks of testing various test tools, I found some interesting results. Here is what happened.</p>
<h2>Introduction</h2>
<p>Test tools are essential for modern development.</p>
</body>
</html>"""

# Step 1: Just wrap, don't fix_opener yet
wrapped = _wrap_bare_paragraphs(html)
print("=== After _wrap_bare_paragraphs ===")
for i, m in enumerate(re.finditer(r'<p[^>]*>(.*?)</p>', wrapped, re.DOTALL | re.IGNORECASE)):
    text = m.group(1)[:100]
    print(f"  <p> #{i}: {text!r}")
    if i > 5:
        break

# Step 2: Now fix_opener
fixed = _fix_opener(html, "best test tool 2026")
print("\n=== After _fix_opener ===")
for i, m in enumerate(re.finditer(r'<p[^>]*>(.*?)</p>', fixed, re.DOTALL | re.IGNORECASE)):
    text = m.group(1)[:100]
    print(f"  <p> #{i}: {text!r}")
    if i > 5:
        break

# What does the regex match as first_p?
first_p = re.search(r'(<p[^>]*>)(.*?)(</p>)', fixed, re.DOTALL | re.IGNORECASE)
if first_p:
    print(f"\nFirst p tag matched by regex:\n  OPEN: {first_p.group(1)}\n  TEXT: {first_p.group(2)[:100]!r}")
