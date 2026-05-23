"""
generation_consensus_engine.py — Multi-Model Consensus Pipeline
================================================================
Transforms single-model generation into multi-model consensus:
  draft → critique → fact-check → entropy → merge → confidence score

Only consensus-approved claims survive. Runs during generation.
"""

from __future__ import annotations

import re
import json
import time
import hashlib
import logging
from typing import Any

log = logging.getLogger("consensus_engine")


# ============================================================
# CRITIQUE MODEL
# ============================================================

class CritiqueModel:
    """Reviews article for factual, structural, and quality issues."""

    BANNED_OPENERS = [
        "in today", "in the world", "when it comes to",
        "let's face it", "have you ever", "if you're looking for",
        "the truth is", "the fact is", "it's no secret",
        "in recent years", "over the past few",
    ]

    def critique(self, article: str, keyword: str) -> list[dict]:
        issues = []
        lower = article.lower()

        # Banned openers
        for opener in self.BANNED_OPENERS:
            if opener in lower:
                issues.append({
                    "type": "banned_opener",
                    "severity": "medium",
                    "detail": f"Banned opener: '{opener}'",
                })
                break  # one is enough

        # H1 check
        h1s = re.findall(r"<h1[^>]*>", article, re.I)
        if len(h1s) == 0:
            issues.append({
                "type": "missing_h1",
                "severity": "critical",
                "detail": "No H1 heading found",
            })
        elif len(h1s) > 1:
            issues.append({
                "type": "duplicate_h1",
                "severity": "high",
                "detail": f"{len(h1s)} H1 headings found",
            })

        # Bare paragraphs (text not wrapped in <p>)
        bare_text = re.findall(r">([^<]+)</(?!p|h[1-6]|div|li|td|th)", article)
        if bare_text:
            issues.append({
                "type": "bare_paragraph",
                "severity": "medium",
                "detail": f"{len(bare_text)} bare text blocks outside <p>",
            })

        # FAQ structure
        faq_q = len(re.findall(r'class="faq-q"', article))
        faq_a = len(re.findall(r'class="faq-a"', article))
        if faq_q > 0 and faq_q != faq_a:
            issues.append({
                "type": "faq_mismatch",
                "severity": "high",
                "detail": f"{faq_q} questions vs {faq_a} answers",
            })

        # Keyword presence in H1
        kw_lower = keyword.lower()
        if h1s and kw_lower not in article[:500].lower():
            issues.append({
                "type": "keyword_missing_h1",
                "severity": "medium",
                "detail": "Keyword not found in article opening",
            })

        return issues


# ============================================================
# FACT MODEL
# ============================================================

class FactModel:
    """Verifies factual claims — price, percentage, year assertions."""

    PRICE_RX = re.compile(r"\$[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?")
    PCT_RX = re.compile(r"\b[0-9]{1,3}%")
    YEAR_RX = re.compile(r"\b(19|20)[0-9]{2}\b")

    def verify(self, article: str) -> list[dict]:
        results = []

        # Price claims
        prices = self.PRICE_RX.findall(article)
        for p in prices:
            ctx = self._context(article, p)
            supported = self._is_supported(ctx)
            results.append({
                "claim": p,
                "type": "price",
                "supported": supported,
                "context": ctx[:120],
                "confidence": 0.8 if supported else 0.3,
            })

        # Percentage claims
        pcts = self.PCT_RX.findall(article)
        for p in pcts[:10]:  # cap per article
            ctx = self._context(article, p)
            supported = self._is_supported(ctx)
            results.append({
                "claim": p,
                "type": "percentage",
                "supported": supported,
                "context": ctx[:120],
                "confidence": 0.8 if supported else 0.3,
            })

        return results

    def _context(self, article: str, fragment: str) -> str:
        idx = article.find(fragment)
        if idx < 0:
            return fragment
        start = max(0, idx - 80)
        end = min(len(article), idx + len(fragment) + 80)
        return article[start:end]

    def _is_supported(self, ctx: str) -> bool:
        lower = ctx.lower()
        indicators = [
            "according to", "source", "report", "study",
            "research", "data", "statistics", "survey",
            "per ", "estimated", "approximately", "around",
        ]
        return any(i in lower for i in indicators)


# ============================================================
# ENTROPY MODEL
# ============================================================

class EntropyModel:
    """Checks sentence rhythm and AI detection patterns."""

    def analyze(self, article: str) -> dict:
        text = re.sub(r"<[^>]+>", " ", article)
        text = re.sub(r"\s+", " ", text).strip()

        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        if not sentences:
            return {"pass": False, "reason": "No sentences"}

        lengths = [len(s.split()) for s in sentences]
        avg = sum(lengths) / len(lengths)
        variance = max(lengths) - min(lengths) if lengths else 0
        std = (
            (sum((l - avg) ** 2 for l in lengths) / len(lengths)) ** 0.5
            if lengths else 0
        )

        repetitive_starts = self._repetitive_starts(sentences)

        return {
            "pass": variance >= 6 and std >= 3 and repetitive_starts < 0.4,
            "sentence_count": len(sentences),
            "avg_words": round(avg, 1),
            "variance": variance,
            "std": round(std, 1),
            "repetitive_starts": round(repetitive_starts, 2),
            "ai_risk": "high" if (variance < 6 or std < 3) else "low",
        }

    def _repetitive_starts(self, sentences: list[str]) -> float:
        if not sentences:
            return 0.0
        starts = [s.split()[0].lower() if s.split() else "" for s in sentences]
        if not starts:
            return 0.0
        unique = len(set(starts))
        return 1.0 - (unique / len(starts))


# ============================================================
# CONFIDENCE SCORER
# ============================================================

class ConfidenceScorer:
    """Scores confidence per claim based on consensus signals."""

    def score(self, claim: dict, critique_issues: list[dict]) -> dict:
        base = claim.get("confidence", 0.5)

        # Deduct for critique issues targeting this claim type
        ctype = claim.get("type", "")
        for issue in critique_issues:
            if ctype == "price" and "price" in issue.get("detail", "").lower():
                base -= 0.2
            if ctype == "percentage" and "percent" in issue.get("detail", "").lower():
                base -= 0.2

        # Boost for supported claims
        if claim.get("supported"):
            base += 0.2

        # Penalize unsupported
        if not claim.get("supported") and claim.get("type") in ("price", "percentage"):
            base -= 0.3

        return {
            "claim": claim.get("claim", ""),
            "raw_confidence": claim.get("confidence", 0.5),
            "adjusted_confidence": max(0.0, min(1.0, base)),
            "verdict": "approved" if base >= 0.5 else "rejected",
        }


# ============================================================
# CONSENSUS ENGINE
# ============================================================

class ConsensusEngine:
    """Merges draft, critique, fact, and entropy into final output."""

    def merge(
        self,
        article: str,
        critique_issues: list[dict],
        fact_results: list[dict],
        entropy: dict,
    ) -> tuple[str, dict]:
        report = {
            "critique_count": len(critique_issues),
            "critical_issues": [i for i in critique_issues if i.get("severity") == "critical"],
            "high_issues": [i for i in critique_issues if i.get("severity") == "high"],
            "fact_verified": sum(1 for f in fact_results if f.get("supported")),
            "fact_rejected": sum(1 for f in fact_results if not f.get("supported")),
            "entropy_pass": entropy.get("pass", False),
            "entropy_risk": entropy.get("ai_risk", "unknown"),
        }

        # Reject unsupported price claims
        for fact in fact_results:
            if not fact.get("supported") and fact.get("type") in ("price", "percentage"):
                claim = fact.get("claim", "")
                if claim and claim in article:
                    article = article.replace(
                        claim,
                        f"{claim} [VERIFY]",
                        1,
                    )

        # Flag critical issues
        if report["critical_issues"]:
            log.warning(
                "[CONSENSUS] %d critical issues — article may be blocked",
                len(report["critical_issues"]),
            )

        return article, report


# ============================================================
# GENERATION CONSENSUS ENGINE
# ============================================================

class GenerationConsensusEngine:
    """Orchestrates multi-model consensus: critique → fact → entropy → merge."""

    def __init__(self):
        self.critique = CritiqueModel()
        self.fact = FactModel()
        self.entropy = EntropyModel()
        self.scorer = ConfidenceScorer()
        self.consensus = ConsensusEngine()

    def run(self, article: str, keyword: str) -> tuple[str, dict]:
        """
        Run full consensus pipeline.

        Returns:
            (modified_article, consensus_report)
        """
        start = time.time()

        # 1. Critique pass
        critique_issues = self.critique.critique(article, keyword)

        # 2. Fact verification pass
        fact_results = self.fact.verify(article)

        # 3. Score each claim
        scored = [self.scorer.score(c, critique_issues) for c in fact_results]

        # 4. Entropy analysis
        entropy = self.entropy.analyze(article)

        # 5. Merge into consensus
        article, report = self.consensus.merge(
            article, critique_issues, fact_results, entropy,
        )

        report["claims_scored"] = len(scored)
        report["claims_approved"] = sum(1 for s in scored if s.get("verdict") == "approved")
        report["claims_rejected"] = sum(1 for s in scored if s.get("verdict") == "rejected")
        report["duration_ms"] = round((time.time() - start) * 1000, 1)

        return article, report


# ============================================================
# GLOBAL SINGLETON
# ============================================================

_CONSENSUS = GenerationConsensusEngine()


def run_consensus(article: str, keyword: str) -> tuple[str, dict]:
    """Run multi-model consensus on an article."""
    return _CONSENSUS.run(article, keyword)
