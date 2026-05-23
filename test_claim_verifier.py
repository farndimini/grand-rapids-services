"""
Tests for claim_verifier.py — no network required.
"""
import sys, re
sys.path.insert(0, '.')
from claim_verifier import ClaimExtractor, VerificationEngine, ConfidenceScorer, SERPConsensusLayer, verify_article

print("=== ClaimExtractor ===")
html = """<html><body>
<h1>Best tool 2026</h1>
<p>The product costs $29.99/month and has a 4.5/10 rating.</p>
<p>After two weeks of testing, we found it delivers 50% faster performance.</p>
<p>Tool X is better than Tool Y for most users.</p>
<p>It features 24GB RAM and 512GB storage.</p>
</body></html>"""

cx = ClaimExtractor()
claims = cx.extract(html)
assert len(claims) > 0, "No claims extracted"
types = [c["type"] for c in claims]
assert "price" in types, "Price claim not found"
assert "metric" in types, "Metric claim not found"
assert "rating" in types, "Rating claim not found"
assert "experience_claim" in types, "Experience claim not found"
assert "comparison" in types, "Comparison claim not found"
print(f"  Extracted {len(claims)} claims: {types}")

print("\n=== ConfidenceScorer ===")
scorer = ConfidenceScorer()
# Fabricated experience should score low
fake_claim = {"type": "experience_claim", "value": "After two weeks of testing", "text": "After two weeks of testing we found it delivers"}
fake_score = scorer.score(fake_claim)
assert fake_score < 0.5, f"Fake claim score too high: {fake_score}"
print(f"  Fabricated experience confidence: {fake_score:.2f} (should be low)")

# Claim with source should score high
sourced_claim = {"type": "price", "value": "$29.99/month", "text": "According to the official website, the product costs $29.99/month"}
sourced_score = scorer.score(sourced_claim, serp_data=["$29.99/month", "pricing starts at $29.99"])
assert sourced_score >= 0.75, f"Sourced claim score too low: {sourced_score}"
print(f"  Sourced claim confidence: {sourced_score:.2f} (should be high)")

print("\n=== VerificationEngine ===")
engine = VerificationEngine()
serp = ["$29.99/month official pricing", "starting at $29.99 per month", "4.5/10 user rating"]
verified = engine.verify(claims, serp_data=serp)
rejected = [c for c in verified if c.get("status") == "rejected"]
verified_ok = [c for c in verified if c.get("status") == "verified"]
print(f"  Rejected: {len(rejected)}, Verified: {len(verified_ok)}, Total: {len(verified)}")
assert len(rejected) >= 1, "Should reject fabricated experience"

print("\n=== SERPConsensusLayer ===")
cons = SERPConsensusLayer()
results = cons.check(verified, serp)
supported = [r for r in results if r.get("consensus") == "supported"]
print(f"  Supported by SERP: {len(supported)}/{len(results)}")

print("\n=== verify_article integrated ===")
report = verify_article(html, serp_texts=serp)
print(f"  Score: {report['score']}/100")
print(f"  Total claims: {report['total_claims']}")
print(f"  Verified: {report['verified_count']}")
print(f"  Rejected: {report['rejected_count']}")
print(f"  Issues: {report['issues']}")
assert report["total_claims"] > 0
assert report["rejected_count"] >= 1  # "After two weeks of testing"

print("\n=== Clean article passes ===")
clean_html = """<html><body>
<h1>Best password manager 2026</h1>
<p>According to industry reviews, leading password managers range from $3-$15/month.</p>
<p>Most experts recommend 1Password or Bitwarden for different use cases.</p>
<p>Reportedly, enterprise features vary significantly by provider.</p>
</body></html>"""
clean_report = verify_article(clean_html)
print(f"  Score: {clean_report['score']}/100")
print(f"  Total claims: {clean_report['total_claims']}")
print(f"  Rejected: {clean_report['rejected_count']}")
print(f"  Issues: {clean_report['issues']}")

print("\n✅ ALL CLAIM VERIFIER TESTS PASSED")
