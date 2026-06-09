#!/usr/bin/env python3
"""Update article HTML files to use shared assets and components.

Replaces duplicated inline blocks with references to shared files:
  - Inline <style> block  -> <link> to /assets/article.css
  - Inline FAQ toggle JS  -> <script src="/assets/faq-toggle.js">
  - Author box HTML       -> canonical version from article_components
  - External links HTML   -> canonical version from article_components
  - Additional costs HTML -> canonical version from article_components
  - Footer HTML           -> canonical version from article_components

Run from repo root:  python shared/update_articles.py
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from shared.article_components import (
    ADDITIONAL_COSTS_TABLE,
    ARTICLE_FOOTER,
    AUTHOR_BOX,
    EXTERNAL_LINKS,
)

ARTICLE_DIRS = ["emergency", "24_hour", "same_day", "affordable", "near_me"]

ARTICLE_CSS_LINK = '<link rel="stylesheet" href="/assets/article.css">'
FAQ_TOGGLE_SCRIPT = '<script src="/assets/faq-toggle.js"></script>'


def collect_article_files():
    """Return list of article HTML file paths."""
    paths = []
    for d in ARTICLE_DIRS:
        dirpath = os.path.join(ROOT, d)
        if not os.path.isdir(dirpath):
            continue
        for fname in sorted(os.listdir(dirpath)):
            if fname.endswith(".html"):
                paths.append(os.path.join(dirpath, fname))
    return paths


def replace_inline_css(html):
    """Replace <style>...</style> with <link> to article.css."""
    pattern = re.compile(r"<style>\n.*?</style>\n", re.DOTALL)
    if not pattern.search(html):
        return html
    if ARTICLE_CSS_LINK in html:
        return pattern.sub("", html)
    return pattern.sub(ARTICLE_CSS_LINK + "\n", html)


def replace_faq_toggle(html):
    """Replace inline FAQ toggle script with external <script src>."""
    pattern = re.compile(
        r"<script>\s*document\.querySelectorAll\('\.faq-q'\)\.forEach.*?</script>",
        re.DOTALL,
    )
    if not pattern.search(html):
        return html
    if FAQ_TOGGLE_SCRIPT in html:
        return pattern.sub("", html)
    return pattern.sub(FAQ_TOGGLE_SCRIPT, html)


def replace_author_box(html):
    """Replace author box HTML with canonical version."""
    pattern = re.compile(
        r'<div class="author-box">.*?</div>\s*</div>', re.DOTALL
    )
    return pattern.sub(AUTHOR_BOX, html)


def replace_external_links(html):
    """Replace external links block with canonical version."""
    pattern = re.compile(
        r'<div class="external-links">\n?.*?</div>', re.DOTALL
    )
    return pattern.sub(EXTERNAL_LINKS, html)


def replace_additional_costs(html):
    """Replace additional costs section with canonical version."""
    pattern = re.compile(
        r'<section id="additional-costs">.*?</section>', re.DOTALL
    )
    return pattern.sub(ADDITIONAL_COSTS_TABLE, html)


def replace_footer(html):
    """Replace footer with canonical version."""
    pattern = re.compile(r"<footer.*?</footer>", re.DOTALL)
    return pattern.sub(ARTICLE_FOOTER, html)


def update_file(path):
    """Apply all transformations to a single article file."""
    with open(path, "r", encoding="utf-8") as f:
        original = f.read()

    html = original
    html = replace_inline_css(html)
    html = replace_faq_toggle(html)
    html = replace_author_box(html)
    html = replace_external_links(html)
    html = replace_additional_costs(html)
    html = replace_footer(html)

    if html != original:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return True
    return False


def main():
    files = collect_article_files()
    updated = 0
    for path in files:
        relpath = os.path.relpath(path, ROOT)
        if update_file(path):
            updated += 1
            print(f"  updated: {relpath}")
        else:
            print(f"  skipped: {relpath} (no changes)")
    print(f"\n{updated}/{len(files)} files updated.")


if __name__ == "__main__":
    main()
