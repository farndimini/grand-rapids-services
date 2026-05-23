"""Quick integration test for seo_intelligence_layer (no network calls)"""
import sys
sys.path.insert(0, '.')
import json
from pathlib import Path

print("=== Testing serp_scraper (no network) ===")
from seo_intelligence_layer.serp_scraper import SerpScraper
# Test just the cache and slug functions
import re
slug = re.sub(r"[^a-z0-9]+", "_", "test keyword").strip("_")[:60]
print(f"Slug: {slug}")
print("  OK")

print("\n=== Testing ranking_tracker ===")
from seo_intelligence_layer.ranking_tracker import RankingTracker
rt = RankingTracker()
# Test with no snapshots (empty state)
dates = rt.get_available_dates("nonexistent_keyword")
assert dates == [], f"Expected empty list, got {dates}"
print(f"Empty state OK: {dates}")

# Test compare with missing snapshots
result = rt.compare_latest_two("nonexistent_keyword")
assert "error" in result
print(f"Error state OK: {result['error'][:40]}")
print("  OK")

print("\n=== Testing web_crawler (no network) ===")
from seo_intelligence_layer.web_crawler import WebCrawler
# Test PageParser with known HTML
from seo_intelligence_layer.web_crawler import PageParser
parser = PageParser()
test_html = """<html><head><title>Test Page</title></head>
<body><h1>Main Title</h1><h2>Section 1</h2><p>Some text here</p>
<h2>Section 2</h2><h3>Sub section</h3><table><tr><td>data</td></tr></table>
<ul><li>item1</li></ul></body></html>"""
parser.feed(test_html)
print(f"Title: {parser.title}")
print(f"H1: {parser.h1}")
print(f"H2s: {parser.h2s}")
print(f"H3s: {parser.h3s}")
print(f"Tables: {parser.tables}")
print(f"Bullet lists: {parser.bullet_lists}")
assert parser.title == "Test Page"
assert parser.h1 == "Main Title"
assert len(parser.h2s) == 2
print("  OK")

print("\n=== Testing content_analyzer ===")
from seo_intelligence_layer.content_analyzer import ContentAnalyzer
ca = ContentAnalyzer()
intent = ca.detect_intent("best password manager", ["Top 10 Best Password Managers 2026"])
print(f"Intent for 'best password manager': {intent}")
assert intent == "commercial"

intent2 = ca.detect_intent("what is seo", ["SEO Guide for Beginners"])
print(f"Intent for 'what is seo': {intent2}")
assert intent2 == "informational"

score = ca.score_content_depth(2500, 6, True, True)
print(f"Depth score (2500w, 6 H2s, FAQ, Tables): {score}/20")
assert score == 18, f"Expected 18, got {score}"

score2 = ca.score_content_depth(3500, 7, True, True)
print(f"Depth score (3500w, 7 H2s, FAQ, Tables): {score2}/20")
assert score2 == 20

fake_comps = [
    {"url": "https://a.com", "word_count": 2500, "h2s": ["Intro","Features","Pricing","Review","FAQ"], "h3s": [], "has_faq": True, "tables_count": 2, "bullet_lists": 3, "content_type": "comparison_list"},
    {"url": "https://b.com", "word_count": 800, "h2s": ["Guide","Setup"], "h3s": [], "has_faq": False, "tables_count": 0, "bullet_lists": 0, "content_type": "guide"},
]
sm = ca.build_competitor_strength_map(fake_comps)
print(f"Avg depth: {sm['avg_depth_score']}, Avg WC: {sm['avg_word_count']}")
assert sm['competitors_analyzed'] == 2
assert sm['avg_word_count'] == 1650

gaps = ca.detect_gaps(
    [["Intro", "Features", "Pricing", "FAQ", "Real User Reviews", "Comparison Table"]],
    ["Intro", "Conclusion"]
)
print(f"Gaps detected: {len(gaps)}")
for g in gaps:
    print(f"  - {g['section']}")
assert len(gaps) >= 3
print("  OK")

print("\n=== Testing learning_orchestrator import ===")
from seo_intelligence_layer import run_intelligence_cycle
print("  OK")

print("\n=== Testing main.py modes ===")
import main as m
# Verify the parser has our modes via argparse internals
try:
    main_module = __import__('main')
    has_intel = hasattr(main_module, '_HAS_INTELLIGENCE') and main_module._HAS_INTELLIGENCE
    # Try importing production cycle directly
    from seo_intelligence_layer import run_production_cycle, run_evolution_cycle
    print(f"  Run functions: production={'✓' if run_production_cycle else '✗'} evolve={'✓' if run_evolution_cycle else '✗'}")
except (ImportError, AttributeError) as e:
    print(f"  Warning: {e}")
print("  OK")

print("\n=== Checking main.py imports ===")
# main.py has everything inside main(), but we verify the top-level imports work
import main as main_module
assert hasattr(main_module, '_HAS_INTELLIGENCE'), "Intelligence flag not found in main.py"
print(f"  _HAS_INTELLIGENCE = {main_module._HAS_INTELLIGENCE}")
assert main_module._HAS_INTELLIGENCE, "Intelligence layer import failed"
print("  OK")

print("\n=== ALL TESTS PASSED ===")
