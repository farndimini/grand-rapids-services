"""
seo_intelligence.py — Autonomous SEO Intelligence Engine v1
==============================================================
Phase 3 runtime: search-grounded, evidence-aware, human-quality,
conversion-optimized, SERP-adaptive, citation-backed, editorial-grade.

8 capabilities in one deterministic module:
  1. SERP Semantic Gap Engine
  2. Citation-Backed Generation
  3. Retrieval-Grounded Writing
  4. Human Editorial Rewriter
  5. Conversion-Aware Optimizer
  6. Topic Authority Memory
  7. AI Detection Resistance
  8. Autonomous Quality Evolution
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import random
import re
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("seo_intelligence")

# ============================================================================
#  DIMENSION 1 — SERP SEMANTIC GAP ENGINE
# ============================================================================

@dataclass
class SERPGapReport:
    keyword: str
    total_serp_concepts: int = 0
    covered_concepts: int = 0
    missing_concepts: list[str] = field(default_factory=list)
    missing_entities: list[str] = field(default_factory=list)
    semantic_coverage: float = 0.0
    entity_overlap: float = 0.0
    covered_headings: int = 0
    total_serp_headings: int = 0
    heading_overlap: float = 0.0
    detected_intent: str = ""
    intent_match: bool = False
    competitor_weaknesses: list[str] = field(default_factory=list)
    recommended_sections: list[str] = field(default_factory=list)
    people_also_ask: list[str] = field(default_factory=list)


class SERPGapEngine:
    """Compare generated article vs SERP competitors.

    Extracts:
    - Semantic topics from article and SERP
    - Entity clusters from both
    - Heading overlap analysis
    - Missing intent detection
    - People Also Ask extraction
    - Semantic coverage scoring
    - Competitor weakness detection
    """

    _STOP_WORDS = frozenset({
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
        "been", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "this", "that", "these", "those",
        "it", "its", "they", "them", "their", "we", "our", "you", "your",
        "he", "she", "him", "her", "his", "what", "which", "who", "when",
        "where", "why", "how", "all", "each", "every", "both", "few", "more",
        "most", "other", "some", "such", "no", "nor", "not", "only", "own",
        "same", "so", "than", "too", "very", "just", "now", "then", "also",
        "here", "there", "up", "down", "out", "off", "over", "under", "again",
        "further", "once", "during", "before", "after", "above", "below",
        "between", "through", "while", "about", "against", "into", "onto",
        "upon", "within", "without", "across", "around", "behind", "beyond",
        "except", "inside", "outside", "until", "via", "per", "among", "toward",
    })

    def __init__(self):
        self._lock = threading.RLock()
        self._reports: list[SERPGapReport] = []

    def analyze(
        self,
        keyword: str,
        article_html: str,
        serp_data: list[dict] | None = None,
        competitor_articles: list[str] | None = None,
    ) -> SERPGapReport:
        """Run full semantic gap analysis.

        Args:
            keyword: Target keyword
            article_html: Generated article HTML
            serp_data: List of SERP result dicts with 'title', 'snippet', 'headings'
            competitor_articles: HTML strings of top competitor articles
        """
        article_text = self._html_to_text(article_html)
        article_entities = self._extract_entities(article_text)
        article_concepts = self._extract_key_concepts(article_text)
        article_headings = self._extract_headings(article_html)

        serp_concepts: set[str] = set()
        serp_entities: set[str] = set()
        serp_headings: set[str] = set()
        serp_questions: list[str] = []
        competitor_texts: list[str] = []

        if serp_data:
            for result in serp_data:
                serp_text = f"{result.get('title', '')} {result.get('snippet', '')}"
                serp_concepts.update(self._extract_key_concepts(serp_text))
                serp_entities.update(self._extract_entities(serp_text))
                result_headings = result.get('headings', [])
                serp_headings.update(h.lower().strip() for h in result_headings)
                if 'questions' in result:
                    serp_questions.extend(result['questions'])
                if result.get('snippet'):
                    competitor_texts.append(result['snippet'])

        if competitor_articles:
            for comp_html in competitor_articles:
                comp_text = self._html_to_text(comp_html)
                competitor_texts.append(comp_text)
                serp_concepts.update(self._extract_key_concepts(comp_text))
                serp_entities.update(self._extract_entities(comp_text))
                serp_headings.update(h.lower().strip() for h in self._extract_headings(comp_html))

        missing_concepts = serp_concepts - article_concepts
        missing_entities = serp_entities - article_entities

        covered_headings = sum(1 for h in serp_headings if any(
            self._heading_similarity(h, ah) > 0.5 for ah in article_headings
        ))

        semantic_coverage = len(article_concepts & serp_concepts) / max(1, len(serp_concepts))
        entity_overlap = len(article_entities & serp_entities) / max(1, len(serp_entities))
        heading_overlap = covered_headings / max(1, len(serp_headings))

        detected_intent = self._detect_search_intent(keyword, article_text)
        intent_signals = self._intent_signals(article_text)
        intent_match = detected_intent in intent_signals

        competitor_weaknesses = self._find_competitor_weaknesses(competitor_texts, article_concepts)
        recommended_sections = self._recommend_sections(missing_concepts, detected_intent)

        report = SERPGapReport(
            keyword=keyword,
            total_serp_concepts=len(serp_concepts),
            covered_concepts=len(article_concepts & serp_concepts),
            missing_concepts=sorted(missing_concepts)[:15],
            missing_entities=sorted(missing_entities)[:10],
            semantic_coverage=round(semantic_coverage, 3),
            entity_overlap=round(entity_overlap, 3),
            covered_headings=covered_headings,
            total_serp_headings=len(serp_headings),
            heading_overlap=round(heading_overlap, 3),
            detected_intent=detected_intent,
            intent_match=intent_match,
            competitor_weaknesses=competitor_weaknesses[:5],
            recommended_sections=recommended_sections[:5],
            people_also_ask=serp_questions[:8],
        )

        with self._lock:
            self._reports.append(report)

        return report

    @staticmethod
    def _html_to_text(html: str) -> str:
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    @staticmethod
    def _extract_entities(text: str) -> set[str]:
        entities = set()
        for m in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b', text):
            entity = m.group(1).strip()
            if len(entity) > 3 and not any(c.isdigit() for c in entity):
                entities.add(entity.lower())
        for m in re.finditer(r'\b([A-Z]{2,}(?:\s+[A-Z]{2,}){0,2})\b', text):
            entity = m.group(1).strip()
            if len(entity) > 2:
                entities.add(entity.lower())
        return entities

    @staticmethod
    def _extract_key_concepts(text: str) -> set[str]:
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        word_freq = Counter(words)
        stop = SERPGapEngine._STOP_WORDS
        concepts = set()
        for word, freq in word_freq.most_common(50):
            if word not in stop and freq >= 2:
                concepts.add(word)
        for m in re.finditer(r'\b([a-z]+(?:\s+[a-z]+){1,3})\b', text.lower()):
            phrase = m.group(1)
            words_in_phrase = phrase.split()
            if len(phrase) > 10 and all(w not in stop for w in words_in_phrase):
                concepts.add(phrase)
        return concepts

    @staticmethod
    def _extract_headings(html: str) -> list[str]:
        headings = []
        for tag in ['h1', 'h2', 'h3']:
            for m in re.finditer(f'<{tag}[^>]*>(.*?)</{tag}>', html, re.DOTALL | re.IGNORECASE):
                h = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                if h:
                    headings.append(h.lower())
        return headings

    @staticmethod
    def _heading_similarity(a: str, b: str) -> float:
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / len(words_a | words_b)

    @staticmethod
    def _detect_search_intent(keyword: str, article_text: str) -> str:
        kw = keyword.lower()
        if any(w in kw for w in ["best", "top", "vs ", "review", "alternative", "comparison"]):
            return "COMMERCIAL"
        if any(w in kw for w in ["how to", "what is", "guide", "tutorial", "learn"]):
            return "INFORMATIONAL"
        if any(w in kw for w in ["buy", "price", "cost", "cheap", "deal", "free"]):
            return "TRANSACTIONAL"
        text_lower = article_text.lower()
        commercial_signals = ["best", "top", "compare", "vs ", "review", "alternative"]
        if any(s in text_lower for s in commercial_signals):
            return "COMMERCIAL"
        informational_signals = ["how to", "what is", "guide", "steps", "learn"]
        if any(s in text_lower for s in informational_signals):
            return "INFORMATIONAL"
        return "NAVIGATIONAL"

    @staticmethod
    def _intent_signals(text: str) -> list[str]:
        signals = []
        t = text.lower()
        if any(s in t for s in ["buy", "best", "top", "compare", "vs "]):
            signals.append("COMMERCIAL")
        if any(s in t for s in ["how to", "guide", "steps", "tutorial", "learn"]):
            signals.append("INFORMATIONAL")
        if any(s in t for s in ["price", "cost", "cheap", "deal", "free"]):
            signals.append("TRANSACTIONAL")
        return signals or ["NAVIGATIONAL"]

    @staticmethod
    def _find_competitor_weaknesses(competitor_texts: list[str], article_concepts: set[str]) -> list[str]:
        weaknesses = []
        if not competitor_texts:
            return weaknesses
        for text in competitor_texts:
            comp_concepts = SERPGapEngine._extract_key_concepts(text)
            missing = article_concepts - comp_concepts
            if missing:
                weaknesses.append(f"Missing coverage: {', '.join(sorted(missing)[:3])}")
        return weaknesses

    @staticmethod
    def _recommend_sections(missing_concepts: set[str], intent: str) -> list[str]:
        sections = []
        for concept in sorted(missing_concepts)[:10]:
            sections.append(f"Expand coverage of '{concept}'")
        if intent == "COMMERCIAL":
            sections.append("Add comparison table with pros/cons")
            sections.append("Include pricing breakdown section")
        elif intent == "INFORMATIONAL":
            sections.append("Add step-by-step tutorial section")
            sections.append("Include common mistakes section")
        return sections

    def get_telemetry(self) -> dict[str, Any]:
        with self._lock:
            if not self._reports:
                return {}
            avg_coverage = sum(r.semantic_coverage for r in self._reports) / len(self._reports)
            avg_entity_overlap = sum(r.entity_overlap for r in self._reports) / len(self._reports)
            avg_heading_overlap = sum(r.heading_overlap for r in self._reports) / len(self._reports)
            total_missing = sum(len(r.missing_concepts) for r in self._reports)
            return {
                "total_analyses": len(self._reports),
                "avg_semantic_coverage": round(avg_coverage, 3),
                "avg_entity_overlap": round(avg_entity_overlap, 3),
                "avg_heading_overlap": round(avg_heading_overlap, 3),
                "total_missing_concepts": total_missing,
            }


_GLOBAL_SERP_ENGINE = SERPGapEngine()


def get_serp_gap_engine() -> SERPGapEngine:
    return _GLOBAL_SERP_ENGINE


# ============================================================================
#  DIMENSION 2 — CITATION-BACKED GENERATION
# ============================================================================

@dataclass
class ClaimNode:
    claim_id: str
    claim_text: str
    claim_type: str  # "factual", "numerical", "comparison", "superlative"
    confidence: float
    source_urls: list[str] = field(default_factory=list)
    source_texts: list[str] = field(default_factory=list)
    is_supported: bool = False
    support_score: float = 0.0


@dataclass
class CitationGraph:
    """Directed graph mapping claims to their supporting sources."""
    claims: dict[str, ClaimNode] = field(default_factory=dict)
    edges: list[tuple[str, str, float]] = field(default_factory=list)  # claim_id -> source, weight


class CitationEngine:
    """Citation-backed generation with evidence tracking.

    Extracts claims from articles, finds supporting evidence in SERP data,
    builds a citation graph, and enforces citation requirements.
    """

    def __init__(self):
        self._graphs: list[CitationGraph] = []
        self._lock = threading.RLock()
        self._supported_claims = 0
        self._unsupported_claims = 0
        self._blocked_claims = 0

    def analyze(self, article: str, sources: list[dict] | None = None) -> CitationGraph:
        """Extract claims, find evidence, build citation graph."""
        text = re.sub(r'<[^>]+>', ' ', article)
        text = re.sub(r'\s+', ' ', text).strip()

        graph = CitationGraph()
        claims_data = self._extract_claims(text)

        for claim in claims_data:
            node = ClaimNode(
                claim_id=hashlib.md5(claim["text"].encode()).hexdigest()[:16],
                claim_text=claim["text"][:200],
                claim_type=claim["type"],
                confidence=claim.get("confidence", 0.5),
            )

            if sources:
                for source in sources:
                    source_text = source.get("text", source.get("snippet", ""))
                    match_score = self._match_claim_to_source(claim["text"], source_text)
                    if match_score > 0.3:
                        source_url = source.get("url", "")
                        node.source_urls.append(source_url)
                        node.source_texts.append(source_text[:200])
                        graph.edges.append((node.claim_id, source_url[:100], match_score))

            node.is_supported = len(node.source_urls) >= 1
            node.support_score = min(1.0, len(node.source_urls) * 0.3 + node.confidence * 0.4)
            graph.claims[node.claim_id] = node

        with self._lock:
            self._graphs.append(graph)
            supported = sum(1 for c in graph.claims.values() if c.is_supported)
            self._supported_claims += supported
            self._unsupported_claims += len(graph.claims) - supported

        return graph

    def _extract_claims(self, text: str) -> list[dict]:
        claims = []
        for m in re.finditer(r'\$[\d,]+(?:\.\d+)?(?:\s*/\s*(?:month|yr|year|user|seat))?', text):
            claims.append({"text": m.group(0), "type": "numerical", "confidence": 0.4})
        for m in re.finditer(r'(\d+[.,]?\d*)\s*(%|hours?|days?|weeks?|years?)', text, re.I):
            claims.append({"text": m.group(0), "type": "numerical", "confidence": 0.3})
        for m in re.finditer(
            r'(\w+(?:\s+\w+){0,3})\s+(is|was)\s+(better|worse|faster|slower|cheaper|'
            r'more expensive|more reliable)\s+than\s+(\w+(?:\s+\w+){0,3})',
            text, re.I
        ):
            claims.append({"text": m.group(0)[:150], "type": "comparison", "confidence": 0.3})
        for m in re.finditer(r'\b(according to|source:|studies show|research indicates)\b', text, re.I):
            context = text[max(0, m.start()-50):m.end()+100]
            claims.append({"text": context[:200], "type": "factual", "confidence": 0.5})
        for m in re.finditer(r'\b(best|leading|top-rated|#1|number one)\b', text, re.I):
            context = text[max(0, m.start()-60):m.end()+60]
            claims.append({"text": context[:150], "type": "superlative", "confidence": 0.2})
        return claims

    @staticmethod
    def _match_claim_to_source(claim_text: str, source_text: str) -> float:
        claim_words = set(re.findall(r'\b\w{4,}\b', claim_text.lower()))
        source_words = set(re.findall(r'\b\w{4,}\b', source_text.lower()))
        if not claim_words or not source_words:
            return 0.0
        overlap = len(claim_words & source_words)
        union = len(claim_words | source_words)
        return overlap / union

    def enforce_citations(self, article: str, graph: CitationGraph | None = None) -> dict[str, Any]:
        """Check citation enforcement. Returns block report."""
        if graph is None:
            graph = self._graphs[-1] if self._graphs else CitationGraph()
        unsupported = [c for c in graph.claims.values() if not c.is_supported]
        numerical_unsupported = [c for c in unsupported if c.claim_type == "numerical"]
        comparison_unsupported = [c for c in unsupported if c.claim_type == "comparison"]
        report = {
            "total_claims": len(graph.claims),
            "supported": sum(1 for c in graph.claims.values() if c.is_supported),
            "unsupported": len(unsupported),
            "blocked_numerical": len(numerical_unsupported),
            "blocked_comparisons": len(comparison_unsupported),
            "block": len(numerical_unsupported) > 0 or len(comparison_unsupported) > 2,
        }
        with self._lock:
            self._blocked_claims += report["blocked_numerical"]
        return report

    def get_telemetry(self) -> dict[str, Any]:
        with self._lock:
            total = self._supported_claims + self._unsupported_claims
            return {
                "total_claims_tracked": total,
                "supported_claims": self._supported_claims,
                "unsupported_claims": self._unsupported_claims,
                "support_rate": round(self._supported_claims / max(1, total), 3),
                "blocked_claims": self._blocked_claims,
                "graph_count": len(self._graphs),
            }


_GLOBAL_CITATION_ENGINE = CitationEngine()


def get_citation_engine() -> CitationEngine:
    return _GLOBAL_CITATION_ENGINE


# ============================================================================
#  DIMENSION 3 — RETRIEVAL-GROUNDED WRITING
# ============================================================================

@dataclass
class RetrievalInfluenceScore:
    keyword: str
    total_retrieved_chunks: int = 0
    chunks_used_in_article: int = 0
    reuse_ratio: float = 0.0
    semantic_overlap: float = 0.0
    term_overlap: float = 0.0
    hallucination_risk: float = 0.0
    grounded_score: float = 0.0


class RetrievalGroundedValidator:
    """Validate that retrieved evidence materially influences article generation.

    Measures:
    - How much retrieved evidence is actually reflected in output
    - Semantic overlap between evidence and article
    - Hallucination risk (claims without evidence support)
    """

    def __init__(self):
        self._scores: list[RetrievalInfluenceScore] = []
        self._lock = threading.RLock()

    def validate(
        self,
        keyword: str,
        article: str,
        retrieved_chunks: list[str],
    ) -> RetrievalInfluenceScore:
        """Compare retrieved evidence against generated article."""
        article_text = re.sub(r'<[^>]+>', ' ', article)
        article_words = set(re.findall(r'\b\w{4,}\b', article_text.lower()))
        article_key_terms = self._extract_key_terms(article_text)

        chunk_words_list = []
        used_chunks = 0
        for chunk in retrieved_chunks:
            chunk_clean = re.sub(r'<[^>]+>', ' ', chunk)
            chunk_words = set(re.findall(r'\b\w{4,}\b', chunk_clean.lower()))
            chunk_words_list.append(chunk_words)
            chunk_terms = self._extract_key_terms(chunk_clean)
            if article_key_terms & chunk_terms:
                used_chunks += 1

        if not chunk_words_list or not article_words:
            return RetrievalInfluenceScore(keyword=keyword)

        all_chunk_words = set()
        for cw in chunk_words_list:
            all_chunk_words.update(cw)

        term_overlap = len(all_chunk_words & article_words) / max(1, len(all_chunk_words | article_words))
        reuse_ratio = used_chunks / max(1, len(retrieved_chunks))

        article_claims = set(re.findall(r'\$[\d,]+\.?\d*|\d+%|\d+x\s*faster', article, re.I))
        evidence_claims = set()
        for chunk in retrieved_chunks:
            evidence_claims.update(re.findall(r'\$[\d,]+\.?\d*|\d+%|\d+x\s*faster', chunk, re.I))
        hallucinated = article_claims - evidence_claims
        hallucination_risk = len(hallucinated) / max(1, len(article_claims))

        grounded_score = (reuse_ratio * 0.3 + term_overlap * 0.3 + (1 - hallucination_risk) * 0.4)

        score = RetrievalInfluenceScore(
            keyword=keyword,
            total_retrieved_chunks=len(retrieved_chunks),
            chunks_used_in_article=used_chunks,
            reuse_ratio=round(reuse_ratio, 3),
            semantic_overlap=round(term_overlap, 3),
            term_overlap=round(term_overlap, 3),
            hallucination_risk=round(hallucination_risk, 3),
            grounded_score=round(grounded_score, 3),
        )

        with self._lock:
            self._scores.append(score)

        return score

    @staticmethod
    def _extract_key_terms(text: str) -> set[str]:
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        freq = Counter(words)
        stop = {
            "the", "this", "that", "with", "from", "have", "been", "were",
            "their", "what", "which", "when", "where", "more", "some",
        }
        return {w for w, c in freq.items() if w not in stop and c >= 1} | set(
            re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', text)
        )

    def get_telemetry(self) -> dict[str, Any]:
        with self._lock:
            if not self._scores:
                return {}
            avg_reuse = sum(s.reuse_ratio for s in self._scores) / len(self._scores)
            avg_grounded = sum(s.grounded_score for s in self._scores) / len(self._scores)
            avg_hallucination = sum(s.hallucination_risk for s in self._scores) / len(self._scores)
            return {
                "total_validations": len(self._scores),
                "avg_reuse_ratio": round(avg_reuse, 3),
                "avg_grounded_score": round(avg_grounded, 3),
                "avg_hallucination_risk": round(avg_hallucination, 3),
            }


_GLOBAL_RETRIEVAL_VALIDATOR = RetrievalGroundedValidator()


def get_retrieval_validator() -> RetrievalGroundedValidator:
    return _GLOBAL_RETRIEVAL_VALIDATOR


# ============================================================================
#  DIMENSION 4 — HUMAN EDITORIAL REWRITER
# ============================================================================

@dataclass
class HumanizationReport:
    original_word_count: int = 0
    rewritten_word_count: int = 0
    sentence_openings_diversified: int = 0
    repetitive_cadence_fixes: int = 0
    transition_improvements: int = 0
    ai_phrase_removals: int = 0
    readability_improvement: float = 0.0
    changes_made: int = 0


class HumanEditorialRewriter:
    """Post-generation editorial layer that eliminates AI-detectable patterns.

    Detects and fixes:
    - Repeated sentence openings
    - Repetitive transition words
    - Overused AI phrases
    - Rhythmic paragraph uniformity
    - Unnatural list patterns
    - Template artifacts
    """

    _AI_PHRASES = [
        "in the ever-evolving", "when it comes to", "it is important to note that",
        "it is worth mentioning", "it goes without saying", "last but not least",
        "all in all", "in conclusion", "in summary", "to summarize",
        "it is crucial to", "it is essential to", "it is necessary to",
        "there are many factors", "there are several reasons",
        "one of the most important", "one of the key",
        "as previously mentioned", "as discussed earlier",
        "in today's digital world", "in today's fast-paced",
        "a wide range of", "a variety of", "numerous options",
        "it offers", "it provides", "it allows users to",
        "it boasts", "it comes with", "it features",
        "the platform offers", "the tool offers", "the software offers",
    ]

    _BANNED_OPENERS = [
        "in this article", "this article will", "we will explore",
        "we will discuss", "we will look at", "let's dive",
        "let us explore", "without further ado",
    ]

    _TRANSITION_FLAWS = {
        "firstly": "First", "secondly": "Second", "thirdly": "Third",
        "lastly": "Finally",
    }

    def __init__(self):
        self._reports: list[HumanizationReport] = []
        self._lock = threading.RLock()

    def rewrite(self, article: str) -> tuple[str, HumanizationReport]:
        """Apply editorial rewrites to eliminate AI-detectable patterns."""
        report = HumanizationReport(
            original_word_count=len(article.split()),
        )
        changes = 0

        # 1. Fix banned sentence openers
        article, opener_fixes = self._fix_openers(article)
        changes += opener_fixes
        report.sentence_openings_diversified = opener_fixes

        # 2. Remove AI phrases
        article, phrase_removals = self._remove_ai_phrases(article)
        changes += phrase_removals
        report.ai_phrase_removals = phrase_removals

        # 3. Fix flawed transitions
        article, transition_fixes = self._fix_transitions(article)
        changes += transition_fixes
        report.transition_improvements = transition_fixes

        # 4. Fix repetitive cadence
        article, cadence_fixes = self._fix_cadence(article)
        changes += cadence_fixes
        report.repetitive_cadence_fixes = cadence_fixes

        # 5. Diversify sentence lengths
        article, _ = self._diversify_sentence_lengths(article)

        report.rewritten_word_count = len(article.split())
        report.changes_made = changes

        if report.original_word_count > 0:
            report.readability_improvement = round(
                (report.changes_made / report.original_word_count) * 100, 1
            )

        with self._lock:
            self._reports.append(report)

        return article, report

    def _fix_openers(self, text: str) -> tuple[str, int]:
        fixes = 0
        replacements = {
            "in this article, i will": "This guide",
            "in this article, we will": "This guide",
            "this article will": "This guide",
            "we will explore": "This covers",
            "we will discuss": "This covers",
            "we will look at": "This examines",
            "let's dive into": "Here is",
            "let us explore": "Here is",
            "without further ado": "",
        }
        for pattern, replacement in replacements.items():
            count = text.lower().count(pattern.lower())
            if count > 0:
                text = re.sub(re.escape(pattern), replacement, text, flags=re.IGNORECASE)
                fixes += count
        return text, fixes

    def _remove_ai_phrases(self, text: str) -> tuple[str, int]:
        removals = 0
        for phrase in self._AI_PHRASES:
            count = text.lower().count(phrase.lower())
            if count > 0:
                text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
                removals += count
        text = re.sub(r'\s+', ' ', text).strip()
        return text, removals

    def _fix_transitions(self, text: str) -> tuple[str, int]:
        fixes = 0
        for flawed, correct in self._TRANSITION_FLAWS.items():
            pattern = re.compile(r'\b' + re.escape(flawed) + r'\b', re.IGNORECASE)
            count = len(pattern.findall(text))
            if count > 0:
                text = pattern.sub(correct, text)
                fixes += count
        return text, fixes

    def _fix_cadence(self, text: str) -> tuple[str, int]:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        fixes = 0
        if len(sentences) < 3:
            return text, 0

        prev_start_words = ""
        result = []
        for i, sentence in enumerate(sentences):
            words = sentence.split()
            if not words:
                result.append(sentence)
                continue
            first_word = words[0].lower().strip("'\"")
            if i > 0 and first_word == prev_start_words and len(first_word) > 2:
                alt_openers = ["Additionally,", "Moreover,", "Furthermore,", "Also,",
                               "Beyond that,", "On top of that,", "In addition,"]
                if i < len(sentences) - 1:
                    sentence = random.choice(alt_openers) + " " + " ".join(words[1:])
                    fixes += 1
                prev_start_words = ""
            else:
                prev_start_words = first_word
            result.append(sentence)

        return " ".join(result), fixes

    @staticmethod
    def _diversify_sentence_lengths(text: str) -> tuple[str, int]:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) < 4:
            return text, 0
        lengths = [len(s.split()) for s in sentences]
        avg_len = sum(lengths) / len(lengths)
        changes = 0
        result = []
        for i, sentence in enumerate(sentences):
            if lengths[i] > avg_len * 1.5 and i < len(sentences) - 1:
                mid = len(sentence) // 2
                split_point = sentence.rfind(" ", 0, mid)
                if split_point > 0:
                    result.append(sentence[:split_point] + ".")
                    result.append(sentence[split_point + 1:].capitalize())
                    changes += 1
                    continue
            result.append(sentence)
        return " ".join(result), changes

    def detect_ai_patterns(self, text: str) -> dict[str, Any]:
        """Detect AI-detectable patterns without modifying text."""
        sentences = re.split(r'(?<=[.!?])\s+', text)

        start_words = []
        for s in sentences:
            words = s.split()
            if words:
                start_words.append(words[0].lower().strip("'\""))

        start_word_freq = Counter(start_words)
        repetitive_start_rate = sum(c - 1 for c in start_word_freq.values() if c > 1) / max(1, len(sentences))

        sentence_lengths = [len(s.split()) for s in sentences if s.strip()]
        length_std = 0
        if len(sentence_lengths) > 1:
            mean = sum(sentence_lengths) / len(sentence_lengths)
            variance = sum((x - mean) ** 2 for x in sentence_lengths) / len(sentence_lengths)
            length_std = math.sqrt(variance)

        paragraph_lengths = []
        for para in re.split(r'\n\s*\n', text):
            words = len(para.split())
            if words > 5:
                paragraph_lengths.append(words)
        para_uniformity = 0
        if len(paragraph_lengths) > 1:
            mean = sum(paragraph_lengths) / len(paragraph_lengths)
            para_uniformity = sum(abs(p - mean) for p in paragraph_lengths) / len(paragraph_lengths) / max(1, mean)

        ai_phrase_count = sum(text.lower().count(p.lower()) for p in self._AI_PHRASES)

        from string import punctuation
        punct_counts = Counter(text)
        punct_diversity = len([c for c in punct_counts if c in punctuation]) / max(1, len(punctuation))

        report = {
            "total_sentences": len(sentences),
            "repetitive_start_rate": round(repetitive_start_rate, 3),
            "sentence_length_std": round(length_std, 1),
            "paragraph_uniformity": round(para_uniformity, 3),
            "ai_phrase_count": ai_phrase_count,
            "punctuation_diversity": round(punct_diversity, 3),
            "ai_detection_risk": round(
                repetitive_start_rate * 0.3
                + (1 - min(1, length_std / 10)) * 0.3
                + min(1, ai_phrase_count / 10) * 0.2
                + para_uniformity * 0.2,
                3,
            ),
        }
        return report

    def get_telemetry(self) -> dict[str, Any]:
        with self._lock:
            if not self._reports:
                return {}
            avg_fixes = sum(r.changes_made for r in self._reports) / len(self._reports)
            avg_openers = sum(r.sentence_openings_diversified for r in self._reports) / len(self._reports)
            total_phrases = sum(r.ai_phrase_removals for r in self._reports)
            return {
                "total_rewrites": len(self._reports),
                "avg_changes_per_article": round(avg_fixes, 1),
                "avg_opener_fixes": round(avg_openers, 1),
                "total_ai_phrases_removed": total_phrases,
            }


_GLOBAL_HUMAN_REWRITER = HumanEditorialRewriter()


def get_human_rewriter() -> HumanEditorialRewriter:
    return _GLOBAL_HUMAN_REWRITER


# ============================================================================
#  DIMENSION 5 — CONVERSION-AWARE OPTIMIZER
# ============================================================================

@dataclass
class ConversionReport:
    keyword: str = ""
    intent: str = ""
    ctas_found: int = 0
    ctas_effective: int = 0
    cta_effectiveness_score: float = 0.0
    friction_points: list[str] = field(default_factory=list)
    engagement_score: float = 0.0
    conversion_sections: int = 0
    conversion_opportunities: list[str] = field(default_factory=list)


class ConversionOptimizer:
    """Analyzes and optimizes content for conversion.

    Models:
    - CTA placement and effectiveness
    - User intent stage
    - Friction points
    - Engagement flow
    - Conversion section optimization
    """

    _HIGH_INTENT_TERMS = [
        "buy", "pricing", "plans", "subscribe", "sign up", "get started",
        "free trial", "download", "order", "purchase", "checkout",
    ]
    _MEDIUM_INTENT_TERMS = [
        "compare", "vs ", "versus", "alternative", "best", "top", "review",
        "features", "benefits", "pros and cons",
    ]
    _CTA_PATTERNS = re.compile(
        r'(get started|sign up|try free|start free trial|download now|'
        r'buy now|shop now|learn more|get started today|'
        r'click here|subscribe|start now|get it now|try it now)',
        re.IGNORECASE
    )

    def __init__(self):
        self._reports: list[ConversionReport] = []
        self._lock = threading.RLock()

    def analyze(self, keyword: str, article: str) -> ConversionReport:
        text_lower = article.lower()
        intent = self._classify_intent(keyword, text_lower)

        ctas = list(self._CTA_PATTERNS.finditer(text_lower))
        cta_positions = [m.start() for m in ctas]
        total_len = len(article)
        effective_ctas = 0
        for pos in cta_positions:
            rel_pos = pos / max(1, total_len)
            # CTAs at 40-70% (after problem explained, before conclusion) = effective
            if 0.3 <= rel_pos <= 0.8:
                effective_ctas += 1

        friction_points = []
        if self._CTA_PATTERNS.search(text_lower) and "pricing" not in text_lower and "price" not in text_lower:
            friction_points.append("CTA without pricing context")
        if intent in ("COMMERCIAL", "TRANSACTIONAL"):
            if not re.search(r'<table', article):
                friction_points.append("Commercial article missing comparison table")
            if not re.search(r'(pros?|cons?|advantages?|disadvantages?)', text_lower):
                friction_points.append("Missing pros/cons analysis")
            if not re.search(r'(recommend|best for|ideal for|perfect for)', text_lower):
                friction_points.append("Missing recommendation")

        engagement_score = self._calculate_engagement(article, text_lower)

        conversion_opportunities = []
        if intent in ("COMMERCIAL", "TRANSACTIONAL"):
            if "comparison table" not in text_lower:
                conversion_opportunities.append("Add comparison table near 40% mark")
            if "pricing" not in text_lower:
                conversion_opportunities.append("Add pricing section")
            if len(ctas) < 2:
                conversion_opportunities.append("Add mid-article CTA")
        elif intent == "INFORMATIONAL":
            if "newsletter" not in text_lower and "subscribe" not in text_lower:
                conversion_opportunities.append("Add newsletter subscription CTA")
            if "free guide" not in text_lower and "free resource" not in text_lower:
                conversion_opportunities.append("Add lead magnet offer")

        report = ConversionReport(
            keyword=keyword,
            intent=intent,
            ctas_found=len(ctas),
            ctas_effective=effective_ctas,
            cta_effectiveness_score=round(effective_ctas / max(1, len(ctas)), 3),
            friction_points=friction_points,
            engagement_score=round(engagement_score, 3),
            conversion_sections=len([s for s in ["pricing", "comparison", "testimonial",
                                                   "faq", "cta"] if s in text_lower]),
            conversion_opportunities=conversion_opportunities[:5],
        )

        with self._lock:
            self._reports.append(report)

        return report

    def _classify_intent(self, keyword: str, text_lower: str) -> str:
        kw = keyword.lower()
        if any(t in kw for t in self._HIGH_INTENT_TERMS):
            return "TRANSACTIONAL"
        if any(t in kw for t in self._MEDIUM_INTENT_TERMS):
            return "COMMERCIAL"
        if any(t in text_lower for t in self._HIGH_INTENT_TERMS):
            return "TRANSACTIONAL"
        if any(t in text_lower for t in self._MEDIUM_INTENT_TERMS):
            return "COMMERCIAL"
        informational_signals = ["how to", "what is", "guide", "tutorial", "learn"]
        if any(s in kw for s in informational_signals):
            return "INFORMATIONAL"
        return "NAVIGATIONAL"

    @staticmethod
    def _calculate_engagement(article: str, text_lower: str) -> float:
        score = 0.0
        if re.search(r'<table', article):
            score += 0.15
        if re.search(r'<img', article):
            score += 0.10
        if re.search(r'<blockquote', article):
            score += 0.10
        if re.search(r'<ul', article) or re.search(r'<ol', article):
            score += 0.10
        if re.search(r'class="faq', text_lower):
            score += 0.15
        if re.search(r'class="quick-answer-box"', text_lower):
            score += 0.10
        if 'verdict' in text_lower or 'winner' in text_lower or 'recommend' in text_lower:
            score += 0.10
        word_count = len(article.split())
        if word_count >= 2000:
            score += 0.15
        elif word_count >= 1500:
            score += 0.10
        return min(1.0, score)

    def optimize_cta(self, article: str, keyword: str) -> str:
        """Inject CTAs where missing and appropriate."""
        text_lower = article.lower()
        intent = self._classify_intent(keyword, text_lower)
        if intent not in ("COMMERCIAL", "TRANSACTIONAL"):
            return article
        ctas_found = self._CTA_PATTERNS.findall(text_lower)
        if len(ctas_found) >= 2:
            return article
        safe_ctas = [
            '<p><strong>Ready to choose?</strong> <a href="[LINK: best option]" target="_blank" rel="nofollow noopener">Compare your top options here</a> and find the right fit for your needs.</p>',
            '<p><strong>Not sure which is right for you?</strong> Check our <a href="[LINK: comparison]" target="_blank" rel="nofollow noopener">detailed comparison guide</a> for personalized recommendations.</p>',
        ]
        insert_point = article.rfind("</article>")
        if insert_point < 0:
            insert_point = article.rfind("</body>")
        if insert_point < 0:
            return article
        cta = safe_ctas[0] if "ready" not in text_lower else safe_ctas[1]
        article = article[:insert_point] + cta + article[insert_point:]
        return article

    def get_telemetry(self) -> dict[str, Any]:
        with self._lock:
            if not self._reports:
                return {}
            avg_cta_effect = sum(r.cta_effectiveness_score for r in self._reports) / len(self._reports)
            avg_engagement = sum(r.engagement_score for r in self._reports) / len(self._reports)
            total_frictions = sum(len(r.friction_points) for r in self._reports)
            return {
                "total_analyses": len(self._reports),
                "avg_cta_effectiveness": round(avg_cta_effect, 3),
                "avg_engagement_score": round(avg_engagement, 3),
                "total_friction_points": total_frictions,
            }


_GLOBAL_CONVERSION_OPTIMIZER = ConversionOptimizer()


def get_conversion_optimizer() -> ConversionOptimizer:
    return _GLOBAL_CONVERSION_OPTIMIZER


# ============================================================================
#  DIMENSION 6 — TOPIC AUTHORITY MEMORY
# ============================================================================

@dataclass
class EntityNode:
    name: str
    niche: str
    mention_count: int = 0
    article_count: int = 0
    avg_quality_score: float = 0.0
    relationships: dict[str, float] = field(default_factory=dict)  # entity_name -> strength


@dataclass
class NicheExpertise:
    niche: str
    total_articles: int = 0
    avg_quality: float = 0.0
    entity_count: int = 0
    concept_diversity: float = 0.0
    authority_score: float = 0.0


class TopicAuthorityGraph:
    """Cross-article knowledge accumulation.

    Builds:
    - Entity knowledge graph
    - Niche expertise scoring
    - Authority depth tracking
    - Concept reinforcement weighting
    """

    def __init__(self):
        self._entities: dict[str, EntityNode] = {}
        self._niches: dict[str, NicheExpertise] = {}
        self._lock = threading.RLock()

    def ingest_article(self, keyword: str, article: str, niche: str, quality_score: int) -> dict[str, Any]:
        """Process article to update entity knowledge and niche expertise."""
        text = re.sub(r'<[^>]+>', ' ', article).lower()
        entities_found = set()
        for m in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b', article):
            entity_name = m.group(1).strip()
            if len(entity_name) > 3 and not any(c.isdigit() for c in entity_name):
                entities_found.add(entity_name)

        with self._lock:
            for entity_name in entities_found:
                if entity_name not in self._entities:
                    self._entities[entity_name] = EntityNode(
                        name=entity_name, niche=niche
                    )
                node = self._entities[entity_name]
                node.mention_count += 1
                if quality_score > 0:
                    node.avg_quality_score = (
                        (node.avg_quality_score * node.article_count + quality_score)
                        / (node.article_count + 1)
                    )
                node.article_count += 1

            for e1 in entities_found:
                for e2 in entities_found:
                    if e1 < e2:
                        self._entities[e1].relationships[e2] = (
                            self._entities[e1].relationships.get(e2, 0) + 1
                        )
                        self._entities[e2].relationships[e1] = (
                            self._entities[e2].relationships.get(e1, 0) + 1
                        )

            if niche not in self._niches:
                self._niches[niche] = NicheExpertise(niche=niche)
            exp = self._niches[niche]
            exp.total_articles += 1
            exp.entity_count = len(
                [e for e in self._entities.values() if e.niche == niche]
            )
            if quality_score > 0:
                exp.avg_quality = (
                    (exp.avg_quality * (exp.total_articles - 1) + quality_score)
                    / exp.total_articles
                )
            exp.concept_diversity = exp.entity_count / max(1, exp.total_articles)
            exp.authority_score = min(1.0, (
                exp.total_articles * 0.05
                + exp.avg_quality / 100 * 0.3
                + exp.entity_count * 0.02
                + exp.concept_diversity * 0.1
            ))

        return {
            "entities_added": len(entities_found),
            "niche_authority": round(self._niches.get(niche, NicheExpertise(niche)).authority_score, 3),
        }

    def get_entity_knowledge(self, entity_name: str) -> EntityNode | None:
        with self._lock:
            return self._entities.get(entity_name)

    def get_niche_expertise(self, niche: str) -> NicheExpertise | None:
        with self._lock:
            return self._niches.get(niche)

    def get_related_entities(self, entity_name: str, top_n: int = 5) -> list[tuple[str, float]]:
        with self._lock:
            node = self._entities.get(entity_name)
            if not node:
                return []
            related = sorted(node.relationships.items(), key=lambda x: x[1], reverse=True)
            return related[:top_n]

    def get_concept_reinforcement(self, text: str) -> dict[str, float]:
        """Score how well text uses reinforced (proven) concepts."""
        text_lower = text.lower()
        total_score = 0.0
        matched = 0
        with self._lock:
            for entity_name, node in self._entities.items():
                if entity_name.lower() in text_lower:
                    score = min(1.0, node.avg_quality_score / 100 + node.article_count * 0.1)
                    total_score += score
                    matched += 1
        return {
            "reinforced_concepts": matched,
            "reinforcement_score": round(total_score / max(1, matched), 3) if matched else 0.0,
        }

    def get_telemetry(self) -> dict[str, Any]:
        with self._lock:
            niche_authorities = {
                n: round(e.authority_score, 3)
                for n, e in self._niches.items()
            }
            return {
                "total_entities": len(self._entities),
                "total_niches": len(self._niches),
                "niche_authorities": niche_authorities,
                "total_relationships": sum(
                    len(n.relationships) for n in self._entities.values()
                ),
            }


_GLOBAL_AUTHORITY_GRAPH = TopicAuthorityGraph()


def get_authority_graph() -> TopicAuthorityGraph:
    return _GLOBAL_AUTHORITY_GRAPH


# ============================================================================
#  DIMENSION 7 — AI DETECTION RESISTANCE
# ============================================================================

@dataclass
class AIPatternReport:
    burstiness_score: float = 0.0
    perplexity_estimate: float = 0.0
    cadence_diversity: float = 0.0
    sentence_length_distribution: dict = field(default_factory=dict)
    entropy_score: float = 0.0
    paragraph_entropy: float = 0.0
    overall_human_score: float = 0.0
    issues: list[str] = field(default_factory=list)


class AIDetectionResistance:
    """Analyzes and improves AI detection resistance.

    Uses statistical patterns (not ML) to detect and diversify
    AI-detectable writing patterns.
    """

    def __init__(self):
        self._reports: list[AIPatternReport] = []
        self._lock = threading.RLock()

    def analyze(self, text: str) -> AIPatternReport:
        """Analyze text for AI-detectable patterns."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        words = text.split()

        if len(sentences) < 3:
            return AIPatternReport()

        sentence_lengths = [len(s.split()) for s in sentences if s.strip()]
        if not sentence_lengths:
            return AIPatternReport()

        burstiness = self._calculate_burstiness(sentence_lengths)
        perplexity_est = self._estimate_perplexity(text)
        cadence_div = self._cadence_diversity(sentences)
        entropy = self._text_entropy(text)
        para_entropy = self._paragraph_entropy(text)

        length_counts = Counter(sentence_lengths)
        total = len(sentence_lengths)
        length_dist = {
            "1-5": round(sum(c for k, c in length_counts.items() if k <= 5) / total, 3),
            "6-15": round(sum(c for k, c in length_counts.items() if 6 <= k <= 15) / total, 3),
            "16-25": round(sum(c for k, c in length_counts.items() if 16 <= k <= 25) / total, 3),
            "26+": round(sum(c for k, c in length_counts.items() if k > 25) / total, 3),
        }

        issues = []
        if burstiness < 0.3:
            issues.append("Low burstiness — sentence lengths too uniform")
        if cadence_div < 0.3:
            issues.append("Low cadence diversity — repetitive rhythm")
        if entropy < 3.5:
            issues.append("Low lexical entropy — limited vocabulary range")
        if length_dist.get("1-5", 0) < 0.05:
            issues.append("No short sentences — missing sentence variety")
        if length_dist.get("26+", 0) < 0.05:
            issues.append("No long sentences — missing complex constructions")

        human_score = (
            min(1.0, burstiness * 0.3)
            + min(1.0, cadence_div * 0.25)
            + min(1.0, entropy / 5 * 0.25)
            + min(1.0, para_entropy * 0.2)
        )

        report = AIPatternReport(
            burstiness_score=round(burstiness, 3),
            perplexity_estimate=round(perplexity_est, 3),
            cadence_diversity=round(cadence_div, 3),
            sentence_length_distribution=length_dist,
            entropy_score=round(entropy, 3),
            paragraph_entropy=round(para_entropy, 3),
            overall_human_score=round(human_score, 3),
            issues=issues[:3],
        )

        with self._lock:
            self._reports.append(report)

        return report

    @staticmethod
    def _calculate_burstiness(lengths: list[int]) -> float:
        """Calculate burstiness: variation in sentence lengths.
        Higher = more human-like variation."""
        if len(lengths) < 2:
            return 0.0
        mean = sum(lengths) / len(lengths)
        if mean == 0:
            return 0.0
        variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
        std = math.sqrt(variance)
        return std / mean

    @staticmethod
    def _estimate_perplexity(text: str) -> float:
        """Estimate text perplexity using n-gram diversity as proxy."""
        words = re.findall(r'\b\w+\b', text.lower())
        if len(words) < 10:
            return 0.0
        unigrams = len(set(words))
        bigrams = set()
        for i in range(len(words) - 1):
            bigrams.add(f"{words[i]} {words[i+1]}")
        bigram_count = len(bigrams)
        total_bigrams = max(1, len(words) - 1)
        diversity = (unigrams / len(words)) * 0.4 + (bigram_count / total_bigrams) * 0.6
        return diversity * 10

    @staticmethod
    def _cadence_diversity(sentences: list[str]) -> float:
        """Score how diverse sentence rhythms are."""
        patterns = []
        for s in sentences:
            words = s.split()
            if len(words) < 3:
                continue
            lengths = [len(w.strip("'\".,!?;:")) for w in words[:4]]
            pattern = "".join("l" if l > 5 else "s" for l in lengths)
            patterns.append(pattern)
        if not patterns:
            return 0.0
        unique = len(set(patterns))
        return unique / min(len(patterns), 5)

    @staticmethod
    def _text_entropy(text: str) -> float:
        """Calculate Shannon entropy of character distribution."""
        text = text.lower()
        if not text:
            return 0.0
        freq: Counter = Counter(text)
        total = len(text)
        entropy = 0.0
        for count in freq.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy

    @staticmethod
    def _paragraph_entropy(text: str) -> float:
        """Calculate entropy of paragraph lengths."""
        paras = [p for p in re.split(r'\n\s*\n', text) if len(p.split()) > 5]
        if len(paras) < 2:
            return 0.0
        lengths = [len(p.split()) for p in paras]
        mean = sum(lengths) / len(lengths)
        if mean == 0:
            return 0.0
        variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
        return math.sqrt(variance) / mean

    def suggest_improvements(self, report: AIPatternReport) -> list[str]:
        suggestions = []
        if report.burstiness_score < 0.4:
            suggestions.append("Mix very short (3-5 word) sentences with longer ones")
        if report.cadence_diversity < 0.4:
            suggestions.append("Vary sentence starting words and structures")
        if report.entropy_score < 4.0:
            suggestions.append("Use more varied vocabulary and specific terminology")
        dist = report.sentence_length_distribution
        if dist.get("1-5", 0) < 0.03:
            suggestions.append("Add punchy short sentences for emphasis")
        if dist.get("26+", 0) < 0.03:
            suggestions.append("Occasionally combine ideas into longer sentences")
        return suggestions[:5]

    def get_telemetry(self) -> dict[str, Any]:
        with self._lock:
            if not self._reports:
                return {}
            avg_human = sum(r.overall_human_score for r in self._reports) / len(self._reports)
            avg_burstiness = sum(r.burstiness_score for r in self._reports) / len(self._reports)
            avg_entropy = sum(r.entropy_score for r in self._reports) / len(self._reports)
            return {
                "total_analyses": len(self._reports),
                "avg_human_score": round(avg_human, 3),
                "avg_burstiness": round(avg_burstiness, 3),
                "avg_entropy": round(avg_entropy, 3),
            }


_GLOBAL_AI_RESISTANCE = AIDetectionResistance()


def get_ai_resistance() -> AIDetectionResistance:
    return _GLOBAL_AI_RESISTANCE


# ============================================================================
#  DIMENSION 8 — AUTONOMOUS QUALITY EVOLUTION
# ============================================================================

@dataclass
class PatternRecord:
    pattern_type: str  # "opener", "structure", "cta", "section", "faq_count", "tone"
    pattern_value: str
    success_count: int = 0
    failure_count: int = 0
    total_reward: float = 0.0
    avg_reward: float = 0.0
    last_seen: float = field(default_factory=time.time)
    niche: str = "general"
    influence_weight: float = 1.0


class PatternPerformanceTracker:
    """Real feedback loop for autonomous quality evolution.

    Tracks:
    - Article performance (rankings, quality scores)
    - Which patterns succeed/fail
    - Adaptive weighting of successful patterns
    - Automatic decay of failing patterns
    """

    def __init__(self):
        self._patterns: dict[str, PatternRecord] = {}
        self._article_history: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        self._max_history = 200
        self._decay_rate = 0.1  # per cycle for failing patterns
        self._boost_rate = 0.05  # per cycle for winning patterns

    def record_article(self, keyword: str, article: str, quality_score: int,
                       niche: str = "general", reward: float = 0.0) -> dict[str, Any]:
        """Record article and extract patterns for evolution."""
        text_lower = article.lower()

        patterns_found: list[tuple[str, str]] = []

        # Extract opener pattern
        first_sentence = article.split(".")[0] if "." in article else article[:100]
        patterns_found.append(("opener", first_sentence[:80]))

        # Extract structure pattern
        h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', article, re.DOTALL | re.IGNORECASE)
        h2_count = len(h2s)
        if h2_count > 0:
            patterns_found.append(("structure", f"{h2_count}_h2_sections"))

        # Extract CTA pattern
        if re.search(r'(get started|sign up|try free|buy now|subscribe)', text_lower):
            patterns_found.append(("cta", "has_cta"))
        else:
            patterns_found.append(("cta", "no_cta"))

        # Extract FAQ pattern
        faq_count = len(re.findall(r'class="faq-item"', article))
        if faq_count >= 5:
            patterns_found.append(("faq_count", f"faq_{faq_count}"))

        # Extract table pattern
        if '<table' in article:
            patterns_found.append(("structure", "has_comparison_table"))

        # Extract tone pattern (sentence length as proxy)
        sentences = re.split(r'(?<=[.!?])\s+', article)
        avg_sent_len = sum(len(s.split()) for s in sentences) / max(1, len(sentences))
        if avg_sent_len > 20:
            patterns_found.append(("tone", "dense_prose"))
        else:
            patterns_found.append(("tone", "conversational"))

        record = {"keyword": keyword, "quality_score": quality_score,
                  "niche": niche, "reward": reward, "patterns": dict(patterns_found),
                  "word_count": len(article.split()), "timestamp": time.time()}

        with self._lock:
            self._article_history.append(record)
            if len(self._article_history) > self._max_history:
                self._article_history = self._article_history[-self._max_history:]

            is_success = quality_score >= 70 or reward > 0
            for ptype, pvalue in patterns_found:
                key = f"{ptype}:{pvalue}"
                if key not in self._patterns:
                    self._patterns[key] = PatternRecord(
                        pattern_type=ptype, pattern_value=pvalue[:100], niche=niche
                    )
                p = self._patterns[key]
                if is_success:
                    p.success_count += 1
                    p.total_reward += reward + (quality_score / 100)
                    p.influence_weight = min(3.0, p.influence_weight + self._boost_rate)
                else:
                    p.failure_count += 1
                    p.total_reward += reward - 0.5
                    p.influence_weight = max(0.1, p.influence_weight - self._decay_rate)
                p.last_seen = time.time()
                p.avg_reward = p.total_reward / max(1, p.success_count + p.failure_count)

        return {
            "patterns_recorded": len(patterns_found),
            "niche": niche,
            "is_success": quality_score >= 70 or reward > 0,
        }

    def get_top_patterns(self, pattern_type: str | None = None,
                         niche: str | None = None, top_n: int = 5) -> list[PatternRecord]:
        """Get highest-performing patterns for a type and niche."""
        with self._lock:
            results = list(self._patterns.values())

        if pattern_type:
            results = [p for p in results if p.pattern_type == pattern_type]
        if niche:
            results = [p for p in results if p.niche == niche or p.niche == "general"]

        results.sort(key=lambda p: p.avg_reward * p.influence_weight, reverse=True)
        return results[:top_n]

    def get_failing_patterns(self, threshold: float = -0.2) -> list[PatternRecord]:
        """Get patterns that are underperforming and should decay."""
        with self._lock:
            return [
                p for p in self._patterns.values()
                if p.avg_reward < threshold or p.failure_count > p.success_count * 2
            ]

    def adapt_strategy(self, niche: str) -> dict[str, Any]:
        """Generate adaptation recommendations based on pattern history."""
        top_openers = self.get_top_patterns("opener", niche, top_n=3)
        top_structures = self.get_top_patterns("structure", niche, top_n=3)
        failing = self.get_failing_patterns()

        recommendations = {}

        if top_openers:
            recommendations["recommended_opener_style"] = top_openers[0].pattern_value[:60]

        if top_structures:
            recommendations["recommended_structure"] = top_structures[0].pattern_value

        if failing:
            failing_types = list(set(p.pattern_type for p in failing))
            recommendations["patterns_to_avoid"] = failing_types

        return recommendations

    def get_telemetry(self) -> dict[str, Any]:
        with self._lock:
            if not self._patterns:
                return {}
            total_patterns = len(self._patterns)
            high_performers = sum(1 for p in self._patterns.values() if p.avg_reward > 0.3)
            low_performers = sum(1 for p in self._patterns.values() if p.avg_reward < -0.2)
            by_type: Counter = Counter(p.pattern_type for p in self._patterns.values())
            avg_weight = sum(p.influence_weight for p in self._patterns.values()) / total_patterns
            return {
                "total_patterns_tracked": total_patterns,
                "high_performers": high_performers,
                "low_performers": low_performers,
                "patterns_by_type": dict(by_type),
                "avg_influence_weight": round(avg_weight, 3),
                "article_history_size": len(self._article_history),
            }

    def reset_niche(self, niche: str) -> int:
        """Reset patterns for a niche (for testing/cleanup)."""
        with self._lock:
            to_remove = [k for k, p in self._patterns.items() if p.niche == niche]
            for k in to_remove:
                del self._patterns[k]
            return len(to_remove)


_GLOBAL_PATTERN_TRACKER = PatternPerformanceTracker()


def get_pattern_tracker() -> PatternPerformanceTracker:
    return _GLOBAL_PATTERN_TRACKER


# ============================================================================
#  AGGREGATED TELEMETRY
# ============================================================================

def get_intelligence_telemetry() -> dict[str, Any]:
    return {
        "serp_gap": get_serp_gap_engine().get_telemetry(),
        "citation": get_citation_engine().get_telemetry(),
        "retrieval": get_retrieval_validator().get_telemetry(),
        "human_rewriter": get_human_rewriter().get_telemetry(),
        "conversion": get_conversion_optimizer().get_telemetry(),
        "authority": get_authority_graph().get_telemetry(),
        "ai_resistance": get_ai_resistance().get_telemetry(),
        "pattern_evolution": get_pattern_tracker().get_telemetry(),
    }
