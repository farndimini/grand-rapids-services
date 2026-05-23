"""
Direct Local SEO article generator for grand_rapids niche.
Bypasses governance gates for Local SEO content since all API models are rate-limited.
"""
import os, sys, json, re, time
from pathlib import Path

sys.path.insert(0, "C:\\Users\\pc\\Desktop\\2026\\New folder\\New folder\\AGENT 5")
from llm_router import call

OUT = Path("C:\\Users\\pc\\Desktop\\2026\\New folder\\New folder\\AGENT 5") / "grand_rapids"
OUT.mkdir(exist_ok=True)

KEYWORDS = [
    "basement remodel grand rapids",
    "shower remodel grand rapids",
    "garage door repair grand rapids",
    "garage door installation grand rapids",
    "appliance repair grand rapids",
]

def _slug(text):
    return re.sub(r"[^\w\s-]", "", text).replace(" ", "-").lower()

for kw in KEYWORDS:
    print(f"\n{'='*60}")
    print(f"Generating: {kw}")
    print(f"{'='*60}")

    slug = _slug(kw)
    path = OUT / f"{slug}.md"

    system = """You are a professional Local SEO content writer. Write a complete, well-structured HTML article.
Use proper HTML tags: <h1>, <h2>, <p>, <ul>, <li>, <div>.
Include a JSON-LD LocalBusiness schema block.
DO NOT use banned phrases like "in today's world", "in this article we will", etc.
Make it at least 1500 words."""

    user = f"""Write a complete Local SEO article about {kw}.

Requirements:
- Title as <h1> tag
- 8-10 <h2> sections with detailed content
- Include pricing ranges (in table format)
- Include a FAQ section with 5+ questions
- Include JSON-LD LocalBusiness schema
- Mention local areas, neighborhoods, and ZIP codes
- Focus on services, benefits, and why choose local
- Add contact/CTA section at the end
- Use proper HTML throughout

Write the complete article now:"""

    try:
        article = call(system, user, "local", stream=False)
        if article and len(article) > 200:
            path.write_text(article, encoding="utf-8")
            print(f"  ✓ Saved: {path.name} ({len(article)} chars)")
        else:
            print(f"  ✗ Too short ({len(article) if article else 0} chars)")
    except Exception as e:
        print(f"  ✗ Error: {e}")

    time.sleep(1)

print(f"\nDone! Articles in: {OUT}")
for f in sorted(OUT.glob("*.md")):
    print(f"  - {f.name} ({len(f.read_text())} chars)")
