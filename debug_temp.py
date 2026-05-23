"""Debug temporal governor scanner failure."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["SEO_AGENT_TEST_MODE"] = "1"

from temporal_governor import StaleArticleScanner

scanner = StaleArticleScanner()

FRESH_ARTICLE = """
<h1>Best Laptops for Programming in 2026</h1>
<p>According to recent studies, the MacBook Pro is currently the top choice for developers in 2026.</p>
<p>The latest models start at approximately $2,499.</p>
<p>As of 2026, Apple M4 chip delivers about 25% better performance.</p>
<a href="https://apple.com">source</a>
"""

try:
    report = scanner.scan(FRESH_ARTICLE, "laptop 2026", "technology")
    print(f"Freshness: {report.overall_freshness}")
    print(f"Stale stats: {report.stale_statistics}")
    print(f"Old pricing: {report.old_pricing}")
    print(f"Expired claims: {len(report.expired_claims)}")
    print(f"Years found: {scanner.YEAR_RX.findall(FRESH_ARTICLE)}")
    # Check assertion
    assert isinstance(report, type(report))
    assert report.overall_freshness > 0.5, f"Freshness {report.overall_freshness} <= 0.5"
    print("ALL OK")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
