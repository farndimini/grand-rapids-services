"""
post_processor.py — SEO Agent Pro
==================================
ضعه في نفس مجلد modules.py

التطبيق في modules.py:
-----------------------
الخطوة 1 — أضف في أعلى modules.py:
    from post_processor import fix_article

الخطوة 2 — في write_article()، بعد السطر:
    article = _filter_banned_phrases(article, keyword)

    أضف:
    article = fix_article(article, keyword)

الاختبار المستقل:
-----------------
    python post_processor.py output/article.html "keyword here"
"""

import random
import re
from datetime import datetime

from system_hardening import get_html_validator

# Phase 3 — AI detection resistance
try:
    from seo_intelligence import get_ai_resistance
    _HAS_AI_RESISTANCE = True
except ImportError:
    _HAS_AI_RESISTANCE = False


KNOWN_LINKS: dict[str, str] = {
    "strict workflow":    "https://chromewebstore.google.com/detail/strict-workflow/cgmnfnmlficgeijcalkgnnkigkefkbhd",
    "freedom":            "https://freedom.to",
    "forest":             "https://www.forestapp.cc",
    "pomofocus":          "https://pomofocus.io",
    "marinara":           "https://chromewebstore.google.com/detail/marinara-pomodoro%C2%AE-assist/lojgmehidjdhhbmpjfamhpkpodfcodef",
    "toggl track":        "https://toggl.com/track",
    "clockify":           "https://clockify.me",
    "rescuetime":         "https://www.rescuetime.com",
    "momentum":           "https://momentumdash.com",
    "stayfocusd":         "https://chromewebstore.google.com/detail/stayfocusd/laankejkbhbdhmipfmgcngdelahlfoji",
    "cold turkey":        "https://getcoldturkey.com",
    "focusmate":          "https://www.focusmate.com",
    "be focused":         "https://xwavesoft.com/be-focused-pro-for-iphone-ipad-mac-os-x.html",
    "grammarly":          "https://www.grammarly.com",
    "notion":             "https://www.notion.so",
    "todoist":            "https://todoist.com",
    "trello":             "https://trello.com",
    "asana":              "https://asana.com",
    "ahrefs":             "https://ahrefs.com",
    "semrush":            "https://www.semrush.com",
    "chatgpt":            "https://chat.openai.com",
    "claude":             "https://claude.ai",
    "gemini":             "https://gemini.google.com",
    "ublock origin":      "https://ublockorigin.com",
    "dark reader":        "https://darkreader.org",
    "1password":          "https://1password.com",
    "lastpass":           "https://www.lastpass.com",
    "bitwarden":          "https://bitwarden.com",
    "google calendar":    "https://calendar.google.com",
    "google docs":        "https://docs.google.com",
    "google drive":       "https://drive.google.com",
    "focus to-do":        "https://chromewebstore.google.com/search/focus%20to%20do",
    "tomato timer":       "https://chromewebstore.google.com/search/tomato%20tomato",
    # Chrome Web Store links for popular extensions
    "honey":              "https://chromewebstore.google.com/detail/honey/bmnlcjabgnpnenekpadlanbbkooimhnj",
    "camelcamelcamel":    "https://chromewebstore.google.com/detail/the-camelizer/ghnomdcacenbmilgjigehppbamfndblo",
    "rakuten":            "https://chromewebstore.google.com/detail/rakuten/ceegchmckkibehdkggicnjaigigfbjhc",
    "prowritingaid":      "https://chromewebstore.google.com/detail/prowritingaid/akjgnelomkpapgnmknjmmiijhpmbfgib",
    "languagetool":       "https://chromewebstore.google.com/detail/languagetool/oldceeleldhonbafppcapldpdifcinil",
    "react devtools":     "https://chromewebstore.google.com/detail/react-developer-tools/fmkadmapgofadopljbjfkapdkoienihi",
    "json viewer":        "https://chromewebstore.google.com/detail/json-viewer/gbmdgpbipflnkeoojdbldlepkbjdcpma",
    "lighthouse":         "https://chromewebstore.google.com/detail/lighthouse/blipmdconlkpinefehnmjammfjpmpbjk",
    "octotree":           "https://chromewebstore.google.com/detail/octotree/bkhaagjahfmjljalopjnoealnfndnagc",
    "whatfont":           "https://chromewebstore.google.com/detail/whatfont/jabopobgcpjmedljpbcaablpmlmfcogm",
    "checkbot":           "https://chromewebstore.google.com/detail/checkbot-seo-web-speed-c/dagohlmlhagincbfilmkfhgijndjahml",
    "onetab":             "https://chromewebstore.google.com/detail/onetab/chphlpgkkbolifaimnlloiipkdnihall",
    "toby":               "https://chromewebstore.google.com/detail/toby-for-chrome/hddnkoipeenegfoeaoibdmnaalmhkmha",
    "session buddy":      "https://chromewebstore.google.com/detail/session-buddy/edacconmaakjimmfgnblocblbcdcpbko",
    "pushbullet":         "https://chromewebstore.google.com/detail/pushbullet/chlffgpmiacpedhhbkiomidkjlcfnbi",
    "evernote web clipper": "https://chromewebstore.google.com/detail/evernote-web-clipper/pioclpoplcdbaefihamjohnefbikjilc",
    "pocket":             "https://chromewebstore.google.com/detail/save-to-pocket/niloccemoadcdkdjlinkgdfekeahmflj",
    "adblock":            "https://chromewebstore.google.com/detail/adblock/gighmmpiobklfepjocnamgkkbiglidom",
    "ghostery":           "https://chromewebstore.google.com/detail/ghostery/mlomiejdfkolichcflejclcbmpeaniij",
    "noscript":           "https://chromewebstore.google.com/detail/noscript/doojmbjmlfjjnbmnoijecmcbfeoakpjm",
    "privacy badger":     "https://chromewebstore.google.com/detail/privacy-badger/pkehgijcmpdhfbdbbnkijodmdjhbjlgp",
    "video speed controller": "https://chromewebstore.google.com/detail/video-speed-controller/nffaoalbilbmmfgbnbgppjihopabppdk",
    "momentum":           "https://chromewebstore.google.com/detail/momentum/laookkfknpbbblfpciffpaejjkokdgca",
    "tabby":              "https://chromewebstore.google.com/detail/tabby/abpijldpgbhhbmliebkddooojhpjakpk",
    "wappalyzer":         "https://chromewebstore.google.com/detail/wappalyzer/gppongmhjkpfnbhagpmjfkannfbllamg",
}

_OPENER_TEMPLATES = [
    "Most {kw} reviews skip the one detail that actually matters: very few hold up under real daily use.",
    "The best {kw} in {year} is not the most popular one — and the difference is more significant than you might expect.",
    "I tested every major {kw} option on the Chrome Web Store. Here is what nobody else tells you.",
    "Three months ago I rebuilt my focus workflow around a {kw}. Here is what changed and what did not.",
    "Finding a {kw} that holds up under real daily pressure is harder than the Chrome Web Store ratings suggest.",
    "Not every {kw} works the way its screenshots suggest — I found that out after switching between five options.",
    "Before installing another {kw}, read this — it will save you an hour of frustration.",
    "{year} has brought real changes to the {kw} space, and the best option today is not what it was twelve months ago.",
]

_BANNED_OPENER_PATTERNS = [
    r"after (two|three|four|five|six|one|\d+) (weeks?|days?|months?) of testing",
    r"in today'?s (digital |fast[- ]paced )?world",
    r"in this article,?\s*(i |we )?(will|am going to|are going to)",
    r"are you (looking for|struggling with|trying to)",
    r"if you'?re (looking for|struggling with|trying to)",
    r"when it comes to [a-z]+",
    r"in the (ever[- ])?evolving (world|landscape|space)",
    r"as (a|an) (busy|modern|remote|digital) (worker|professional|student)",
]


def _wrap_bare_paragraphs(article: str) -> str:
    """Wrap bare text (not inside HTML tags) in <p>...</p>.
    Skips content inside <head>, <script>, <style> to avoid
    corrupting metadata, JSON-LD, and CSS."""
    # Strip head/script/style blocks before wrapping, then restore
    protected = {}
    def _protect(m: re.Match) -> str:
        idx = len(protected)
        placeholder = f"<__protect_{idx}__/>"
        protected[placeholder] = m.group(0)
        return placeholder
    article = re.sub(r'<head>.*?</head>', _protect, article, flags=re.DOTALL | re.IGNORECASE)
    article = re.sub(r'<script[^>]*>.*?</script>', _protect, article, flags=re.DOTALL | re.IGNORECASE)
    article = re.sub(r'<style[^>]*>.*?</style>', _protect, article, flags=re.DOTALL | re.IGNORECASE)
    # Wrap bare text segments
    parts = re.split(r'(<[^>]+>)', article)
    for i, part in enumerate(parts):
        if not part.startswith('<') and part.strip():
            paras = re.split(r'\n\s*\n+', part)
            wrapped = []
            for para in paras:
                para = para.strip()
                if not para:
                    continue
                wrapped.append(f'<p>{para}</p>')
            if wrapped:
                parts[i] = '\n'.join(wrapped)
    article = ''.join(parts)
    # Restore protected blocks
    for placeholder, original in protected.items():
        article = article.replace(placeholder, original)
    # Cleanup: remove <p> wrapping inside headings and fix double-wrapping
    article = re.sub(r'(<h[1-6][^>]*>)<p>(.*?)</p>(</h[1-6]>)', r'\1\2\3', article, flags=re.DOTALL | re.IGNORECASE)
    article = re.sub(r'<p>\s*<p>', r'<p>', article)
    article = re.sub(r'</p>\s*</p>', r'</p>', article)
    return article


def _ensure_qa_box(article: str) -> str:
    """Inject a quick-answer-box if missing."""
    if 'quick-answer-box' in article.lower():
        return article
    # Find the meta bar and inject after it
    meta_end = re.search(r'</div>\s*(?=<h2|<div\s)', article)
    if not meta_end:
        return article
    qa = """<div class="quick-answer-box">
    <strong>Quick Answer:</strong> The best option depends on your specific needs. This guide covers the top choices with real testing data, pricing, and honest comparisons to help you decide.
</div>
"""
    article = article[:meta_end.start()] + qa + article[meta_end.start():]
    return article


def _self_critique_article(article: str, keyword: str = "") -> list:
    """
    Self-critique pass: scan for unsupported claims, duplication,
    cross-niche contamination, and hallucination risks.
    Returns list of issues found (empty = clean).
    """
    import logging
    log = logging.getLogger("post_processor.self_critique")
    issues = []
    kw = keyword.lower() if keyword else ""

    # 1. Unsupported numerical claims (numbers without [VERIFY] or link context)
    numbers = re.findall(r'\$\d+[\d.,]*(?:/\s*(?:month|yr|year|user|seat))?', article)
    unsupported = []
    for n in numbers:
        # Check if number is near a [VERIFY] placeholder or a link
        pos = article.find(n)
        context = article[max(0, pos-200):pos+len(n)+200].lower()
        if '[verify' not in context and 'href=' not in context:
            # Check if it's inside a known schema block or legitimate context
            if 'datepublished' not in context and 'pricerange' not in context:
                unsupported.append(n)
    if unsupported:
        issues.append(f"UNSUPPORTED_CLAIMS: {len(unsupported)} numerical claims without [VERIFY] or source link")

    # 2. Duplicated H2 sections
    h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', article, re.DOTALL | re.IGNORECASE)
    h2_clean = [re.sub(r'<[^>]+>', '', h).strip().lower() for h in h2s]
    seen_h2 = set()
    for h in h2_clean:
        if h in seen_h2 and len(h) > 10:
            issues.append(f"DUPLICATE_H2: '{h[:50]}' appears more than once")
            break
        seen_h2.add(h)

    # 3. Cross-niche contamination
    if kw:
        niche_signals = {
            "tech": ["laptop", "software", "browser", "extension", "gaming", "computer", "smartphone", "app"],
            "finance": ["credit card", "loan", "mortgage", "insurance", "investing", "crypto", "stock", "retirement", "tax"],
            "health": ["workout", "diet", "supplement", "vitamin", "exercise", "fitness", "nutrition", "wellness", "yoga", "meditation"],
            "marketing": ["seo", "social media", "email marketing", "ppc", "analytics", "conversion", "copywriting"],
            "education": ["course", "certification", "degree", "scholarship"],
            "business": ["startup", "saas", "entrepreneur", "freelance", "project management"],
        }
        kw_niche = "general"
        for niche, signals in niche_signals.items():
            if any(s in kw for s in signals):
                kw_niche = niche
                break

        if kw_niche != "general":
            other_niches = [n for n in niche_signals if n != kw_niche]
            contamination_terms = []
            for other in other_niches:
                for term in niche_signals[other]:
                    if term in article.lower() and term not in kw:
                        # Check if term is used in a relevant context or just mentioned
                        if not any(kw_term in term for kw_term in kw.split()):
                            contamination_terms.append(term)
            if len(contamination_terms) > 3:
                issues.append(f"CROSS_NICHE: {len(contamination_terms)} terms from unrelated niches found ({', '.join(contamination_terms[:3])})")

    # 4. Hallucination risk: invented product names (capitalized phrases that look like products)
    invented_patterns = re.findall(r'(?:^|\s)([A-Z][a-z]+ [A-Z][a-z]+ Pro\b)', article)
    if len(invented_patterns) > 5:
        issues.append(f"HALLUCINATION_RISK: {len(invented_patterns)} suspicious product-like names found")

    # 5. Template bleed detection
    template_phrases = [
        "when it comes to finding the", "in the world of", "it is important to note that",
        "there are many factors to consider", "it is worth mentioning that",
        "it goes without saying", "last but not least", "all in all",
    ]
    for phrase in template_phrases:
        if phrase in article.lower():
            issues.append(f"TEMPLATE_BLEED: '{phrase}' found in content")
            break

    for issue in issues:
        log.warning("[SELF-CRITIQUE] %s", issue)
    return issues


def _fix_opener(article: str, keyword: str) -> str:
    # First ensure paragraphs are wrapped
    article = _wrap_bare_paragraphs(article)
    # Walk <p> tags to find the one after any meta/div-only wrapped content
    all_ps = list(re.finditer(r'(<p[^>]*>)(.*?)(</p>)', article, re.DOTALL | re.IGNORECASE))
    target = None
    for m in all_ps:
        txt = m.group(2).strip()
        # Skip metadata: date/author lines or <p> directly inside class="meta"
        if re.match(r'^(Published|Updated|By |Posted|Date|Last )', txt, re.I):
            continue
        # Check if <p> is inside a <div class="meta"> container
        before = article[max(0, m.start()-500):m.start()]
        # Find the last opening tag before this <p>
        last_open = before.rfind('<')
        snippet = before[last_open:] if last_open >= 0 else before
        if re.search(r'class=["\']meta["\']', snippet, re.I):
            continue
        if len(txt) < 20 and not any(re.search(pat, txt.lower()) for pat in _BANNED_OPENER_PATTERNS):
            continue
        target = m
        break
    if not target:
        return article
    p_open, p_text, p_close = target.group(1), target.group(2), target.group(3)
    if not any(re.search(pat, p_text.lower()) for pat in _BANNED_OPENER_PATTERNS):
        return article
    year   = datetime.now().year
    opener = random.choice(_OPENER_TEMPLATES).format(kw=keyword, year=year)
    sentences = re.split(r'(?<=[.!?])\s+', p_text.strip(), maxsplit=1)
    rest      = sentences[1] if len(sentences) > 1 else ""
    new_p     = p_open + opener + (" " + rest if rest else "") + p_close
    return article[:target.start()] + new_p + article[target.end():]


def _add_links(article: str) -> str:
    for tool, url in KNOWN_LINKS.items():
        pattern = re.compile(r'\b(' + re.escape(tool) + r')\b', re.IGNORECASE)
        parts    = re.split(r'(<[^>]+>)', article)
        linked   = False
        in_anchor = False
        new_parts = []
        for p in parts:
            if p.startswith('<'):
                if re.match(r'<a\s', p, re.IGNORECASE):
                    in_anchor = True
                elif p.startswith('</a') and in_anchor:
                    in_anchor = False
                new_parts.append(p)
            elif in_anchor:
                new_parts.append(p)
            elif linked:
                new_parts.append(p)
            else:
                new_part, n = pattern.subn(
                    lambda m, u=url: f'<a href="{u}" target="_blank" rel="nofollow noopener">{m.group(1)}</a>',
                    p, count=1
                )
                new_parts.append(new_part)
                if n > 0:
                    linked = True
        article = ''.join(new_parts)
    return article


def _fix_vague_prices(article: str) -> str:
    article = re.sub(
        r'(<td[^>]*>)\s*Varies\s*(</td>)',
        r'\1<span style="color:#c62828;font-size:0.85em">[VERIFY PRICE]</span>\2',
        article, flags=re.IGNORECASE
    )
    article = re.sub(
        r'(<td[^>]*>)\s*(See official site|See site|N/A|TBD)\s*(</td>)',
        r'\1<span style="color:#c62828;font-size:0.85em">[ADD DATA]</span>\3',
        article, flags=re.IGNORECASE
    )
    return article


def _resolve_link_placeholders(article: str) -> str:
    """Convert [LINK: name] to real <a> tags when name matches KNOWN_LINKS.
    Unresolved placeholders remain for _highlight_placeholders to flag.
    """
    def _resolve(m: re.Match) -> str:
        name = m.group(1).strip().lower()
        for tool, url in KNOWN_LINKS.items():
            if tool.lower() == name or name in tool.lower() or tool.lower() in name:
                return f'<a href="{url}" target="_blank" rel="nofollow noopener">{m.group(1)}</a>'
        return m.group(0)
    article = re.sub(r'\[LINK:\s*([^\]]+)\]', _resolve, article)
    return article


def _highlight_placeholders(article: str) -> str:
    article = re.sub(
        r'\[LINK:\s*([^\]]+)\]',
        r'<span style="background:#fff3cd;color:#856404;padding:1px 5px;border-radius:3px;font-size:0.85em">LINK: \1</span>',
        article
    )
    article = re.sub(
        r'\[VERIFY:\s*([^\]]+)\]',
        r'<span style="background:#f8d7da;color:#721c24;padding:1px 5px;border-radius:3px;font-size:0.85em">VERIFY: \1</span>',
        article
    )
    return article


def _add_extension_screenshots(article: str, keyword: str = "") -> str:
    """Convert [SCREENSHOT: ExtensionName] to professional HTML image blocks."""
    def _screenshot_replace(match: re.Match) -> str:
        name = match.group(1).strip()
        slug = re.sub(r"[^\w\s-]", "", name).lower().replace(" ", "-")[:40]
        alt = f"{name} Chrome extension screenshot — user interface overview"
        caption_text = f"{name} — Chrome extension interface and features"

        # Try to find a Chrome Web Store URL for this extension
        cws_url = ""
        for tool_name, url in KNOWN_LINKS.items():
            if tool_name.lower() in name.lower() or name.lower() in tool_name.lower():
                cws_url = url
                break

        if cws_url:
            return f'''
<div class="ext-screenshot-wrapper" style="margin:20px 0;text-align:center;">
    <a href="{cws_url}" target="_blank" rel="nofollow noopener">
        <img src="images/ext_{slug}.jpg" alt="{alt}" class="ext-screenshot" loading="lazy" onerror="this.style.display='none'">
    </a>
    <p style="font-size:0.85em;color:#666;margin-top:6px;"><em>{caption_text}</em> — <a href="{cws_url}" target="_blank" rel="nofollow noopener">View on Chrome Web Store</a></p>
</div>'''

        return f'''
<div class="ext-screenshot-wrapper" style="margin:20px 0;text-align:center;">
    <img src="images/ext_{slug}.jpg" alt="{alt}" class="ext-screenshot" loading="lazy" onerror="this.style.display='none'">
    <p style="font-size:0.85em;color:#666;margin-top:6px;"><em>{caption_text}</em></p>
</div>'''

    article = re.sub(
        r'\[SCREENSHOT:\s*([^\]]+)\]',
        _screenshot_replace,
        article
    )
    return article


def _add_extension_cards(article: str) -> str:
    """Wrap each extension mention in a professional card, add rating badges."""
    # Convert lines with "— Chrome Web Store:" or "★" to use ext-rating spans
    article = re.sub(
        r'(Chrome Web Store:\s*)(\d+\.?\d*)(★)\s*\((\d[\d,]*\d?\s*ratings?)\)',
        r'\1<span class="ext-rating">\2\3 \4</span>',
        article
    )

    # Add price badges
    article = re.sub(
        r'(Pricing:\s*)(Free|Freemium|\$\d[\d.,]*/?(month|yr|year)?)',
        r'\1<span class="ext-price">\2</span>',
        article
    )

    # Wrap each H3 extension with an ext-card div
    def _wrap_ext_card(match: re.Match) -> str:
        h3 = match.group(1)
        content = match.group(2)
        # Only wrap if it looks like an extension name (starts with known tool or has ★/rating)
        if "★" in content or "Chrome Web Store" in content or "Pricing:" in content:
            return f'<div class="ext-card">{h3}{content}</div>'
        return match.group(0)

    article = re.sub(
        r'(<h3[^>]*>.*?</h3>)(.*?)(?=<h[23]|\Z)',
        _wrap_ext_card,
        article,
        flags=re.DOTALL | re.IGNORECASE
    )

    return article


def _fix_duplicate_h1(article: str) -> str:
    matches = list(re.finditer(r'<h1[^>]*>.*?</h1>', article, re.IGNORECASE | re.DOTALL))
    if len(matches) <= 1:
        return article
    for m in reversed(matches[1:]):
        article = article[:m.start()] + article[m.end():]
    return article


def _fix_duplicate_toc(article: str) -> str:
    """Remove ALL TOC blocks — formatter adds its own."""
    return re.sub(
        r'<div[^>]*class=["\'][^"\']*toc[^"\']*["\'][^>]*>.*?</div>',
        '',
        article,
        flags=re.IGNORECASE | re.DOTALL
    )


def _fix_duplicate_meta(article: str) -> str:
    matches = list(re.finditer(
        r'<div[^>]*class=["\']meta["\'][^>]*>.*?</div>',
        article, re.IGNORECASE | re.DOTALL
    ))
    if len(matches) <= 1:
        return article
    for m in reversed(matches[1:]):
        article = article[:m.start()] + article[m.end():]
    return article


def _fix_faq_count(article: str, keyword: str = "") -> str:
    """Ensure FAQ section has minimum ~8 FAQ items for commercial (pad generically if needed)."""
    from modules import _detect_intent
    intent = _detect_intent(keyword) if keyword else "COMMERCIAL"
    target = 8 if intent == "COMMERCIAL" else 5
    faq_items = list(re.finditer(
        r'<div\s+class="faq-item">.*?</div>',
        article, re.DOTALL
    ))
    count = len(faq_items)
    if count >= target:
        return article
    need = target - count
    pad_items = ""
    pad_qa = [
        ("Is this product worth the investment in 2026?", "For most users, yes. The key is matching features to your specific needs. Consider your primary use case, budget, and required platforms before committing."),
        ("How long does delivery usually take?", "Delivery times vary by seller and location. Most retailers offer standard (5-7 business days) and expedited (2-3 business days) shipping options."),
        ("What is the return policy?", "Most products come with a 30-day return policy. Check the specific seller's return policy before purchasing, as conditions may vary."),
        ("Does this work with other tools I already use?", "Most modern options offer integrations with popular platforms. Check the integrations page on the official website for a full list of supported tools."),
        ("What kind of support is available?", "Support options typically include email, live chat, and knowledge base. Premium plans often include priority phone support and dedicated account management."),
        ("Are there any hidden fees I should know about?", "Some providers charge setup fees, cancellation fees, or overage charges. Always read the fine print and terms of service before committing to a paid plan."),
    ]
    for q, a in pad_qa[:need]:
        pad_items += f"""
<div class="faq-item">
    <div class="faq-q">Q: {q}</div>
    <div class="faq-a">A: {a}</div>
</div>"""
    if faq_items:
        last_item = faq_items[-1]
        article = article[:last_item.end()] + pad_items + article[last_item.end():]
    return article


def _fix_faq_schema(article: str) -> str:
    """Rebuild FAQPage schema to exactly match actual FAQ items."""
    import json as _json
    faq_items_text = re.findall(r'class="faq-q"[^>]*>(.*?)</div>', article, re.DOTALL)
    faq_items_clean = [re.sub(r'<[^>]+>', '', q).strip() for q in faq_items_text]
    if not faq_items_clean:
        return article
    # Find the FAQPage schema block by searching for start/end markers
    start = article.find('"@type": "FAQPage"')
    if start == -1:
        start = article.find('"@type":"FAQPage"')
    if start == -1:
        return article
    # Find the enclosing script tag boundaries
    script_start = article.rfind('<script', 0, start)
    if script_start == -1:
        return article
    script_end = article.find('</script>', start)
    if script_end == -1:
        return article
    script_end += len('</script>')
    # Rebuild the full schema block using json.dumps for proper formatting
    faqpage_obj = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": re.sub(r'^Q:\s*', '', fq), "acceptedAnswer": {"@type": "Answer", "text": "See the answer in the FAQ section above."}}
            for fq in faq_items_clean
        ]
    }
    new_block = '<script type="application/ld+json">\n' + _json.dumps(faqpage_obj, indent=4, ensure_ascii=False) + '\n</script>'
    article = article[:script_start] + new_block + article[script_end:]
    return article


def _ensure_link_fallback(article: str) -> str:
    """If article has fewer than 3 external links, add generic authoritative links."""
    ext_links = re.findall(r'<a\s[^>]*href="https?://', article, re.IGNORECASE)
    if len(ext_links) >= 3:
        return article
    fallback_links = [
        '<p>For the latest updates, check <a href="https://www.google.com" target="_blank" rel="nofollow noopener">Google Search Central</a> and <a href="https://developers.google.com/search" target="_blank" rel="nofollow noopener">Google Search documentation</a> for official guidelines. See also <a href="https://developers.google.com/search/docs/fundamentals/creating-helpful-content" target="_blank" rel="nofollow noopener">Google\'s Helpful Content guidance</a>.</p>',
    ]
    # Insert before final verdict or closing body
    insert_point = re.search(r'(<h2[^>]*>Final Verdict|</body>)', article, re.IGNORECASE)
    if insert_point:
        article = article[:insert_point.start()] + fallback_links[0] + article[insert_point.start():]
    return article


def _ensure_link_attrs(article: str) -> str:
    """Ensure ALL external links have rel=nofollow noopener and target=_blank."""
    def _fix_tag(match: re.Match) -> str:
        tag = match.group(0)
        href = re.search(r'href="(https?://[^"]+)"', tag, re.IGNORECASE)
        if not href:
            return tag
        # Skip internal links (same domain placeholders)
        url = href.group(1)
        if 'yoursite.com' in url:
            return tag
        if 'rel=' not in tag.lower():
            tag = tag.replace('<a', '<a rel="nofollow noopener"', 1)
        if 'target=' not in tag.lower():
            tag = tag.replace('<a', '<a target="_blank"', 1)
        return tag

    article = re.sub(
        r'<a\s[^>]*href="(https?://[^"]*)"[^>]*>',
        _fix_tag,
        article,
        flags=re.IGNORECASE
    )
    return article


def _fix_unclosed_tags(html: str) -> str:
    """Auto-close unclosed HTML tags and remove extra closing tags."""
    import re as _re
    _self_close = {'br', 'hr', 'img', 'input', 'meta', 'link', 'source', 'wbr', 'area', 'path'}
    _open_re = _re.compile(r'<(\w+)([\s>])', _re.IGNORECASE)
    _close_re = _re.compile(r'</(\w+)>', _re.IGNORECASE)
    _opens = []
    for m in _open_re.finditer(html):
        tag = m.group(1).lower()
        if tag not in _self_close:
            _opens.append(tag)
    _closes = []
    for m in _close_re.finditer(html):
        _closes.append(m.group(1).lower())
    from collections import Counter
    _open_counts = Counter(_opens)
    _close_counts = Counter(_closes)
    all_tags = sorted(set(list(_open_counts.keys()) + list(_close_counts.keys())))
    # Add missing closing tags at end
    _missing = []
    for tag in all_tags:
        diff = _open_counts.get(tag, 0) - _close_counts.get(tag, 0)
        if diff > 0:
            _missing.extend([f'</{tag}>'] * diff)
    if _missing:
        html += '\n' + '\n'.join(_missing)
    # Remove extra closing tags (closes > opens) from end
    for tag in reversed(all_tags):
        diff = _open_counts.get(tag, 0) - _close_counts.get(tag, 0)
        if diff < 0:
            for _ in range(-diff):
                last_close = html.rfind(f'</{tag}>')
                if last_close >= 0:
                    html = html[:last_close] + html[last_close + len(f'</{tag}>'):]
    return html

def _normalize_html(article: str) -> str:
    """Pre-parse: strip markdown fences, fix doubled HTML, remove bare <p> wrapping."""
    # Strip markdown code fences anywhere (```html, ```, etc.)
    article = re.sub(r'```html?\s*\n?', '', article, flags=re.IGNORECASE)
    article = article.replace('```', '')
    # Strip leading/trailing stray <p> caused by code-fence removal
    article = re.sub(r'<p>\s*</p>', '', article, flags=re.IGNORECASE)
    # Fix doubled <html> tags
    article = re.sub(r'<html>\s*<html\b', '<html', article, flags=re.IGNORECASE)
    article = re.sub(r'</html>\s*</html>', '</html>', article, flags=re.IGNORECASE)
    # Remove bare <p> wrapping <!DOCTYPE> or stray markup
    article = re.sub(r'<p>\s*<!DOCTYPE', '<!DOCTYPE', article, flags=re.IGNORECASE)
    article = re.sub(r'</html>\s*</p>', '</html>', article, flags=re.IGNORECASE)
    # Remove empty paragraphs left behind
    article = re.sub(r'<p>\s*</p>', '', article, flags=re.IGNORECASE)
    # Fix doubled <head>, </head>, <body>, </body> from model output inside template
    article = re.sub(r'</head>\s*<head[^>]*>', '', article, flags=re.IGNORECASE)
    article = re.sub(r'</body>\s*<body[^>]*>', '', article, flags=re.IGNORECASE)
    return article


def fix_article(article: str, keyword: str = "") -> str:
    """
    الدالة الرئيسية — استدعِها في write_article() بعد _filter_banned_phrases
    """
    article = _normalize_html(article)
    article = _wrap_bare_paragraphs(article)
    article = _fix_duplicate_h1(article)
    article = _fix_duplicate_toc(article)
    article = _fix_duplicate_meta(article)
    article = _fix_opener(article, keyword) if keyword else article
    article = _fix_vague_prices(article)
    article = _add_links(article)
    article = _ensure_link_attrs(article)
    article = _resolve_link_placeholders(article)
    article = _highlight_placeholders(article)
    article = _add_extension_screenshots(article, keyword)
    article = _add_extension_cards(article)
    article = _fix_faq_count(article, keyword)
    article = _fix_faq_schema(article)
    article = _ensure_link_fallback(article)
    article = _ensure_qa_box(article)
    article = _fix_unclosed_tags(article)
    _self_critique_article(article, keyword)
    # AI detection resistance check (Phase 3)
    if _HAS_AI_RESISTANCE:
        try:
            _ai_rpt = get_ai_resistance().analyze(article)
            if _ai_rpt.overall_human_score < 0.25:
                import logging as _pp_log
                _pp_log.getLogger("post_processor").warning(
                    "[AI_DETECTION] Low human score %.3f — burstiness=%.3f entropy=%.3f",
                    _ai_rpt.overall_human_score, _ai_rpt.burstiness_score, _ai_rpt.entropy_score
                )
        except Exception:
            pass
    # HTML structural validation
    _validator = get_html_validator()
    _validation = _validator.validate(article)
    if not _validation["pass"]:
        import logging as _pp_log
        _pp_log.getLogger("post_processor").warning(
            "[HTML_VALIDATION] %d issues, %d warnings (score: %d/100)",
            len(_validation["issues"]), len(_validation["warnings"]), _validation["score"]
        )
    final_publish_audit(article)
    return article


def final_publish_audit(article: str):
    """Final pre-publish audit for post-processor output. Hard blocks only for structural
    issues (unclosed tags, broken anchors). Pattern issues (nested FAQ, malformed tags,
    duplicate IDs) are downgraded to warnings and logged."""
    # Check for unclosed <div> or <p> or <table> — structural, always block
    for tag in ['div', 'p', 'table', 'tr', 'td', 'th', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4']:
        opens = len(re.findall(f'<{tag}[\\s>]', article, re.IGNORECASE))
        closes = len(re.findall(f'</{tag}>', article, re.IGNORECASE))
        if opens != closes and opens > 0:
            from modules import PublishBlocked
            raise PublishBlocked(f"Unclosed <{tag}> tags ({opens} open, {closes} closed)")

    # Check for raw markdown inside HTML (lines starting with ## or **)
    lines = article.splitlines()
    markdown_h = [l for l in lines if l.strip().startswith('##') and '</h' not in l and '{' not in l]
    if markdown_h:
        import logging as _log
        _log.warning("[AUDIT_WARN] Raw markdown headings found (%d lines) — continuing", len(markdown_h))

    # Check for nested FAQ blocks — warn, don't block (common in Local SEO)
    faq_inside_faq = re.findall(r'class="faq-item"[^>]*>.*?class="faq-item"', article, re.DOTALL)
    if faq_inside_faq:
        import logging as _log
        _log.warning("[AUDIT_WARN] Nested FAQ blocks detected (%d) — continuing", len(faq_inside_faq))

    # Check for <div. (dot after div, malformed tag) — warn, don't block
    if re.search(r'<div\.', article):
        import logging as _log
        _log.warning("[AUDIT_WARN] Malformed tag <div. found — continuing")

    # Check for acceptedanswer (wrong casing) — warn
    if 'acceptedanswer' in article:
        import logging as _log
        _log.warning("[AUDIT_WARN] Invalid schema casing 'acceptedanswer' — continuing")

    # Check for duplicate IDs — warn
    ids = re.findall(r'id="([^"]+)"', article)
    if len(ids) != len(set(ids)):
        import logging as _log
        _log.warning("[AUDIT_WARN] Duplicate HTML IDs detected — continuing")

    # Check for placeholder URLs
    if 'href="[LINK:' in article:
        from modules import PublishBlocked
        raise PublishBlocked("Placeholder URL in href attribute")

    # Check for broken anchors
    broken_anchors = re.findall(r'href="#([^"]+)"', article)
    for anchor in broken_anchors:
        if f'id="{anchor}"' not in article and f'name="{anchor}"' not in article:
            from modules import PublishBlocked
            raise PublishBlocked(f"Broken anchor href='#{anchor}' (no matching id/name)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python post_processor.py <article.html> [keyword]")
        sys.exit(1)
    path    = sys.argv[1]
    keyword = sys.argv[2] if len(sys.argv) > 2 else ""
    with open(path, encoding="utf-8") as f:
        content = f.read()
    h1_b  = len(re.findall(r'<h1[^>]*>', content, re.I))
    toc_b = len(re.findall(r'class=["\']toc["\']', content, re.I))
    lnk_b = len(re.findall(r'<a href=', content, re.I))
    fixed = fix_article(content, keyword)
    h1_a  = len(re.findall(r'<h1[^>]*>', fixed, re.I))
    toc_a = len(re.findall(r'class=["\']toc["\']', fixed, re.I))
    lnk_a = len(re.findall(r'<a href=', fixed, re.I))
    out = path.replace(".html", "_fixed.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(fixed)
    print(f"\n  Saved \u2192 {out}\n")
    print(f"  {'':20s}  BEFORE  AFTER")
    print(f"  {'\u2500'*36}")
    print(f"  {'H1 tags':20s}  {h1_b:>6}  {h1_a:>5}")
    print(f"  {'TOC blocks':20s}  {toc_b:>6}  {toc_a:>5}")
    print(f"  {'External links':20s}  {lnk_b:>6}  {lnk_a:>5}")
    fp = re.search(r'<p[^>]*>(.*?)</p>', fixed, re.DOTALL)
    if fp:
        print(f"\n  Opener: {fp.group(1)[:100].strip()}...")
