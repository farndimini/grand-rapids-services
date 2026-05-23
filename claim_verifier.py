"""
claim_verifier.py — Autonomous Editorial Intelligence
====================================================
Runtime components for the nuclear constitution:
- ClaimExtractor: extract claims, numbers, comparisons from article HTML
- VerificationEngine: verify claims against SERP data and memory
- ConfidenceScorer: score confidence per claim
- SERPConsensusLayer: compare claims against SERP consensus
- verify_article: integrated pipeline for write_article()
"""

import re
import json
import logging
from typing import Any

from system_hardening import get_claim_auditor, ClaimLineage

log = logging.getLogger("claim_verifier")


class ClaimExtractor:
    """Extract factual claims from article HTML."""

    def extract(self, article: str) -> list[dict[str, Any]]:
        claims: list[dict[str, Any]] = []
        text = re.sub(r'<[^>]+>', ' ', article)
        text = re.sub(r'\s+', ' ', text).strip()

        # 1. Numerical claims ($X, X%, X hours, X days, X months)
        for m in re.finditer(r'\$[\d,]+(?:\.\d+)?(?:\s*/\s*(?:month|yr|year|user|seat|mo))?', text):
            claims.append({
                "type": "price",
                "value": m.group(0),
                "text": text[max(0, m.start()-60):m.end()+60],
                "position": m.start(),
            })
        for m in re.finditer(r'(\d+[.,]?\d*)\s*(%|hours?|days?|weeks?|months?|years?|gb|mb|tb|gbps|mbps|stars?|rating)', text, re.I):
            claims.append({
                "type": "metric",
                "value": m.group(0),
                "text": text[max(0, m.start()-60):m.end()+60],
                "position": m.start(),
            })
        for m in re.finditer(r'(\d+[.,]?\d*)\s*/\s*10', text):
            claims.append({
                "type": "rating",
                "value": m.group(0),
                "text": text[max(0, m.start()-60):m.end()+60],
                "position": m.start(),
            })

        # 2. Forbidden experience phrases
        for pat in [r'\bwe tested\b', r'\bafter testing\b', r'\bhands-on\b',
                     r'\bour benchmarks\b', r'\bwe measured\b', r'\bour results showed\b',
                     r'\bafter (two|three|four|five|six|one|\d+) (weeks?|days?|months?) of testing\b']:
            for m in re.finditer(pat, text, re.I):
                claims.append({
                    "type": "experience_claim",
                    "value": m.group(0),
                    "text": text[max(0, m.start()-80):m.end()+80],
                    "position": m.start(),
                })

        # 3. Comparison assertions (X is better than Y, X > Y)
        for m in re.finditer(r'(\w+(?:\s+\w+){0,3})\s+is\s+(better|worse|faster|slower|cheaper|more expensive|more reliable)\s+than\s+(\w+(?:\s+\w+){0,3})', text, re.I):
            claims.append({
                "type": "comparison",
                "value": m.group(0),
                "text": text[max(0, m.start()-40):m.end()+40],
                "position": m.start(),
            })

        # 4. Product assertions (X costs Y, X has Z)
        for m in re.finditer(r'([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,3})\s+(costs?|priced? at|offers?|provides?|delivers?|features?|includes?|supports?|handles?|processes?)', text):
            claims.append({
                "type": "product_assertion",
                "value": m.group(0)[:100],
                "text": text[max(0, m.start()-40):m.end()+60],
                "position": m.start(),
            })

        return claims


class ConfidenceScorer:
    """Score confidence for each claim based on evidence availability.
    
    Uses source diversity weighting, contradiction severity, and confidence decay.
    """

    def score(self, claim: dict[str, Any], serp_data: list[str] | None = None,
              memory_data: list[str] | None = None) -> float:
        base = 0.5
        text_lower = claim.get("text", "").lower()

        # Boost if explicit source is mentioned
        if re.search(r'(according to|source:|reported by|study by|research from|data from)', text_lower):
            base += 0.25
        # Boost if [VERIFY] is already present (author was careful)
        if '[verify' in text_lower:
            base += 0.1
        # Boost if uncertainty language is already used
        if re.search(r'\b(reportedly|typically|may|can|varies|approximately|roughly|around|about)\b', text_lower):
            base += 0.1

        # Penalize fabricated experience claims
        if claim.get("type") == "experience_claim":
            base -= 0.3

        # SERP consensus boost with source diversity weighting
        if serp_data:
            val_lower = claim.get("value", "").lower()
            supporting = [s for s in serp_data if val_lower in s.lower()]
            match_count = len(supporting)
            if match_count >= 3:
                base += 0.25  # higher boost for diverse sources
            elif match_count >= 2:
                base += 0.2
            elif match_count == 1:
                base += 0.05
            elif match_count == 0:
                base -= 0.15

        # Memory consistency boost
        if memory_data:
            mem_match = sum(1 for m in memory_data if claim.get("value", "").lower() in m.lower())
            if mem_match >= 1:
                base += 0.15

        # Apply confidence decay via claim auditor
        auditor = get_claim_auditor()
        base = auditor.confidence_decay(
            base_confidence=base,
            source_diversity=len(serp_data) if serp_data else 0,
            contradiction_count=0,
        )

        return max(0.0, min(1.0, base))


class VerificationEngine:
    """Verify claims against available sources."""

    def verify(self, claims: list[dict[str, Any]],
               serp_data: list[str] | None = None,
               memory_data: list[str] | None = None) -> list[dict[str, Any]]:
        scorer = ConfidenceScorer()
        auditor = get_claim_auditor()
        verified: list[dict[str, Any]] = []
        for c in claims:
            c["confidence"] = scorer.score(c, serp_data, memory_data)
            c["status"] = "verified" if c["confidence"] >= 0.75 else "unverified"
            if c["type"] == "experience_claim" and c["confidence"] < 0.4:
                c["status"] = "rejected"
                c["action"] = "remove"
            elif c["confidence"] < 0.5:
                c["action"] = "downgrade_confidence"
            elif c["confidence"] < 0.75:
                c["action"] = "add_uncertainty"
            else:
                c["action"] = "keep"
            # Record claim lineage telemetry
            text = c.get("text", "")
            is_superlative = bool(re.search(r'\b(best|worst|greatest|leading|ultimate|perfect)\b', text, re.I))
            is_comparative = bool(re.search(r'\b(better|worse|faster|cheaper)\b', text, re.I))
            auditor.record_lineage(ClaimLineage(
                claim_text=text[:100],
                claim_type=c.get("type", "unknown"),
                source="extracted",
                confidence_before=0.5,
                confidence_after=c["confidence"],
                action_taken=c.get("action", "unknown"),
                supporting_sources=0,
                contradicting_sources=0,
                is_superlative=is_superlative,
                is_comparative=is_comparative,
            ))
            verified.append(c)
        return verified


class SERPConsensusLayer:
    """Compare claims against SERP data for consensus checking."""

    def check(self, claims: list[dict[str, Any]], serp_texts: list[str]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for c in claims:
            val = c.get("value", "").lower()
            supporting = [s for s in serp_texts if val in s.lower()]
            contradicting = [s for s in serp_texts if self._contradicts(c, s)]
            results.append({
                "claim": c,
                "supporting_sources": len(supporting),
                "contradicting_sources": len(contradicting),
                "consensus": "supported" if len(supporting) >= 2 else (
                    "contradicted" if len(contradicting) > len(supporting) else "unknown"),
            })
        return results

    @staticmethod
    def _contradicts(claim: dict[str, Any], serp_text: str) -> bool:
        val = claim.get("value", "")
        if not val:
            return False
        # Check for negation patterns near the claim value
        negations = ["not", "no", "never", "cannot", "can't", "doesn't", "does not",
                     "isn't", "is not", "aren't", "are not", "won't", "will not",
                     "contrary", "misleading", "exaggerated", "actually", "but"]
        idx = serp_text.lower().find(val.lower())
        if idx < 0:
            return False
        before = serp_text[max(0, idx-80):idx]
        return any(n in before.lower() for n in negations)


def verify_article(article: str, serp_texts: list[str] | None = None,
                   memory_entries: list[str] | None = None) -> dict[str, Any]:
    """
    Full verification pipeline for an article.
    Returns report with: claims, verified, consensus, score, issues.
    """
    extractor = ClaimExtractor()
    engine = VerificationEngine()
    consensus = SERPConsensusLayer()

    claims = extractor.extract(article)
    verified = engine.verify(claims, serp_texts, memory_entries)
    consensus_results = consensus.check(verified, serp_texts or [])

    rejected = [c for c in verified if c.get("status") == "rejected"]
    unverified = [c for c in verified if c.get("status") == "unverified"]
    low_conf = [c for c in verified if c.get("confidence", 1.0) < 0.75]

    score = 100
    issues = []
    if rejected:
        score -= len(rejected) * 25
        issues.append(f"REJECTED_CLAIMS: {len(rejected)} fabricated experience claims found")
    if unverified:
        score -= len(unverified) * 10
        issues.append(f"UNVERIFIED_CLAIMS: {len(unverified)} claims without source verification")
    if low_conf:
        score -= len(low_conf) * 5
        issues.append(f"LOW_CONFIDENCE: {len(low_conf)} claims below confidence threshold")

    contradicted = [r for r in consensus_results if r.get("consensus") == "contradicted"]
    if contradicted:
        score -= len(contradicted) * 15
        issues.append(f"CONTRADICTED: {len(contradicted)} claims contradict SERP consensus")

    return {
        "score": max(0, score),
        "total_claims": len(claims),
        "verified_count": len([c for c in verified if c.get("status") == "verified"]),
        "rejected_count": len(rejected),
        "unverified_count": len(unverified),
        "low_confidence_count": len(low_conf),
        "contradicted_count": len(contradicted),
        "issues": issues,
        "claims": verified,
        "consensus": consensus_results,
    }
