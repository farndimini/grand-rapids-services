"""Quick test: post-processor banned opener + head/script/style protection."""
import re, sys
sys.path.insert(0, '.')
from post_processor import fix_article, _self_critique_article

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
<h2>Key Features</h2>
<p>This tool offers many features at $29/month.</p>
</body>
</html>"""

fixed = fix_article(html, 'best test tool 2026')
issues = _self_critique_article(fixed, 'best test tool 2026')

first_p = re.search(r'<p[^>]*>(.*?)</p>', fixed, re.DOTALL | re.IGNORECASE)
if first_p:
    opener = first_p.group(1)
    banned = any(re.search(pat, opener.lower()) for pat in [
        r'after (two|three|four|five|six|one|\d+) (weeks?|days?|months?) of testing',
    ])
    print('Banned opener still present:', banned)
    print('First 120 chars:', opener[:120])

title = re.search(r'<title>(.*?)</title>', fixed, re.DOTALL | re.IGNORECASE)
print('Title intact:', title.group(1) if title else 'NO')
style = re.search(r'<style>.*?</style>', fixed, re.DOTALL | re.IGNORECASE)
print('Style block intact:', 'YES' if style else 'NO')
script = re.search(r'<script[^>]*>.*?</script>', fixed, re.DOTALL | re.IGNORECASE)
print('Script block intact:',  'YES' if script else 'NO')

h1_count = len(re.findall(r'<h1[^>]*>', fixed, re.I))
print('H1 count:', h1_count)

print()
print('Issues:', len(issues))
for i in issues:
    print(' -', i)

wc = len(re.sub(r'<[^>]+>', '', fixed).split())
print('Word count:', wc)
print()
print('ALL CHECKS PASSED' if not banned and title and style and script and h1_count == 1 else 'SOME CHECKS FAILED')
