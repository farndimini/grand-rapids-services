#!/usr/bin/env python3
"""
AI Content Generator for الوكيل Financial Blog
Follows EXACT article format from existing data.js articles
"""
import urllib.request, json, sys, os, time, re
from datetime import datetime

API_KEY = "sk-98sclqUBITjMyC5a8rjgRs6Hv9IObtLqn080K7lCa80OTVwX"
API_URL = "https://api.bluesminds.com/v1/chat/completions"

EXISTING_SLUGS = [
    "how-to-save-money-from-salary","best-way-to-divide-monthly-salary",
    "how-to-get-out-of-debt","financial-mistakes-young-people-make",
    "how-to-save-1000-dollars-in-a-year","how-to-start-a-personal-budget",
    "best-money-management-apps","how-to-control-daily-expenses",
    "saving-vs-investing-differences","how-to-build-an-emergency-fund"
]

def slugify(text):
    s = text.lower().replace(" ", "-").replace("$", "dollars").replace("%", "percent")
    s = re.sub(r'[^a-z0-9\-]', '', s)
    s = re.sub(r'-+', '-', s)
    return s.strip('-')

def generate_article(topic, category="general"):
    # Variables for the CTA based on category
    cta_actions = {
        "saving": ("Start Saving Today", "Start Saving"),
        "budget": ("Start Budgeting Now", "Start Budgeting Free"),
        "debt": ("Start Your Debt Plan", "Create Your Plan"),
        "investment": ("Optimize Your Budget", "Start Investing"),
        "general": ("Take Control Now", "Use Budget Manager"),
    }
    cta_title, cta_btn = cta_actions.get(category.lower(), ("Take Control Now", "Use Budget Manager"))

    system_prompt = f"""You are a professional financial content writer for a personal finance website called الوكيل.
Write in clear, friendly, practical English. Target: beginners.

IMPORTANT FORMAT RULES — follow EXACTLY:
1. Start with: <p class="lead">...</p>
2. NO <h1> tag — title is in JS, not content
3. Tables wrapped: <div class="table-wrap"><table>...</table></div>
4. Tips use: <div class="tip-callout"><strong>Pro Tip:</strong> OR <strong>Key Insight:</strong> OR <strong>Psychology Hack:</strong> etc.</div>
5. CTA box MUST use EXACTLY this format (replace text as needed):
   <div class="cta-box"><p><strong>{cta_title}</strong> Your call-to-action message here.</p><a href="#budget" class="btn btn-primary btn-sm" data-nav><i class="fas fa-calculator"></i> {cta_btn}</a></div>
6. Use <strong> for emphasis, NOT <b>
7. Include specific dollar amounts, percentages, and practical numbers
8. Keep paragraphs short (2-3 sentences)
9. Return ONLY the HTML content — no markdown fences, no extra text"""

    user_prompt = f"""Write a complete article about: "{topic}"

Requirements:
- 400-700 words
- Start with <p class="lead">...</p>
- Use <h2> for sections (NO h1 tag)
- At least one table wrapped in <div class="table-wrap"><table>...</table></div>
- Include <div class="tip-callout"> with a strong label
- End with a <div class="cta-box"> matching the EXACT format shown
- Include practical dollar amounts and percentages
- Write for beginners — no jargon without explanation

Return ONLY the HTML, no markdown."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    models = ["openai/gpt-4.1-mini", "gpt-3.5-turbo-0613", "multi-model"]
    last_error = None

    for model in models:
        try:
            print(f"  → {model}...", end=" ", flush=True)
            payload = json.dumps({"model": model, "messages": messages, "max_tokens": 2000, "temperature": 0.7}).encode()
            req = urllib.request.Request(API_URL, data=payload, headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                result = json.loads(resp.read().decode())
            try:
                content = result["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError, TypeError) as e:
                print(f"unexpected API response structure: {e}")
                last_error = f"API returned unexpected JSON: {e}"
                time.sleep(2)
                continue
            model_used = result.get("model", model)

            # Clean markdown fences
            if content.startswith("```"):
                content = re.sub(r'^```[\w]*\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            content = content.strip()

            # Remove html wrapper
            content = re.sub(r'<!DOCTYPE[^>]*>', '', content, flags=re.I)
            content = re.sub(r'<html[^>]*>', '', content, flags=re.I)
            content = re.sub(r'</html>', '', content, flags=re.I)
            content = re.sub(r'<head>.*?</head>', '', content, flags=re.I|re.S)
            content = re.sub(r'<body[^>]*>', '', content, flags=re.I)
            content = re.sub(r'</body>', '', content, flags=re.I)
            # Remove any <h1> tags (title comes from JS object)
            content = re.sub(r'<h1>.*?</h1>\s*', '', content, flags=re.I|re.S)
            content = content.strip()

            # Ensure starts with <p class="lead">
            if not content.startswith("<p"):
                content = f'<p class="lead">A practical guide to help you take control of your finances.</p>\n{content}'

            words = len(content.split())
            if words < 150:
                print(f"only {words} words, next...")
                time.sleep(2)
                continue

            # Ensure cta-box exists
            if 'cta-box' not in content:
                content += f'\n<div class="cta-box"><p><strong>{cta_title}</strong> Use our Budget Manager to apply what you have learned today.</p><a href="#budget" class="btn btn-primary btn-sm" data-nav><i class="fas fa-calculator"></i> {cta_btn}</a></div>'

            print(f"{words} words ✓")
            return {"title": topic, "category": category, "html": content, "words": words, "model": model_used, "slug": slugify(topic)}

        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            print(f"HTTP {e.code}: {err_body[:120]}")
            last_error = f"HTTP {e.code}: {err_body[:200]}"
            time.sleep(2)
        except urllib.error.URLError as e:
            print(f"connection failed: {e.reason}")
            last_error = f"Connection failed: {e.reason}"
            time.sleep(2)
        except Exception as e:
            print(f"failed: {type(e).__name__}: {str(e)[:120]}")
            last_error = f"{type(e).__name__}: {str(e)[:200]}"
            time.sleep(2)

    return {"error": f"All failed: {last_error}"}

def main():
    # 10 topics matching the same categories as existing
    topics = [
        ("How to Save Money on Groceries Every Month", "saving"),
        ("The Best Budgeting Apps of 2026 Compared", "budget"),
        ("Debt Snowball vs Avalanche: Which is Faster?", "debt"),
        ("Index Funds vs ETFs: What's the Difference?", "investment"),
        ("How to Negotiate Your Credit Card Interest Rate", "debt"),
        ("10 Side Hustles That Pay $500+ Per Month", "general"),
        ("How to Teach Your Kids About Money", "general"),
        ("Rent or Buy: The Financial Decision Guide", "budget"),
        ("How Much Should You Spend on a Car?", "budget"),
        ("Tax-Saving Strategies for Freelancers", "saving"),
    ]

    if len(sys.argv) > 1:
        topics = []
        args = sys.argv[1:]
        for arg in args:
            if "--" in arg:
                t, c = arg.split("--", 1)
                topics.append((t.strip(), c.strip().lower()))
            else:
                topics.append((arg.strip(), "general"))

    output_dir = "generated_articles"
    os.makedirs(output_dir, exist_ok=True)

    js_entries = []
    print(f"\n{'='*55}")
    print(f"  الوكيل — Content Generator ({len(topics)} articles)")
    print(f"  Format: exact match to data.js existing articles")
    print(f"{'='*55}\n")

    for i, (topic, category) in enumerate(topics, 1):
        print(f"[{i}/{len(topics)}] {topic}")
        article = generate_article(topic, category)

        if "error" in article:
            print(f"  ✗ SKIPPED: {article['error']}\n")
            continue

        slug = article["slug"]
        # Ensure unique slug
        if slug in EXISTING_SLUGS:
            slug = f"{slug}-guide"
        article["slug"] = slug

        # Save preview HTML
        preview_path = os.path.join(output_dir, f"{slug}.html")
        try:
            preview_html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{topic} - Preview</title>
<style>
  body {{ max-width: 800px; margin: 2rem auto; padding: 1rem; font-family: system-ui, sans-serif; background: #0f0f1a; color: #e2e8f0; line-height: 1.7; }}
  h1 {{ color: #3b82f6; }} h2 {{ color: #94a3b8; margin-top: 2rem; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
  th, td {{ border: 1px solid #334155; padding: 0.75rem; text-align: left; }}
  th {{ background: #1e293b; }}
  .tip-callout {{ background: linear-gradient(135deg, #1e293b, #1a1a3e); padding: 1.5rem; border-radius: 12px; margin: 1.5rem 0; border-left: 4px solid #3b82f6; }}
  .cta-box {{ background: #1e293b; border: 1px solid #3b82f6; padding: 2rem; border-radius: 12px; text-align: center; margin: 2rem 0; }}
  .table-wrap {{ overflow-x: auto; margin: 1rem 0; }}
  .btn {{ display: inline-block; background: linear-gradient(135deg, #3b82f6, #8b5cf6); color: white; padding: 0.5rem 1.2rem; border-radius: 8px; text-decoration: none; }}
  .btn-primary {{ background: linear-gradient(135deg, #3b82f6, #8b5cf6); }}
  .btn-sm {{ font-size: 0.9rem; padding: 0.4rem 1rem; }}
</style>
</head>
<body>
  <h1>Preview: {topic}</h1>
  <p>Category: {category} | Words: {article['words']} | Model: {article['model']}</p>
  <hr style="border-color:#334155">
  {article['html']}
</body>
</html>"""
            with open(preview_path, "w", encoding="utf-8") as f:
                f.write(preview_html)
            print(f"  📄 Preview saved")
        except OSError as e:
            print(f"  ⚠ Failed to save preview: {e}")

        # Build JS entry (escape backticks and ${} for template literal)
        html_content = article["html"]
        html_content = html_content.replace("\\", "\\\\")
        html_content = html_content.replace("`", "\\`")
        html_content = html_content.replace("${", "\\${")

        js_entry = f"""  {{
    slug: '{slug}',
    category: '{category}',
    title: '{article["title"]}',
    excerpt: 'A practical guide to {topic.lower()}.',
    content: `{html_content}`
  }},"""
        js_entries.append(js_entry)

        # Save JS file
        js_path = os.path.join(output_dir, "articles_data.js")
        try:
            with open(js_path, "w", encoding="utf-8") as f:
                f.write("// الوكيل — AUTO-GENERATED ARTICLES\n")
                f.write("// Paste these into data.js ARTICLES array (before the closing ])\n\n")
                f.write("const GENERATED_ARTICLES = [\n")
                f.write("\n".join(js_entries))
                f.write("\n];\n")
        except OSError as e:
            print(f"  ⚠ Failed to save JS data: {e}")

        print(f"  ✅ {article['words']} words\n")
        if i < len(topics):
            time.sleep(3)

    print(f"{'='*55}")
    print(f"  COMPLETE: {len(js_entries)}/{len(topics)} articles")
    print(f"  📁 Output: {output_dir}/articles_data.js")
    print(f"  📋 Open {output_dir}/*.html to preview each article")
    print(f"  📋 Paste articles_data.js entries into js/data.js ARTICLES array")
    print(f"{'='*55}")

if __name__ == "__main__":
    main()
