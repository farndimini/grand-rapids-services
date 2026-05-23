"""
Article Formatter — Converts raw SEO Agent output into professional HTML.
Usage:  python format_article.py input.md [output.html]
"""

import re
import sys
from datetime import datetime
from pathlib import Path
from config import SETTINGS as _fmt_cfg

TEMPLATE = Path("template_professional.html").read_text(encoding="utf-8")

def slug(text: str) -> str:
    return re.sub(r"[^\w\s-]", "", text).lower().replace(" ", "-")[:50]

def extract_title(html: str) -> str:
    m = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if m: return m.group(1).strip()
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
    if m: return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    return "Article"

def extract_desc(html: str) -> str:
    m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html, re.IGNORECASE)
    return m.group(1) if m else "Complete guide and analysis."

def extract_body(html: str) -> str:
    """Extract content between <h1> and </body>, strip editorial comments."""
    body = html
    m = re.search(r'(<h1[^>]*>.*?)</body>', body, re.IGNORECASE | re.DOTALL)
    if m: body = m.group(1)
    else:
        m = re.search(r'<body[^>]*>(.*?)</body>', body, re.IGNORECASE | re.DOTALL)
        if m: body = m.group(1)
    # Remove editorial audit comments
    body = re.sub(r'<!-- Editorial Audit.*?-->', '', body, flags=re.DOTALL)
    body = re.sub(r'<!-- REWRITE NEEDED.*?-->', '', body, flags=re.DOTALL)
    body = re.sub(r'<p[^>]*style="color:#c00[^"]*"[^>]*>.*?</p>', '', body, flags=re.DOTALL)
    body = re.sub(r'<p[^>]*>⚠.*?Rewrite recommended.*?</p>', '', body, flags=re.DOTALL)
    # Remove schema.org meta tags in body
    body = re.sub(r'<meta\s+itemprop[^>]*>', '', body, flags=re.DOTALL)
    body = re.sub(r'</?meta[^>]*>', '', body, flags=re.DOTALL)
    # Wrap bare H2s and below that aren't in proper tags
    body = body.strip()
    return body

def make_toc(html: str) -> str:
    """Generate table of contents from H2 headings."""
    headings = re.findall(r'<h2[^>]*id="?([^"\s]*)"?[^>]*>(.*?)</h2>', html, re.IGNORECASE | re.DOTALL)
    if not headings:
        headings = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.IGNORECASE | re.DOTALL)
        if not headings: return ""
        items = []
        for h in headings:
            text = re.sub(r'<[^>]+>', '', h).strip()
            hid = slug(text)
            items.append(f'<a href="#{hid}">{text}</a>')
            html = html.replace(f'<h2>{h}</h2>', f'<h2 id="{hid}">{h}</h2>', 1)
    else:
        items = []
        for hid, h in headings:
            text = re.sub(r'<[^>]+>', '', h).strip()
            items.append(f'<a href="#{hid}">{text}</a>')
    if not items: return html, ""
    toc = f'<div class="toc"><h3>📑 Table of Contents</h3>' + "\n".join(items) + '</div>'
    return html, toc

def format_article(input_path: str, output_path: str = None) -> str:
    raw = Path(input_path).read_text(encoding="utf-8")

    # Remove YAML frontmatter
    raw = re.sub(r'^---\n.*?---\n', '', raw, flags=re.DOTALL)

    title = extract_title(raw)
    desc = extract_desc(raw)
    body = extract_body(raw)

    # Add IDs to H2s for TOC
    body, toc = make_toc(body)

    # Build meta
    today = datetime.now().strftime("%B %d, %Y")
    author_name = _fmt_cfg.get("author_name", "SEO Agent Pro")
    site_url = _fmt_cfg.get("site_url", "https://yoursite.com").rstrip("/")
    meta = f'<div class="meta"><span>📅 {today}</span><span>✍️ {author_name}</span><span>⏱ {len(body.split()) // 200 + 1} min read</span></div>'

    # Inject TOC after first paragraph or after H1
    body = body.replace('<h1', '<h1', 1)

    full_html = TEMPLATE.replace("[TITLE]", title.replace('"', '&quot;'))
    full_html = full_html.replace("[DESCRIPTION]", desc.replace('"', '&quot;'))
    full_html = full_html.replace("[CANONICAL_URL]", f"{site_url}/{slug(title)}")
    full_html = full_html.replace("[DATE]", datetime.now().strftime("%Y-%m-%d"))
    full_html = full_html.replace("[CONTENT]", f"<h1>{title}</h1>\n{meta}\n{toc}\n{body}")

    if not output_path:
        output_path = input_path.replace(".md", ".html").replace(".html", "_formatted.html")
        if output_path == input_path:
            output_path = Path(input_path).stem + "_formatted.html"

    Path(output_path).write_text(full_html, encoding="utf-8")
    print(f"  ✓ Formatted → {output_path}")
    return output_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python format_article.py input.md [output.html]")
        sys.exit(1)
    format_article(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
