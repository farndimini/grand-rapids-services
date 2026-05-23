"""
adversarial_swarm.py — Multi-Agent Adversarial Review Swarm
=============================================================
Asynchronous multi-agent audit system where each agent independently
scores risk across a different dimension. Produces weighted consensus,
disagreement detection, and actionable recommendations.

Architecture:
  Agent 1 (HallucinationHunter)     → risk_score, findings
  Agent 2 (ContradictionHunter)     → risk_score, findings
  Agent 3 (CitationAuditor)         → risk_score, findings
  Agent 4 (SEOOverOptimizationDetector) → risk_score, findings
  Agent 5 (AIStyleDetector)         → risk_score, findings
  Agent 6 (LegalRiskAuditor)        → risk_score, findings
  Agent 7 (TemporalDecayAuditor)    → risk_score, findings
  Agent 8 (SchemaValidator)         → risk_score, findings
  Agent 9 (ManipulationDetector)    → risk_score, findings

  SwarmCoordinator → AdversarialReport
"""

from __future__ import annotations

import re
import json
import time
import math
import hashlib
import logging
from typing import Any, Optional, Callable
from dataclasses import dataclass, field

log = logging.getLogger("adversarial_swarm")


# ── Agent Result ───────────────────────────────────────────

@dataclass
class AgentResult:
    """Result from a single adversarial agent."""
    agent_name: str
    risk_score: float          # 0.0 (safe) to 1.0 (critical)
    critical: bool             # if True, triggers hard-fail
    findings: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.5   # how confident the agent is in its score
    duration_ms: float = 0.0
    agent_version: str = "1.0"

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "risk_score": self.risk_score,
            "critical": self.critical,
            "findings": list(self.findings),
            "evidence": list(self.evidence),
            "confidence": self.confidence,
            "duration_ms": self.duration_ms,
            "agent_version": self.agent_version,
        }


# ── Base Agent ─────────────────────────────────────────────

class BaseAdversarialAgent:
    """Base class for all adversarial agents."""

    def __init__(self, name: str, weight: float = 1.0):
        self.name = name
        self.weight = weight

    def audit(self, article: str, keyword: str, **kwargs) -> AgentResult:
        raise NotImplementedError

    def _check_banned(self, text: str, patterns: list[str]) -> list[str]:
        lower = text.lower()
        return [p for p in patterns if p in lower]


# ============================================================
# AGENT 1 — HallucinationHunter
# ============================================================

class HallucinationHunter(BaseAdversarialAgent):
    """Scores risk of hallucinated claims: unsupported prices,
    percentages, years, superlatives without sources."""

    UNCERTAINTY_WORDS = [
        "reportedly", "rumored", "not officially", "early leaks",
        "approximate", "approximately", "around", "about",
        "estimated", "typically", "may", "can", "varies",
        "suggest", "unconfirmed", "expected", "planned",
        "alleged", "unofficial",
    ]

    PRICE_RX = re.compile(r"\$[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?")
    PCT_RX = re.compile(r"\b[0-9]{1,3}%")
    YEAR_RX = re.compile(r"\b(19|20)[0-9]{2}\b")
    SUPERLATIVE_RX = re.compile(
        r"\b(best|worst|greatest|largest|smallest|fastest|slowest|"
        r"cheapest|most expensive|highest|lowest|top|leading|"
        r"ultimate|premier|always|never)\b", re.I
    )

    def __init__(self):
        super().__init__("HallucinationHunter", weight=1.2)

    def audit(self, article: str, keyword: str, **kwargs) -> AgentResult:
        start = time.time()
        findings = []
        evidence = []

        prices = self.PRICE_RX.findall(article)
        pcts = self.PCT_RX.findall(article)
        years = self.YEAR_RX.findall(article)
        superlatives = self.SUPERLATIVE_RX.findall(article)

        unsupported_prices = 0
        for p in prices:
            idx = article.index(p)
            ctx = article[max(0, idx-150):idx+len(p)+50].lower()
            if not any(w in ctx for w in self.UNCERTAINTY_WORDS):
                unsupported_prices += 1
                if unsupported_prices <= 3:
                    evidence.append(f"Unsupported price: '{p}' without qualifier")

        unsupported_pcts = 0
        for p in pcts[:10]:
            idx = article.index(p)
            ctx = article[max(0, idx-150):idx+len(p)+50].lower()
            if not any(w in ctx for w in self.UNCERTAINTY_WORDS):
                unsupported_pcts += 1
                if unsupported_pcts <= 3:
                    evidence.append(f"Unsupported percentage: '{p}' without source")

        if unsupported_prices > 3:
            findings.append(f"{unsupported_prices} unsupported price claims")

        if unsupported_pcts > 5:
            findings.append(f"{unsupported_pcts} unsupported percentage claims")

        if superlatives:
            unsupported_sup = 0
            for s in superlatives[:10]:
                idx = article.lower().index(s.lower())
                ctx = article[max(0, idx-150):idx+len(s)+50].lower()
                if not any(w in ctx for w in self.UNCERTAINTY_WORDS):
                    unsupported_sup += 1
            if unsupported_sup > 3:
                findings.append(f"{unsupported_sup} unsupported superlatives")
                evidence.append(f"Superlatives without qualification: {superlatives[:5]}")

        # [VERIFY] markers are unresolved hallucinations
        verify_count = len(re.findall(r'\[VERIFY[^\]]*\]', article))
        if verify_count > 0:
            findings.append(f"{verify_count} unresolved [VERIFY] markers")
            evidence.append(f"Unresolved verification markers remain")

        n_issues = unsupported_prices + unsupported_pcts + verify_count
        risk_score = min(1.0, n_issues / 10.0)
        critical = n_issues > 5 or unsupported_prices > 5
        confidence = min(0.9, 0.5 + n_issues * 0.05)

        return AgentResult(
            agent_name=self.name,
            risk_score=risk_score,
            critical=critical,
            findings=findings,
            evidence=evidence[:8],
            confidence=confidence,
            duration_ms=(time.time() - start) * 1000,
        )


# ============================================================
# AGENT 2 — ContradictionHunter
# ============================================================

class ContradictionHunter(BaseAdversarialAgent):
    """Detects contradictory claims within the article."""

    CONTRADICTION_PAIRS = [
        ("best", "worst"),
        ("always", "never"),
        ("most", "least"),
        ("highest", "lowest"),
        ("cheapest", "most expensive"),
        ("fastest", "slowest"),
        ("largest", "smallest"),
        ("top", "bottom"),
        ("increase", "decrease"),
        ("more", "less"),
        ("guaranteed", "may not"),
        ("100%", "risk"),
        ("free", "paid"),
        ("all", "none"),
        ("always", "sometimes"),
        ("every", "no"),
        ("must", "avoid"),
        ("essential", "optional"),
    ]

    def __init__(self):
        super().__init__("ContradictionHunter", weight=1.5)

    def audit(self, article: str, keyword: str, **kwargs) -> AgentResult:
        start = time.time()
        findings = []
        evidence = []
        lower = article.lower()

        contradictions_found = 0
        for a, b in self.CONTRADICTION_PAIRS:
            a_present = a in lower
            b_present = b in lower
            if a_present and b_present:
                # Check they're in different sections to confirm contradiction
                sections = re.split(r'<h[1-6][^>]*>', article)
                contra_in_same_section = False
                for sec in sections:
                    sec_lower = sec.lower()
                    if a in sec_lower and b in sec_lower:
                        contra_in_same_section = True
                        break
                if len(sections) > 1:
                    contradictions_found += 1
                    detail = f"'{a}' vs '{b}'" + (" (same section)" if contra_in_same_section else "")
                    evidence.append(detail)

        if contradictions_found > 0:
            findings.append(f"{contradictions_found} contradiction pairs detected")
            if contradictions_found > 3:
                findings.append("High contradiction density — article may be logically inconsistent")

        # Check for explicit contradiction markers
        contra_markers = re.findall(
            r'(however|but|on the other hand).{0,40}(?:but|however|on the other hand)',
            lower
        )
        if len(contra_markers) > 5:
            findings.append(f"{len(contra_markers)} excessive contrast transitions")

        risk_score = min(1.0, contradictions_found / 8.0)
        critical = contradictions_found > 4

        return AgentResult(
            agent_name=self.name,
            risk_score=risk_score,
            critical=critical,
            findings=findings,
            evidence=evidence[:8],
            confidence=0.8 if contradictions_found > 0 else 0.95,
            duration_ms=(time.time() - start) * 1000,
        )


# ============================================================
# AGENT 3 — CitationAuditor
# ============================================================

class CitationAuditor(BaseAdversarialAgent):
    """Audits citation quality, count, freshness, and link health."""

    def __init__(self):
        super().__init__("CitationAuditor", weight=1.0)

    def audit(self, article: str, keyword: str, **kwargs) -> AgentResult:
        start = time.time()
        findings = []
        evidence = []

        links = re.findall(r'<a\s[^>]*href="(https?://[^"]+)"[^>]*>', article, re.I)
        link_count = len(links)

        # Check for minimum citations
        if link_count < 3:
            findings.append(f"Only {link_count} external links (minimum 3 required)")
            evidence.append("Insufficient external citations")

        # Check rel and target
        missing_rel = 0
        for a_tag in re.findall(r'<a\s[^>]*href="https?://[^"]*"[^>]*>', article, re.I):
            if 'rel="nofollow' not in a_tag.lower():
                missing_rel += 1
            if 'target="_blank"' not in a_tag:
                missing_rel += 1

        if missing_rel > 0:
            findings.append(f"{missing_rel} links missing rel=nofollow or target=_blank")

        # Check for broken patterns
        broken_links = re.findall(r'\[LINK:\s*[^\]]+\]', article)
        if broken_links:
            findings.append(f"{len(broken_links)} unresolved link placeholders")
            evidence.append(f"Unresolved placeholders: {broken_links[:3]}")

        # Check for link diversity
        domains = set()
        for link in links:
            m = re.match(r"https?://(?:www\.)?([^/]+)", link)
            if m:
                domains.add(m.group(1))
        if len(domains) < 2 and link_count >= 3:
            findings.append(f"Low citation diversity — all {link_count} links from {len(domains)} domain(s)")
            evidence.append(f"Domains: {', '.join(domains)}")

        risk_score = min(1.0, max(
            0.0,
            (max(0, 3 - link_count)) * 0.25 +
            (missing_rel / max(1, link_count)) * 0.3 +
            (1.0 if not domains else 0.0)
        ))

        critical = link_count == 0 or (link_count < 3 and broken_links)

        return AgentResult(
            agent_name=self.name,
            risk_score=risk_score,
            critical=critical,
            findings=findings,
            evidence=evidence[:6],
            confidence=0.85,
            duration_ms=(time.time() - start) * 1000,
        )


# ============================================================
# AGENT 4 — SEOOverOptimizationDetector
# ============================================================

class SEOOverOptimizationDetector(BaseAdversarialAgent):
    """Detects keyword stuffing, over-optimization, and unnatural phrasing."""

    def __init__(self):
        super().__init__("SEOOverOptimizationDetector", weight=0.9)

    def audit(self, article: str, keyword: str, **kwargs) -> AgentResult:
        start = time.time()
        findings = []
        evidence = []

        total_words = len(article.split())
        if total_words == 0:
            return AgentResult(self.name, 1.0, True, ["Empty article"], [], 0.5)

        # Keyword density
        kw_lower = keyword.lower()
        kw_count = article.lower().count(kw_lower)
        density = kw_count / max(1, total_words)

        if density > 0.05:
            findings.append(f"Keyword density {density:.3f} ({kw_count} occurrences) exceeds 5% threshold")
            evidence.append(f"'{keyword}' appears {kw_count} times in {total_words} words")

        # Exact match repetition
        if density > 0.03:
            # Check for unnatural repetition patterns
            sentences = re.split(r'[.!?]+', article)
            kw_sentences = sum(1 for s in sentences if kw_lower in s.lower())
            if len(sentences) > 0 and kw_sentences / len(sentences) > 0.15:
                findings.append(f"Keyword in {kw_sentences}/{len(sentences)} sentences ({kw_sentences/max(1,len(sentences))*100:.0f}%)")
                evidence.append("Keyword appears in too many sentences")

        # Check for exact-match anchors
        anchors = re.findall(r'>([^<]+)</a>', article)
        exact_match_anchors = sum(1 for a in anchors if kw_lower in a.lower())
        if exact_match_anchors > 3:
            findings.append(f"{exact_match_anchors} keyword-rich anchor texts (risk of over-optimization)")
            evidence.append(f"Keyword-matching anchors: {anchors[:5]}")

        # Check for list of keywords in meta/keyword sections
        meta_keywords = re.findall(r'<meta[^>]*name="keywords"[^>]*content="([^"]+)"', article, re.I)
        if meta_keywords:
            findings.append("Meta keywords tag found (obsolete SEO practice)")
            evidence.append(f"Meta keywords: {meta_keywords[0][:100]}")

        risk_score = min(1.0, density * 5 + exact_match_anchors * 0.1)
        critical = density > 0.08 or kw_count > total_words * 0.10

        return AgentResult(
            agent_name=self.name,
            risk_score=risk_score,
            critical=critical,
            findings=findings,
            evidence=evidence,
            confidence=0.85,
            duration_ms=(time.time() - start) * 1000,
        )


# ============================================================
# AGENT 5 — AIStyleDetector
# ============================================================

class AIStyleDetector(BaseAdversarialAgent):
    """Detects AI writing patterns: repetitive structure, low entropy,
    generic transitions, predictable phrasing."""

    AI_PHRASES = [
        "in today's digital age", "in the ever-evolving world",
        "when it comes to", "it is important to note",
        "it is worth mentioning", "in conclusion", "in summary",
        "to sum up", "all in all", "as previously mentioned",
        "as mentioned earlier", "it goes without saying",
        "needless to say", "last but not least",
        "in this article, we will", "this article will explore",
        "this comprehensive guide", "let's dive in",
        "dive into the world", "unlock the potential",
        "in the realm of", "a plethora of",
        "in the fast-paced world", "the digital landscape",
        "harness the power", "revolutionize the way",
        "game-changer", "cutting-edge",
    ]

    def __init__(self):
        super().__init__("AIStyleDetector", weight=1.1)

    def audit(self, article: str, keyword: str, **kwargs) -> AgentResult:
        start = time.time()
        findings = []
        evidence = []

        text = re.sub(r"<[^>]+>", " ", article)
        text = re.sub(r"\s+", " ", text).strip()

        # Count AI phrases
        lower = text.lower()
        ai_phrases_found = []
        for phrase in self.AI_PHRASES:
            if phrase in lower:
                ai_phrases_found.append(phrase)
        if ai_phrases_found:
            findings.append(f"{len(ai_phrases_found)} AI-associated phrases detected")
            evidence.append(f"Phrases: {ai_phrases_found[:5]}")

        # Sentence start variety
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if len(s.strip().split()) > 3]

        if sentences:
            starts = []
            for s in sentences[:30]:
                words = s.split()
                if words:
                    starts.append(words[0].lower())
            if starts:
                unique_starts = len(set(starts))
                variety = unique_starts / max(1, len(starts))
                if variety < 0.35:
                    findings.append(f"Low sentence start variety ({variety:.2f}) — AI pattern risk")
                    evidence.append(f"Common starts: {starts[:5]}")

            # Sentence length variance
            lengths = [len(s.split()) for s in sentences]
            if lengths:
                avg_len = sum(lengths) / len(lengths)
                variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
                std = math.sqrt(variance)
                if std < 3.0:
                    findings.append(f"Uniform sentence length (std={std:.1f}) — AI rhythm risk")
                    evidence.append("Machine-like sentence pacing")

        # Transition word density
        transitions = [
            "however", "furthermore", "moreover", "nevertheless",
            "nonetheless", "consequently", "additionally", "therefore",
            "thus", "hence", "accordingly", "besides",
        ]
        trans_count = sum(1 for t in transitions if t in lower)
        if trans_count > 5:
            findings.append(f"Excessive transitions ({trans_count}) — template AI style")
            evidence.append(f"Overused: {[t for t in transitions[:8] if t in lower]}")

        risk_score = min(1.0, (
            len(ai_phrases_found) * 0.06 +
            (1.0 - variety if 'variety' in dir() and variety < 0.35 else 0.0) * 0.4 +
            (trans_count * 0.02)
        ))
        critical = len(ai_phrases_found) > 8 or (len(sentences) > 10 and 'std' in dir() and std < 2.0)

        return AgentResult(
            agent_name=self.name,
            risk_score=risk_score,
            critical=critical,
            findings=findings,
            evidence=evidence[:6],
            confidence=0.75,
            duration_ms=(time.time() - start) * 1000,
        )


# ============================================================
# AGENT 6 — LegalRiskAuditor
# ============================================================

class LegalRiskAuditor(BaseAdversarialAgent):
    """Detects legal risk: fake testimonials, earnings claims,
    health claims, guarantees, warranty language, liability exposure."""

    RISKY_PATTERNS = {
        "fake_testimonial": [
            "results may vary", "individual results", "testimonial",
            "\"i lost", "\"i made", "\"i earned",
        ],
        "earnings_claim": [
            "make money fast", "earn $", "passive income",
            "work from home", "get rich", "financial freedom",
        ],
        "health_claim": [
            "cure", "treats", "prevents", "reverses",
            "heals", "no side effects", "guaranteed results",
            "miracle", "detox", "cleansing",
        ],
        "guarantee": [
            "money-back guarantee", "satisfaction guaranteed",
            "100% guarantee", "risk-free", "no questions asked",
        ],
        "affiliate_disclosure_missing": [
            "affiliate", "commission", "paid link",
        ],
    }

    def __init__(self):
        super().__init__("LegalRiskAuditor", weight=1.3)

    def audit(self, article: str, keyword: str, **kwargs) -> AgentResult:
        start = time.time()
        findings = []
        evidence = []
        lower = article.lower()

        total_risk = 0
        for category, patterns in self.RISKY_PATTERNS.items():
            matches = [p for p in patterns if p in lower]
            if matches:
                total_risk += len(matches)
                if len(matches) > 1:
                    findings.append(f"{category}: {len(matches)} risky patterns")
                    evidence.append(f"Patterns: {matches[:4]}")

        # Check for affiliate disclosure
        has_affiliate = any(p in lower for p in self.RISKY_PATTERNS["affiliate_disclosure_missing"])
        has_disclosure = "disclosure" in lower and ("affiliate" in lower or "commission" in lower)
        if has_affiliate and not has_disclosure:
            findings.append("Possible affiliate links without disclosure")
            evidence.append("Affiliate signals found but no disclosure statement")

        # Check for absolute claims
        absolute_claims = re.findall(
            r'\b(always|never|guaranteed|100%|everyone|nobody)\b', lower
        )
        if len(absolute_claims) > 5:
            findings.append(f"Excessive absolute claims ({len(absolute_claims)}) — legal liability risk")
            evidence.append(f"Absolute terms: {list(set(absolute_claims))[:6]}")

        risk_score = min(1.0, total_risk / 10.0)
        critical = total_risk > 5 or (has_affiliate and not has_disclosure)

        return AgentResult(
            agent_name=self.name,
            risk_score=risk_score,
            critical=critical,
            findings=findings,
            evidence=evidence[:6],
            confidence=0.8,
            duration_ms=(time.time() - start) * 1000,
        )


# ============================================================
# AGENT 7 — TemporalDecayAuditor
# ============================================================

class TemporalDecayAuditor(BaseAdversarialAgent):
    """Scores how much of the article relies on stale or expired information."""

    FRESHNESS_INDICATORS = {
        "as of 2026": 0.95,
        "2026": 0.90,
        "2025": 0.70,
        "2024": 0.40,
        "2023": 0.20,
        "2022": 0.10,
        "2021": 0.05,
        "2020": 0.0,
        "recent study": 0.80,
        "latest": 0.75,
        "new research": 0.70,
        "current": 0.60,
    }

    STALE_PHRASES = [
        "as of 2020", "as of 2021", "as of 2022", "as of 2023",
        "in 2020", "in 2021",
        "last year", "a few years ago",
        "traditionally", "historically",
    ]

    def __init__(self):
        super().__init__("TemporalDecayAuditor", weight=1.0)

    def audit(self, article: str, keyword: str, **kwargs) -> AgentResult:
        start = time.time()
        findings = []
        evidence = []
        lower = article.lower()

        # Score freshness
        freshness_score = 0.3  # baseline
        for indicator, score in self.FRESHNESS_INDICATORS.items():
            if indicator in lower:
                freshness_score = max(freshness_score, score)
                if score < 0.3:
                    evidence.append(f"Stale indicator: '{indicator}'")

        # Count stale references
        stale_count = sum(1 for p in self.STALE_PHRASES if p in lower)
        if stale_count > 0:
            findings.append(f"{stale_count} stale date references detected")
            evidence.append(f"Stale references found")

        # Check for year distribution
        years_found = re.findall(r'\b(19|20)[0-9]{2}\b', article)
        old_years = [y for y in years_found if int(y) < 2025]
        if len(old_years) > 3:
            findings.append(f"{len(old_years)} references to years before 2025")
            evidence.append(f"Old years: {list(set(old_years))[:5]}")

        # Check for "recent" without date
        recent_claims = re.findall(r'recent(?:ly)?\s+(?:study|report|research|data|survey)', lower)
        if recent_claims:
            findings.append(f"{len(recent_claims)} vague 'recent' claims without specific dates")
            evidence.append(f"Vague recency: {recent_claims[:3]}")

        risk_score = max(0.0, 1.0 - freshness_score - stale_count * 0.1)
        risk_score = min(1.0, risk_score + len(old_years) * 0.05)
        critical = freshness_score < 0.2 or stale_count > 3

        return AgentResult(
            agent_name=self.name,
            risk_score=risk_score,
            critical=critical,
            findings=findings,
            evidence=evidence[:6],
            confidence=0.8,
            duration_ms=(time.time() - start) * 1000,
        )


# ============================================================
# AGENT 8 — SchemaValidator
# ============================================================

class SchemaValidator(BaseAdversarialAgent):
    """Validates JSON-LD schemas, HTML structure, and required elements."""

    def __init__(self):
        super().__init__("SchemaValidator", weight=1.0)

    def audit(self, article: str, keyword: str, **kwargs) -> AgentResult:
        start = time.time()
        findings = []
        evidence = []

        # Extract schema blocks
        schema_blocks = re.findall(
            r'<script[^>]*type="?application/ld\+json"?[^>]*>(.*?)</script>',
            article, re.DOTALL | re.IGNORECASE
        )

        if not schema_blocks:
            findings.append("No JSON-LD schema found")
            evidence.append("Missing all schema markup")
            return AgentResult(
                self.name, 0.9, True,
                ["No JSON-LD schema found"],
                ["Missing all schema markup"], 0.95,
                duration_ms=(time.time() - start) * 1000,
            )

        # Parse and validate each schema
        valid_count = 0
        invalid_count = 0
        has_article = False
        has_faqpage = False
        has_itemlist = False

        for block in schema_blocks:
            try:
                data = json.loads(block.strip())
                schema_type = ""
                if isinstance(data, dict):
                    schema_type = data.get("@type", "")
                    if schema_type == "Article":
                        has_article = True
                        # Check required fields
                        for field in ["headline", "datePublished"]:
                            if field not in data:
                                findings.append(f"Article schema missing '{field}'")
                                evidence.append(f"Missing {field} in Article schema")
                    elif schema_type == "FAQPage":
                        has_faqpage = True
                        main_entity = data.get("mainEntity", [])
                        if not main_entity:
                            findings.append("FAQPage schema has no mainEntity items")
                            evidence.append("Empty FAQPage schema")
                    elif schema_type == "ItemList":
                        has_itemlist = True
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            st = item.get("@type", "")
                            if st == "Article":
                                has_article = True
                            elif st == "FAQPage":
                                has_faqpage = True
                            elif st == "ItemList":
                                has_itemlist = True
                valid_count += 1
            except json.JSONDecodeError:
                invalid_count += 1
                evidence.append(f"Invalid JSON in schema block {len(schema_blocks)}")

        if invalid_count:
            findings.append(f"{invalid_count} schema block(s) failed JSON validation")

        if not has_article:
            findings.append("Missing Article JSON-LD schema (required)")
            evidence.append("Article schema @type not found")

        # H1 check
        h1s = re.findall(r'<h1[^>]*>', article, re.I)
        if len(h1s) == 0:
            findings.append("Missing H1 heading")
        elif len(h1s) > 1:
            findings.append(f"{len(h1s)} H1 headings (only 1 allowed)")
            evidence.append("Multiple H1 tags")

        # Check for unclosed tags
        for tag in ['div', 'p', 'section', 'table', 'tr', 'td', 'th', 'ul', 'ol', 'li']:
            opens = len(re.findall(rf'<{tag}[\s>]', article, re.I))
            closes = len(re.findall(rf'</{tag}>', article, re.I))
            if opens != closes and opens > 0:
                findings.append(f"Unclosed <{tag}> tags ({opens} open, {closes} closed)")
                if len(evidence) < 6:
                    evidence.append(f"<{tag}> mismatch: {opens} vs {closes}")

        # FAQPage schema vs actual FAQ items match
        if has_faqpage:
            faqpage_block = ""
            for fp in ['"@type": "FAQPage"', '"@type":"FAQPage"']:
                idx = article.find(fp)
                if idx >= 0:
                    closing = article.find('}', idx)
                    if closing >= 0:
                        faqpage_block = article[idx:closing+1]
                        break
            if faqpage_block:
                schema_qs = re.findall(r'"name":\s*"([^"]+)"', faqpage_block)
                faq_items = re.findall(r'class="faq-q"[^>]*>(.*?)</div>', article, re.DOTALL)
                faq_clean = [re.sub(r'<[^>]+>', '', q).strip() for q in faq_items]
                if schema_qs and faq_clean:
                    unmatched = sum(
                        1 for s in schema_qs
                        if not any(s.lower() in fq.lower() or fq.lower() in s.lower() for fq in faq_clean)
                    )
                    if unmatched > 2:
                        findings.append(f"{unmatched} FAQPage schema questions don't match FAQ items")
                        evidence.append(f"FAQ schema/items mismatch")

        risk_score = 0.0
        if not has_article:
            risk_score += 0.4
        if invalid_count:
            risk_score += 0.2 * invalid_count
        if len(h1s) != 1:
            risk_score += 0.2
        risk_score = min(1.0, risk_score)

        critical = not has_article or invalid_count > 1 or len(h1s) == 0

        return AgentResult(
            agent_name=self.name,
            risk_score=risk_score,
            critical=critical,
            findings=findings,
            evidence=evidence[:8],
            confidence=0.9,
            duration_ms=(time.time() - start) * 1000,
        )


# ============================================================
# AGENT 9 — ManipulationDetector
# ============================================================

class ManipulationDetector(BaseAdversarialAgent):
    """Detects dark patterns, manipulation, and deceptive content."""

    MANIPULATION_PATTERNS = [
        "limited time", "act now", "don't miss out",
        "only X left", "exclusive offer", "secret",
        "hidden", "insider", "proprietary",
        "urgent", "warning", "important notice",
        "claim your", "reserve your", "secure your",
        "before it's too late", "last chance",
        "exclusive access", "members only",
        "free trial", "no obligation",
        "risk-free", "no strings attached",
        "guaranteed approval", "guaranteed results",
    ]

    DECEPTIVE_PATTERNS = [
        "as seen on", "featured in", "trusted by",
        "recommended by", # without specific context
        "#1 rated", "top rated", "award-winning",
        "voted best", "most popular",
    ]

    def __init__(self):
        super().__init__("ManipulationDetector", weight=0.8)

    def audit(self, article: str, keyword: str, **kwargs) -> AgentResult:
        start = time.time()
        findings = []
        evidence = []
        lower = article.lower()

        # Count manipulation patterns
        manip_found = []
        for p in self.MANIPULATION_PATTERNS:
            if p in lower:
                manip_found.append(p)

        if manip_found:
            findings.append(f"{len(manip_found)} manipulation/urgency patterns detected")
            evidence.append(f"Patterns: {manip_found[:5]}")

        # Deceptive patterns
        deceptive_found = []
        for p in self.DECEPTIVE_PATTERNS:
            if p in lower:
                deceptive_found.append(p)

        if deceptive_found:
            findings.append(f"{len(deceptive_found)} potentially deceptive claims")
            evidence.append(f"Patterns: {deceptive_found[:5]}")

        # Check for fake scarcity
        scarcity_patterns = re.findall(
            r'(only|just)\s+\d+\s+(left|remaining|available|spots|seats)',
            lower
        )
        if scarcity_patterns:
            findings.append(f"Fake scarcity language detected")
            evidence.append(f"Scarcity: {scarcity_patterns[:3]}")

        # Count exclamation mark density
        excl_count = article.count('!')
        word_count = len(article.split())
        if word_count > 0 and excl_count / word_count > 0.02:
            findings.append(f"Excessive exclamation marks ({excl_count}) — sensationalism")
            evidence.append(f"! density: {excl_count}/{word_count}")

        total_issues = len(manip_found) + len(deceptive_found) + len(scarcity_patterns)
        risk_score = min(1.0, total_issues / 12.0)
        critical = total_issues > 6

        return AgentResult(
            agent_name=self.name,
            risk_score=risk_score,
            critical=critical,
            findings=findings,
            evidence=evidence[:6],
            confidence=0.75,
            duration_ms=(time.time() - start) * 1000,
        )


# ============================================================
# SWARM COORDINATOR
# ============================================================

@dataclass
class AdversarialReport:
    """Aggregated report from the full adversarial swarm."""
    keyword: str
    agent_results: list[AgentResult] = field(default_factory=list)
    weighted_risk_score: float = 0.0
    consensus_verdict: str = "pass"  # pass / review / quarantine / block
    majority_disagreement: bool = False
    cross_agent_contradictions: list[dict] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    quarantine_recommended: bool = False
    human_review_recommended: bool = False
    auto_repair_recommended: bool = False
    swarm_confidence: float = 0.0
    computed_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "agent_results": [r.to_dict() for r in self.agent_results],
            "weighted_risk_score": self.weighted_risk_score,
            "consensus_verdict": self.consensus_verdict,
            "majority_disagreement": self.majority_disagreement,
            "cross_agent_contradictions": self.cross_agent_contradictions,
            "recommendations": self.recommendations,
            "quarantine_recommended": self.quarantine_recommended,
            "human_review_recommended": self.human_review_recommended,
            "auto_repair_recommended": self.auto_repair_recommended,
            "swarm_confidence": self.swarm_confidence,
            "computed_at": self.computed_at,
        }

    def summary(self) -> str:
        lines = [f"Adversarial Swarm: {self.consensus_verdict.upper()} (risk={self.weighted_risk_score:.3f})"]
        lines.append(f"  Agents: {len(self.agent_results)} total")
        for r in sorted(self.agent_results, key=lambda x: x.risk_score, reverse=True):
            bar = "█" * int(r.risk_score * 20)
            flag = " ⚠ CRITICAL" if r.critical else ""
            lines.append(f"    {r.agent_name:30s} {r.risk_score:.3f}  {bar}{flag}")
        if self.recommendations:
            lines.append("  Recommendations:")
            for rec in self.recommendations:
                lines.append(f"    • {rec}")
        return "\n".join(lines)


class SwarmCoordinator:
    """Orchestrates all adversarial agents, normalizes confidence,
    detects cross-agent disagreement, produces AdversarialReport."""

    def __init__(self):
        self.agents: list[BaseAdversarialAgent] = [
            HallucinationHunter(),
            ContradictionHunter(),
            CitationAuditor(),
            SEOOverOptimizationDetector(),
            AIStyleDetector(),
            LegalRiskAuditor(),
            TemporalDecayAuditor(),
            SchemaValidator(),
            ManipulationDetector(),
        ]

    def run_swarm(
        self,
        article: str,
        keyword: str,
        **kwargs
    ) -> AdversarialReport:
        """Run all agents synchronously (can be parallelized externally)."""
        results: list[AgentResult] = []

        for agent in self.agents:
            try:
                result = agent.audit(article, keyword, **kwargs)
                results.append(result)
            except Exception as e:
                log.error("[SWARM] Agent '%s' failed: %s", agent.name, e)
                results.append(AgentResult(
                    agent_name=agent.name,
                    risk_score=0.5,
                    critical=False,
                    findings=[f"Agent crashed: {e}"],
                    evidence=[],
                    confidence=0.0,
                ))

        return self._build_report(results, keyword)

    def run_agents_async(self, article: str, keyword: str, **kwargs) -> list[AgentResult]:
        """Return raw results without aggregation (for external orchestration)."""
        results = []
        for agent in self.agents:
            try:
                results.append(agent.audit(article, keyword, **kwargs))
            except Exception as e:
                log.error("[SWARM] Agent '%s' failed: %s", agent.name, e)
        return results

    def _build_report(self, results: list[AgentResult], keyword: str) -> AdversarialReport:
        # Normalize confidence across agents
        total_confidence = sum(r.confidence for r in results)
        if total_confidence > 0:
            for r in results:
                r.confidence = min(1.0, r.confidence / total_confidence * len(results))

        # Weighted risk score
        total_weight = sum(r.confidence * r.risk_score for r in results)
        total_confidence_sum = sum(r.confidence for r in results) or 1.0
        weighted_risk_score = total_weight / total_confidence_sum

        # Detect majority disagreement (high variance in scores)
        scores = [r.risk_score for r in results]
        if scores:
            mean = sum(scores) / len(scores)
            variance = sum((s - mean) ** 2 for s in scores) / len(scores)
            std_dev = math.sqrt(variance)
            majority_disagreement = std_dev > 0.25

        # Consensus verdict
        critical_count = sum(1 for r in results if r.critical)
        high_risk_count = sum(1 for r in results if r.risk_score > 0.6)

        if critical_count >= 3 or weighted_risk_score > 0.75:
            consensus_verdict = "block"
        elif critical_count >= 1 or weighted_risk_score > 0.55:
            consensus_verdict = "quarantine"
        elif high_risk_count >= 2 or weighted_risk_score > 0.35:
            consensus_verdict = "review"
        else:
            consensus_verdict = "pass"

        # Cross-agent contradiction detection
        cross_contradictions = self._detect_cross_contradictions(results)

        # Recommendations
        recommendations = []
        quarantine_rec = consensus_verdict in ("block", "quarantine")
        human_review_rec = consensus_verdict in ("quarantine", "review")
        auto_repair_rec = consensus_verdict == "review" and weighted_risk_score < 0.6

        if consensus_verdict == "block":
            recommendations.append("BLOCK: Article exceeds safety thresholds across multiple dimensions")
        if quarantine_rec:
            recommendations.append("Quarantine article for manual inspection")
        if human_review_rec:
            recommendations.append("Request human editorial review before publishing")
        if auto_repair_rec:
            recommendations.append("Attempt auto-repair with targeted strategy")
        if majority_disagreement:
            recommendations.append("High agent disagreement — investigate edge cases")

        # Add top findings
        for r in sorted(results, key=lambda x: x.risk_score, reverse=True)[:3]:
            if r.findings:
                recommendations.append(f"[{r.agent_name}] {r.findings[0]}")

        swarm_confidence = 1.0 - (std_dev if scores else 0.0)

        return AdversarialReport(
            keyword=keyword,
            agent_results=results,
            weighted_risk_score=weighted_risk_score,
            consensus_verdict=consensus_verdict,
            majority_disagreement=majority_disagreement,
            cross_agent_contradictions=cross_contradictions,
            recommendations=recommendations[:10],
            quarantine_recommended=quarantine_rec,
            human_review_recommended=human_review_rec,
            auto_repair_recommended=auto_repair_rec,
            swarm_confidence=swarm_confidence,
            computed_at=time.time(),
        )

    def _detect_cross_contradictions(self, results: list[AgentResult]) -> list[dict]:
        """Find cases where agents disagree significantly."""
        contradictions = []
        for i in range(len(results)):
            for j in range(i + 1, len(results)):
                a, b = results[i], results[j]
                score_diff = abs(a.risk_score - b.risk_score)
                if score_diff > 0.5:
                    contradictions.append({
                        "agent_a": a.agent_name,
                        "agent_b": b.agent_name,
                        "score_a": a.risk_score,
                        "score_b": b.risk_score,
                        "delta": score_diff,
                        "type": "risk_score_disagreement",
                    })
        return contradictions


# ── Global Singleton ─────────────────────────────────────

_SWARM: Optional[SwarmCoordinator] = None


def get_swarm() -> SwarmCoordinator:
    global _SWARM
    if _SWARM is None:
        _SWARM = SwarmCoordinator()
    return _SWARM


def reset_swarm() -> None:
    global _SWARM
    _SWARM = None


def run_adversarial_swarm(
    article: str,
    keyword: str,
    **kwargs
) -> AdversarialReport:
    """Quick-access: run full adversarial swarm audit."""
    swarm = get_swarm()
    return swarm.run_swarm(article, keyword, **kwargs)
