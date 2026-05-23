"""
evaluation/scorers.py — Modular Article Quality Scorers
=========================================================
Each scorer is a pure function or class that evaluates one dimension:
  • SemanticScorer — keyword relevance, TF-IDF cosine, entity coverage
  • StructureScorer — heading hierarchy, schema completeness, HTML validity
  • SERPScorer — alignment with top-ranking SERP patterns
  • ReadabilityScorer — Flesch-Kincaid, sentence length distribution

All return normalized 0-100 scores with detailed feedback.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScoreResult:
    score: float = 0.0          # 0-100
    weight: float = 1.0         # contribution to final weighted score
    feedback: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────
#  Semantic Scorer
# ──────────────────────────────────────────────────────────────

_STOP_WORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "by","from","as","is","was","are","were","be","been","being","have",
    "has","had","do","does","did","will","would","could","should","may",
    "might","must","shall","can","need","used","this","that","these","those",
    "i","you","he","she","it","we","they","me","him","her","us","them",
    "my","your","his","its","our","their","what","which","who","when","where",
    "why","how","all","each","every","both","few","more","most","other",
    "some","such","no","nor","not","only","own","same","so","than","too",
    "very","just","now","then","also","here","there","up","down","out","off",
    "over","under","again","further","once","during","before","after","above",
    "below","between","through","while","about","against","into","onto","upon",
    "within","without","across","around","behind","beyond","except","inside",
    "outside","until","via","per","among","toward","best","top","review",
    "guide","complete","ultimate","vs","versus","alternative","free","paid",
}


class SemanticScorer:
    """Evaluate semantic relevance between article and keyword using TF overlap."""

    def score(self, article_text: str, keyword: str) -> ScoreResult:
        text_lower = article_text.lower()
        kw_tokens = [t for t in re.findall(r'\b\w{3,}\b', keyword.lower()) if t not in _STOP_WORDS]
        if not kw_tokens:
            kw_tokens = [keyword.lower()]

        text_tokens = [t for t in re.findall(r'\b\w{3,}\b', text_lower) if t not in _STOP_WORDS]
        if not text_tokens:
            return ScoreResult(score=0.0, feedback=["Empty article text"])

        vocab = set(kw_tokens) | set(text_tokens)
        tf_kw = {t: kw_tokens.count(t) / len(kw_tokens) for t in vocab}
        tf_text = {t: text_tokens.count(t) / len(text_tokens) for t in vocab}

        dot = sum(tf_kw.get(t, 0) * tf_text.get(t, 0) for t in vocab)
        norm_kw = math.sqrt(sum(v ** 2 for v in tf_kw.values()))
        norm_text = math.sqrt(sum(v ** 2 for v in tf_text.values()))

        similarity = dot / (norm_kw * norm_text) if norm_kw and norm_text else 0.0
        score = min(100.0, similarity * 120)  # boost for stronger matches

        feedback = []
        if similarity < 0.2:
            feedback.append("Very low keyword relevance — article may be off-topic")
        elif similarity < 0.4:
            feedback.append("Moderate relevance — weave keyword variants more naturally")

        # Entity coverage: simple bigram check
        kw_bigrams = set(zip(kw_tokens, kw_tokens[1:]))
        text_bigrams = set(zip(text_tokens, text_tokens[1:]))
        bigram_coverage = len(kw_bigrams & text_bigrams) / max(1, len(kw_bigrams))

        return ScoreResult(
            score=round(score, 1),
            feedback=feedback,
            details={
                "cosine_similarity": round(similarity, 3),
                "keyword_tokens": len(kw_tokens),
                "bigram_coverage": round(bigram_coverage, 2),
            },
        )


# ──────────────────────────────────────────────────────────────
#  Structure Scorer
# ──────────────────────────────────────────────────────────────

class StructureScorer:
    """Evaluate article structure: headings, schema, HTML quality."""

    def score(self, article_html: str, keyword: str) -> ScoreResult:
        feedback = []
        score = 100.0

        h1s = re.findall(r'<h1[^>]*>.*?</h1>', article_html, re.I | re.S)
        h2s = re.findall(r'<h2[^>]*>.*?</h2>', article_html, re.I | re.S)
        h3s = re.findall(r'<h3[^>]*>.*?</h3>', article_html, re.I | re.S)

        if len(h1s) == 0:
            feedback.append("Missing H1 heading")
            score -= 20
        elif len(h1s) > 1:
            feedback.append("Multiple H1 headings (should be exactly 1)")
            score -= 10

        if len(h2s) < 5:
            feedback.append(f"Only {len(h2s)} H2 sections — aim for 6+")
            score -= 15

        # Schema checks
        has_article = '"@type": "Article"' in article_html or '"@type":"Article"' in article_html
        has_faq = '"@type": "FAQPage"' in article_html or '"@type":"FAQPage"' in article_html
        has_itemlist = '"@type": "ItemList"' in article_html or '"@type":"ItemList"' in article_html

        if not has_article:
            feedback.append("Missing Article JSON-LD schema")
            score -= 10
        if not has_faq:
            feedback.append("Missing FAQPage schema")
            score -= 8

        # Table check for commercial intent
        is_commercial = any(w in keyword.lower() for w in ["best", "top", "vs", "compare"])
        has_table = '<table' in article_html.lower()
        if is_commercial and not has_table:
            feedback.append("Commercial article missing comparison table")
            score -= 12

        # Quick answer box
        if 'quick-answer-box' not in article_html.lower():
            feedback.append("Missing .quick-answer-box for featured snippet")
            score -= 5

        return ScoreResult(
            score=round(max(0, score), 1),
            feedback=feedback,
            details={
                "h1_count": len(h1s),
                "h2_count": len(h2s),
                "h3_count": len(h3s),
                "has_article_schema": has_article,
                "has_faq_schema": has_faq,
                "has_itemlist_schema": has_itemlist,
                "has_table": has_table,
            },
        )


# ──────────────────────────────────────────────────────────────
#  SERP Scorer
# ──────────────────────────────────────────────────────────────

class SERPScorer:
    """Compare generated article against extracted SERP benchmarks."""

    def score(self, article_html: str, keyword: str, serp_data: dict | None = None) -> ScoreResult:
        if not serp_data:
            return ScoreResult(score=50.0, feedback=["No SERP data provided — neutral score"])

        feedback = []
        score = 70.0
        details: dict[str, Any] = {}

        # Content depth vs SERP average
        text_only = re.sub(r'<[^>]+>', ' ', article_html)
        wc = len(text_only.split())
        serp_avg = serp_data.get("average_word_count", 0) or serp_data.get("content_length_avg", 0)
        if isinstance(serp_avg, str):
            serp_avg = int(re.search(r'\d+', serp_avg).group()) if re.search(r'\d+', serp_avg) else 0

        if serp_avg > 0:
            ratio = wc / serp_avg
            details["word_count_ratio"] = round(ratio, 2)
            if ratio < 0.8:
                feedback.append(f"Article shorter than SERP avg ({wc} vs {serp_avg} words)")
                score -= 15
            elif ratio >= 1.2:
                score += 10
                feedback.append("Article exceeds SERP average depth")

        # Gap coverage
        serp_gaps = serp_data.get("content_gaps", []) or serp_data.get("missing_gaps", [])
        if serp_gaps:
            art_lower = article_html.lower()
            covered = sum(1 for gap in serp_gaps if gap.lower()[:20] in art_lower)
            coverage = covered / len(serp_gaps)
            details["gap_coverage"] = round(coverage, 2)
            if coverage < 0.3:
                feedback.append(f"Low SERP gap coverage ({coverage:.0%})")
                score -= 10
            elif coverage >= 0.6:
                score += 10
                feedback.append("Strong gap exploitation")

        # Heading overlap with SERP common sections
        serp_sections = serp_data.get("common_sections", [])
        if serp_sections:
            h2_texts = [re.sub(r'<[^>]+>', '', h).lower() for h in re.findall(r'<h2[^>]*>(.*?)</h2>', article_html, re.I | re.S)]
            matched = 0
            for sec in serp_sections:
                sec_words = set(sec.lower().split())
                for h2 in h2_texts:
                    if sec_words & set(h2.split()):
                        matched += 1
                        break
            section_overlap = matched / len(serp_sections)
            details["section_overlap"] = round(section_overlap, 2)
            if section_overlap < 0.4:
                feedback.append("Article structure diverges from SERP patterns")
                score -= 8

        return ScoreResult(
            score=round(min(100, max(0, score)), 1),
            feedback=feedback,
            details=details,
        )


# ──────────────────────────────────────────────────────────────
#  Readability Scorer
# ──────────────────────────────────────────────────────────────

class ReadabilityScorer:
    """Flesch-Kincaid based readability with web-target adjustments."""

    def score(self, article_text: str) -> ScoreResult:
        sentences = max(1, len(re.findall(r'[.!?]+', article_text)))
        words = article_text.split()
        word_count = max(1, len(words))
        syllables = sum(self._syllable_count(w) for w in words)

        fk_ease = 206.835 - 1.015 * (word_count / sentences) - 84.6 * (syllables / word_count)
        fk_grade = 0.39 * (word_count / sentences) + 11.8 * (syllables / word_count) - 15.59

        # Target for web: FK ease 40-70 (grade 8-14)
        if 40 <= fk_ease <= 70:
            score = 90.0
        elif 30 <= fk_ease <= 80:
            score = 75.0
        else:
            score = 55.0

        feedback = []
        if fk_ease < 30:
            feedback.append("Very difficult readability — simplify vocabulary and shorten sentences")
        elif fk_ease > 80:
            feedback.append("Very easy readability — may lack depth and authority signals")

        return ScoreResult(
            score=round(score, 1),
            feedback=feedback,
            details={
                "flesch_kincaid_ease": round(fk_ease, 1),
                "flesch_kincaid_grade": round(fk_grade, 1),
                "avg_sentence_length": round(word_count / sentences, 1),
                "word_count": word_count,
            },
        )

    @staticmethod
    def _syllable_count(word: str) -> int:
        word = word.lower().strip(".,!?;:'\"")
        if len(word) <= 3:
            return 1
        vowels = "aeiouy"
        count = 0
        prev_vowel = False
        for ch in word:
            is_v = ch in vowels
            if is_v and not prev_vowel:
                count += 1
            prev_vowel = is_v
        if word.endswith("e"):
            count -= 1
        return max(1, count)
