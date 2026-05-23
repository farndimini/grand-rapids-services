"""evidence_pack.py — Pre-Generation Evidence Extraction & Compression

Extracts structured, verifiable evidence from SERP crawl data BEFORE
generation. The LLM is instructed to USE ONLY the evidence pack,
dramatically reducing hallucination even with weaker models.

Flow:
  SERP crawl data → EvidenceExtractor → EvidencePack → compressed string → LLM prompt
"""

from __future__ import annotations
import json
import logging
import re
from collections import Counter
from datetime import datetime
from typing import Any

log = logging.getLogger("evidence_pack")

CURRENT_YEAR = 2026

# Patterns for extracting structured evidence from competitor text
PRICE_RX = re.compile(r'\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:-\s*\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?))?')
PERCENTAGE_RX = re.compile(r'(\d{1,3}(?:\.\d)?)\s*%')
YEAR_RX = re.compile(r'\b(?:19|20)[0-9]{2}\b')
RATING_RX = re.compile(r'(\d+(?:\.\d)?)\s*\/\s*10')
STAR_RX = re.compile(r'(\d+(?:\.\d)?)\s*[★☆]')
SPEC_RX = re.compile(r'(\d+)\s*(?:GB|TB|GHz|cores|threads|nm|W)\b', re.IGNORECASE)
PRODUCT_NAME_RX = re.compile(
    r'(MacBook\s*(?:Pro|Air)\s*\w*|ThinkPad\s*\w+|XPS\s*\d+|'
    r'Spectre\s*\w*|Gram\s*\d*|ZenBook\s*\w*|ROG\s*\w*|'
    r'Surface\s*(?:Laptop|Book|Pro)\s*\d*|Galaxy\s*Book\s*\w*|'
    r'Prestige\s*\w*|Serval\s*\w*)',
    re.IGNORECASE
)


class EvidenceExtractor:
    """Extract structured evidence from raw competitor article HTML/text."""

    def __init__(self):
        self._seen_claims: set[str] = set()

    def extract_from_competitors(self, competitors: list[dict]) -> dict[str, Any]:
        """Process a list of competitor analysis dicts into structured evidence."""
        all_prices: list[dict] = []
        all_percentages: list[dict] = []
        all_specs: list[dict] = []
        all_products: list[str] = []
        all_ratings: list[dict] = []
        all_years: list[int] = []
        all_claims: list[dict] = []
        domain_counts: Counter = Counter()

        for comp in competitors:
            text = comp.get("raw_text", comp.get("content", ""))
            url = comp.get("url", "")
            domain = self._extract_domain(url)
            if domain:
                domain_counts[domain] += 1

            # Extract prices
            for m in PRICE_RX.finditer(text):
                price = self._clean_price(m.group(0))
                if price and self._is_unique(f"price:{price}"):
                    all_prices.append({
                        "value": price,
                        "context": self._context(text, m.start(), 60),
                        "source": domain or url[:50],
                    })

            # Extract percentages
            for m in PERCENTAGE_RX.finditer(text):
                if self._is_unique(f"pct:{m.group(0)}"):
                    all_percentages.append({
                        "value": m.group(0),
                        "context": self._context(text, m.start(), 60),
                        "source": domain or url[:50],
                    })

            # Extract specs (GB, TB, GHz, cores)
            for m in SPEC_RX.finditer(text):
                key = f"spec:{m.group(0)}"
                if self._is_unique(key):
                    all_specs.append({
                        "value": m.group(0),
                        "context": self._context(text, m.start(), 40),
                        "source": domain or url[:50],
                    })

            # Extract product names
            for m in PRODUCT_NAME_RX.finditer(text):
                name = m.group(0).strip()
                if self._is_unique(f"product:{name.lower()}"):
                    all_products.append(name)

            # Extract ratings
            for m in RATING_RX.finditer(text):
                if self._is_unique(f"rating:{m.group(0)}"):
                    all_ratings.append({
                        "value": m.group(0),
                        "context": self._context(text, m.start(), 50),
                        "source": domain or url[:50],
                    })
            for m in STAR_RX.finditer(text):
                if self._is_unique(f"star:{m.group(0)}"):
                    all_ratings.append({
                        "value": f"{m.group(1)}/5",
                        "context": self._context(text, m.start(), 50),
                        "source": domain or url[:50],
                    })

            # Extract years
            for m in YEAR_RX.finditer(text):
                year = int(m.group(0))
                if CURRENT_YEAR - 5 <= year <= CURRENT_YEAR + 2:
                    if self._is_unique(f"year:{year}"):
                        all_years.append(year)

            # Extract explicit claim sentences (sentences with $, %, or "is")
            claim_sentences = self._extract_claim_sentences(text)
            for sentence in claim_sentences:
                key = f"claim:{hash(sentence)}"
                if self._is_unique(key):
                    all_claims.append({
                        "text": sentence[:200],
                        "source": domain or url[:50],
                    })

        # Deduplicate products (case-insensitive)
        all_products = list(dict.fromkeys(p.lower() for p in all_products))
        # Title-case them
        all_products = [p.title() for p in all_products]

        return {
            "products": all_products[:20],
            "prices": all_prices[:30],
            "percentages": all_percentages[:15],
            "specs": all_specs[:20],
            "ratings": all_ratings[:15],
            "years": sorted(set(all_years))[:10],
            "claims": all_claims[:20],
            "domain_count": len(domain_counts),
            "competitors_analyzed": len(competitors),
        }

    def build_evidence_prompt_block(self, evidence: dict[str, Any], keyword: str) -> str:
        """Compress evidence dict into a structured prompt injection block."""
        if not evidence or not evidence.get("products"):
            return ""

        lines = [
            "═══════════════════════════════════════════════════════════════",
            "EVIDENCE PACK — VERIFIED DATA FOR GENERATION",
            "═══════════════════════════════════════════════════════════════",
            f"Keyword: {keyword}",
            f"Competitors analyzed: {evidence.get('competitors_analyzed', 0)}",
            f"Unique domains: {evidence.get('domain_count', 0)}",
            "",
        ]

        # Products detected
        products = evidence.get("products", [])
        if products:
            lines.append("PRODUCTS MENTIONED BY COMPETITORS:")
            for p in products[:12]:
                lines.append(f"  • {p}")
            lines.append("")

        # Prices found
        prices = evidence.get("prices", [])
        if prices:
            lines.append("PRICES EXTRACTED FROM COMPETITOR CONTENT:")
            for p in prices[:10]:
                ctx = p.get("context", "")[:80]
                lines.append(f"  • {p['value']}  (context: \"{ctx}\")")
            lines.append("")

        # Specs found
        specs = evidence.get("specs", [])
        if specs:
            lines.append("SPECIFICATIONS FOUND:")
            for s in specs[:8]:
                ctx = s.get("context", "")[:60]
                lines.append(f"  • {s['value']}  ({ctx})")
            lines.append("")

        # Ratings
        ratings = evidence.get("ratings", [])
        if ratings:
            lines.append("RATINGS FOUND:")
            for r in ratings[:6]:
                ctx = r.get("context", "")[:60]
                lines.append(f"  • {r['value']}  ({ctx})")
            lines.append("")

        # Percentages
        percentages = evidence.get("percentages", [])
        if percentages:
            lines.append("STATISTICS/PERCENTAGES FOUND:")
            for p in percentages[:6]:
                ctx = p.get("context", "")[:60]
                lines.append(f"  • {p['value']}  ({ctx})")
            lines.append("")

        lines.append("HARD RULES:")
        lines.append("- You MUST prioritize evidence from this pack over your training data.")
        lines.append("- If a claim is NOT in the evidence pack, mark it [VERIFY] or remove it.")
        lines.append("- Do NOT fabricate prices, specs, or ratings not listed above.")
        lines.append("- If evidence is insufficient, acknowledge uncertainty.")
        lines.append("═══════════════════════════════════════════════════════════════\n")

        return "\n".join(lines)

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        m = re.match(r'https?://([^/]+)', url or '')
        return m.group(1) if m else ""

    def _clean_price(self, raw: str) -> str:
        """Normalize a price string."""
        raw = raw.replace(",", "")
        m = re.search(r'\$\s?(\d+(?:\.\d{2})?)', raw)
        if m:
            val = float(m.group(1))
            if 10 <= val <= 100000:
                return f"${val:,.0f}" if val >= 100 else f"${val:.2f}"
        return ""

    def _is_unique(self, key: str) -> bool:
        """Deduplicate evidence entries."""
        if key in self._seen_claims:
            return False
        self._seen_claims.add(key)
        return True

    def _context(self, text: str, pos: int, width: int = 50) -> str:
        """Extract surrounding context around a match."""
        start = max(0, pos - width)
        end = min(len(text), pos + width)
        ctx = text[start:end].replace("\n", " ").strip()
        if len(ctx) > width * 2:
            ctx = ctx[:width * 2] + "..."
        return ctx

    def _extract_claim_sentences(self, text: str) -> list[str]:
        """Extract sentences that look like factual claims."""
        sentences = re.split(r'[.!?]+', text)
        claim_sentences = []
        for s in sentences:
            s = s.strip()
            if not s or len(s) < 20:
                continue
            # Look for claim indicators
            if any(indicator in s.lower() for indicator in [
                "costs", "priced at", "starting at", "features a",
                "equipped with", " powered by ", " delivers ",
                " offers ", " includes ", " supports ",
                "weighs", "measures", "lasts up to",
            ]):
                if any(c in s for c in "0123456789"):
                    claim_sentences.append(s[:200])
        return claim_sentences[:20]


class RetrievalRanker:
    """Score and rank evidence chunks by relevance, freshness, and domain trust.

    Each evidence item gets a score (0-1). Top-K items are selected
    for the final evidence pack.
    """

    def __init__(self):
        # Domain trust scores (0.0 - 1.0)
        self._domain_trust: dict[str, float] = {
            "techradar.com": 0.85, "pcmag.com": 0.85, "tomshardware.com": 0.80,
            "anandtech.com": 0.85, "theverge.com": 0.75, "wired.com": 0.80,
            "arstechnica.com": 0.85, "notebookcheck.net": 0.80,
            "lenovo.com": 0.90, "dell.com": 0.90, "apple.com": 0.90,
            "samsung.com": 0.85, "asus.com": 0.85, "hp.com": 0.85,
            "amazon.com": 0.50, "wikipedia.org": 0.75,
            "reddit.com": 0.30, "youtube.com": 0.40,
        }
        self._default_trust = 0.50

    def rank_prices(self, prices: list[dict], keyword: str) -> list[dict]:
        """Rank price evidence by reasonability and source trust."""
        kw_lower = keyword.lower()
        for p in prices:
            score = 0.5
            # Prefer prices in reasonable ranges
            try:
                val = float(p.get("value", "$0").replace("$", "").replace(",", ""))
                if 100 <= val <= 10000:
                    score += 0.2
                if 300 <= val <= 5000:
                    score += 0.1
            except ValueError:
                pass
            # Boost if context contains keyword terms
            ctx = p.get("context", "").lower()
            if any(w in ctx for w in kw_lower.split()):
                score += 0.15
            # Boost by domain trust
            domain = self._extract_domain(p.get("source", ""))
            score += self._domain_trust.get(domain, self._default_trust) * 0.2
            p["_rank_score"] = min(1.0, score)
        prices.sort(key=lambda x: x.get("_rank_score", 0), reverse=True)
        return prices

    def rank_specs(self, specs: list[dict], keyword: str) -> list[dict]:
        """Rank spec evidence by specificity and keyword overlap."""
        kw_lower = keyword.lower()
        for s in specs:
            score = 0.5
            ctx = s.get("context", "").lower()
            if any(w in ctx for w in kw_lower.split()):
                score += 0.2
            # Prefer specific specs (GB, GHz, cores)
            val = s.get("value", "").lower()
            if any(u in val for u in ["gb", "tb", "ghz", "core"]):
                score += 0.15
            domain = self._extract_domain(s.get("source", ""))
            score += self._domain_trust.get(domain, self._default_trust) * 0.15
            s["_rank_score"] = min(1.0, score)
        specs.sort(key=lambda x: x.get("_rank_score", 0), reverse=True)
        return specs

    def rank_products(self, products: list[str], keyword: str) -> list[str]:
        """Rank product names by frequency and keyword overlap."""
        kw_lower = keyword.lower()
        scored = []
        for p in products:
            score = 0.5
            p_lower = p.lower()
            if any(w in p_lower for w in kw_lower.split()):
                score += 0.3
            scored.append((p, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in scored]

    def _extract_domain(self, source: str) -> str:
        m = re.match(r'https?://([^/]+)', source or "")
        return m.group(1) if m else ""


class EvidencePack:
    """High-level interface for evidence pack generation and injection."""

    def __init__(self):
        self._extractor = EvidenceExtractor()
        self._ranker = RetrievalRanker()

    def build(
        self,
        competitor_data: list[dict],
        keyword: str,
        serp_analysis: dict | None = None,
    ) -> dict[str, Any]:
        """Full pipeline: extract evidence from competitors, build pack."""
        evidence = self._extractor.extract_from_competitors(competitor_data)
        evidence["keyword"] = keyword
        evidence["generated_at"] = datetime.now().isoformat()

        # Merge in any structured SERP data
        if serp_analysis:
            evidence["serp_intent"] = serp_analysis.get("dominant_search_intent", "")
            evidence["serp_word_count_avg"] = serp_analysis.get("average_word_count", 0)
            evidence["serp_gaps"] = serp_analysis.get("content_gaps", [])[:5]

        return evidence

    def build_prompt_block(
        self,
        evidence: dict[str, Any],
        keyword: str,
    ) -> str:
        """Compress evidence into a prompt injection block."""
        return self._extractor.build_evidence_prompt_block(evidence, keyword)


# Module-level convenience
_shared_extractor = EvidenceExtractor()
_shared_pack = EvidencePack()


def extract_evidence(competitors: list[dict]) -> dict[str, Any]:
    return _shared_extractor.extract_from_competitors(competitors)


def build_evidence_prompt(evidence: dict[str, Any], keyword: str) -> str:
    return _shared_extractor.build_evidence_prompt_block(evidence, keyword)


def build_evidence_pack(
    competitor_data: list[dict],
    keyword: str,
    serp_analysis: dict | None = None,
) -> dict[str, Any]:
    return _shared_pack.build(competitor_data, keyword, serp_analysis)
