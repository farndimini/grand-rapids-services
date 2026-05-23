"""
validator.py — Semantic Quality Validation Engine (v2)
=======================================================
Enhancements over v1:
  • Reward/penalty scoring that feeds back into MetricsCollector
  • Content pattern fingerprinting (detect winning structures)
  • SERP alignment scoring (how well article matches top result patterns)
  • E-E-A-T signal strength meter
  • Actionable rewrite directives (not just pass/fail)

Usage:
    from agent_core.validator import SemanticValidator
    v = SemanticValidator()
    report = v.validate(article_html, keyword="best password manager")
    print(report.score, report.reward_score, report.rewrite_directives)
"""

from __future__ import annotations

import json
import logging
import math
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from agent_core.metrics_collector import get_collector

log = logging.getLogger("agent_core.validator")

_STOP_WORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "by","from","as","is","was","are","were","be","been","being","have",
    "has","had","do","does","did","will","would","could","should","may",
    "might","must","shall","can","need","dare","ought","used","this","that",
    "these","those","i","you","he","she","it","we","they","me","him","her",
    "us","them","my","your","his","its","our","their","what","which","who",
    "when","where","why","how","all","each","every","both","few","more",
    "most","other","some","such","no","nor","not","only","own","same","so",
    "than","too","very","just","now","then","also","here","there","up","down",
    "out","off","over","under","again","further","once","during","before",
    "after","above","below","between","through","while","about","against",
    "into","onto","upon","within","without","across","around","behind",
    "beyond","except","inside","outside","until","via","per","among","toward",
    "best","top","review","guide","complete","ultimate","vs","versus",
    "alternative","free","paid","cheap","affordable","2025","2026",
}


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


def _flesch_kincaid(text: str) -> float:
    sentences = max(1, len(re.findall(r'[.!?]+', text)))
    words = text.split()
    word_count = max(1, len(words))
    syllables = sum(_syllable_count(w) for w in words)
    return 206.835 - 1.015 * (word_count / sentences) - 84.6 * (syllables / word_count)


def _flesch_grade(text: str) -> float:
    sentences = max(1, len(re.findall(r'[.!?]+', text)))
    words = text.split()
    word_count = max(1, len(words))
    syllables = sum(_syllable_count(w) for w in words)
    return 0.39 * (word_count / sentences) + 11.8 * (syllables / word_count) - 15.59


@dataclass
class QualityReport:
    score: int = 0
    reward_score: float = 0.0          # -1 to +1 (for RL feedback)
    keyword_relevance: float = 0.0
    readability_ease: float = 0.0
    readability_grade: float = 0.0
    structure_score: int = 0
    eeat_score: int = 0               # NEW: E-E-A-T strength
    serp_alignment: float = 0.0       # NEW: alignment with top SERP patterns
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rewrite_directives: list[dict] = field(default_factory=list)  # NEW
    metadata: dict[str, Any] = field(default_factory=dict)

    def passed(self, threshold: int = 70) -> bool:
        return self.score >= threshold and not any(i.startswith("CRITICAL") for i in self.issues)


class SemanticValidator:
    """Advanced quality validation with reward scoring and actionable directives."""

    def __init__(self, keyword_relevance_threshold: float = 0.25):
        self._rel_thresh = keyword_relevance_threshold
        self._collector = get_collector()

    def validate(self, article: str, keyword: str) -> QualityReport:
        report = QualityReport()
        text_only = re.sub(r'<[^>]+>', ' ', article)
        text_only = re.sub(r'\s+', ' ', text_only).strip()
        word_count = len(text_only.split())

        # 1. Keyword relevance
        report.keyword_relevance = self._keyword_relevance(text_only, keyword)
        if report.keyword_relevance < self._rel_thresh:
            report.issues.append(
                f"CRITICAL: Low keyword relevance ({report.keyword_relevance:.2f} < {self._rel_thresh:.2f})"
            )
            report.rewrite_directives.append({"type": "keyword_density", "priority": 1, "action": f"Increase natural usage of '{keyword}' and variants"})
        elif report.keyword_relevance < 0.4:
            report.warnings.append(f"Low keyword relevance ({report.keyword_relevance:.2f})")
            report.rewrite_directives.append({"type": "keyword_density", "priority": 2, "action": f"Weave '{keyword}' more naturally into subheadings"})

        # 2. Readability
        report.readability_ease = _flesch_kincaid(text_only)
        report.readability_grade = _flesch_grade(text_only)
        if report.readability_ease < 30:
            report.warnings.append(f"Very hard to read (FK ease {report.readability_ease:.1f})")
            report.rewrite_directives.append({"type": "readability", "priority": 2, "action": "Break long sentences, replace jargon with simpler terms"})
        elif report.readability_ease > 80:
            report.warnings.append(f"Very easy — may lack depth (FK ease {report.readability_ease:.1f})")
            report.rewrite_directives.append({"type": "readability", "priority": 3, "action": "Add specificity and technical detail where appropriate"})

        # 3. Structure alignment
        report.structure_score = self._structure_score(article, keyword)

        # 4. E-E-A-T signals
        report.eeat_score = self._eeat_score(article)
        if report.eeat_score < 50:
            report.warnings.append(f"Weak E-E-A-T signals ({report.eeat_score}/100)")
            report.rewrite_directives.append({"type": "eeat", "priority": 1, "action": "Add expert credentials, real testing evidence, or citations"})

        # 5. Schema completeness
        schema_issues = self._schema_check(article)
        report.warnings.extend(schema_issues)
        for si in schema_issues:
            if "Missing" in si:
                report.rewrite_directives.append({"type": "schema", "priority": 2, "action": si.replace("Missing ", "Add ")})

        # 6. Link health (sample)
        dead_links = self._sample_dead_links(article)
        if dead_links:
            report.warnings.append(f"Dead links detected: {', '.join(dead_links[:3])}")
            report.rewrite_directives.append({"type": "links", "priority": 3, "action": f"Fix or replace {len(dead_links)} dead external links"})

        # 7. SERP alignment (heuristic)
        report.serp_alignment = self._serp_alignment(article, keyword)

        # 8. Composite score
        report.score = self._composite_score(report, word_count)

        # 9. Reward calculation
        report.reward_score = self._reward(report, word_count)

        # Record metrics
        self._collector.record_quality(report.score)

        report.metadata = {
            "word_count": word_count,
            "h1_count": len(re.findall(r'<h1[^>]*>', article, re.I)),
            "h2_count": len(re.findall(r'<h2[^>]*>', article, re.I)),
            "h3_count": len(re.findall(r'<h3[^>]*>', article, re.I)),
            "external_links": len(re.findall(r'<a[^>]*href="https?://', article, re.I)),
            "tables": len(re.findall(r'<table', article, re.I)),
            "dead_links_sample": dead_links,
            "eeat_score": report.eeat_score,
            "serp_alignment": report.serp_alignment,
            "reward_score": report.reward_score,
        }

        return report

    def _keyword_relevance(self, text: str, keyword: str) -> float:
        kw_tokens = [t.lower() for t in re.findall(r'\b\w{3,}\b', keyword) if t.lower() not in _STOP_WORDS]
        if not kw_tokens:
            kw_tokens = [keyword.lower()]
        text_tokens = [t.lower() for t in re.findall(r'\b\w{3,}\b', text) if t.lower() not in _STOP_WORDS]
        if not text_tokens:
            return 0.0
        vocab = set(kw_tokens) | set(text_tokens)
        tf_kw = {t: kw_tokens.count(t) / len(kw_tokens) for t in vocab}
        tf_text = {t: text_tokens.count(t) / len(text_tokens) for t in vocab}
        def _weight(tok, freq):
            boost = 2.0 if tok in kw_tokens else 1.0
            return freq * boost
        dot = sum(_weight(t, tf_kw.get(t, 0)) * _weight(t, tf_text.get(t, 0)) for t in vocab)
        norm_kw = math.sqrt(sum(v ** 2 for v in tf_kw.values()))
        norm_text = math.sqrt(sum(v ** 2 for v in tf_text.values()))
        if norm_kw == 0 or norm_text == 0:
            return 0.0
        return min(1.0, dot / (norm_kw * norm_text))

    def _structure_score(self, article: str, keyword: str) -> int:
        score = 100
        h1s = re.findall(r'<h1[^>]*>(.*?)</h1>', article, re.I | re.S)
        h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', article, re.I | re.S)
        kw_lower = keyword.lower()
        h1_texts = [re.sub(r'<[^>]+>', '', h).lower() for h in h1s]
        if not any(kw_lower in h or h in kw_lower for h in h1_texts):
            score -= 25
        if len(h2s) < 5:
            score -= 20
        has_article = '"@type": "Article"' in article or '"@type":"Article"' in article
        has_faq = '"@type": "FAQPage"' in article or '"@type":"FAQPage"' in article
        if not has_article:
            score -= 15
        if not has_faq:
            score -= 10
        if 'quick-answer-box' not in article.lower():
            score -= 10
        return max(0, score)

    def _eeat_score(self, article: str) -> int:
        """Score Experience, Expertise, Authoritativeness, Trustworthiness signals."""
        score = 0
        text_lower = article.lower()
        # Experience: first-person testing, specific observations
        exp_signals = ["i tested", "we tested", "after testing", "real-world", "in practice",
                       "from experience", "hands-on", "live test", "actual usage"]
        score += min(25, sum(5 for s in exp_signals if s in text_lower))
        # Expertise: technical depth, citations, data
        if re.search(r'\b\d{1,2}\.\d%|\b\d{1,3}\s*(ms|fps|mb|gb|seconds|minutes)\b', text_lower):
            score += 15
        if len(re.findall(r'<a[^>]*href="https?://[^"]*\.(edu|gov|research)', text_lower)) > 0:
            score += 10
        # Authoritativeness: external citations, expert quotes
        if len(re.findall(r'<blockquote', text_lower)) > 0 or "according to" in text_lower:
            score += 15
        # Trustworthiness: honest negatives, transparency, dates
        if any(w in text_lower for w in ["not ideal for", "downside", "weakness", "honest",
                                          "cons:", " Drawback", "limitation"]):
            score += 15
        if re.search(r'"datePublished":\s*"\d{4}-\d{2}-\d{2}"', article):
            score += 10
        # Penalties
        if "seo agent pro" in text_lower:
            score -= 10
        if "after two weeks of testing" in text_lower or "after four weeks of testing" in text_lower:
            score -= 5
        return max(0, min(100, score))

    def _serp_alignment(self, article: str, keyword: str) -> float:
        """Heuristic: does the article contain typical top-ranking elements?"""
        score = 0.0
        text_lower = article.lower()
        # Comparison elements for commercial keywords
        if any(w in keyword.lower() for w in ["best", "top", "vs", "compare"]):
            if "<table" in article:
                score += 0.3
            if re.search(r'pros?\s+(and|&|vs)', text_lower):
                score += 0.2
            if "$" in article or "pricing" in text_lower or "free" in text_lower:
                score += 0.2
            if "verdict" in text_lower or "winner" in text_lower or "recommend" in text_lower:
                score += 0.2
        # Informational elements
        if any(w in keyword.lower() for w in ["how to", "what is", "guide"]):
            if re.search(r'<ol[^>]*>', article):
                score += 0.3
            if re.search(r'step\s+\d', text_lower):
                score += 0.2
        # Universal
        if re.search(r'<div[^>]*class="faq', text_lower):
            score += 0.1
        return min(1.0, score)

    def _schema_check(self, article: str) -> list[str]:
        issues = []
        schemas = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', article, re.S | re.I)
        parsed = []
        for s in schemas:
            try:
                parsed.append(json.loads(s.strip()))
            except json.JSONDecodeError:
                issues.append("Malformed JSON-LD schema detected")
        types = [p.get("@type", "") for p in parsed if isinstance(p, dict)]
        if "Article" not in types:
            issues.append("Missing Article schema")
        today_pattern = re.search(r'"datePublished":\s*"(\d{4}-\d{2}-\d{2})"', article)
        if today_pattern:
            from datetime import datetime
            try:
                dp = datetime.strptime(today_pattern.group(1), "%Y-%m-%d")
                delta = (datetime.now() - dp).days
                if delta > 7:
                    issues.append(f"Schema date is {delta} days old")
            except ValueError:
                pass
        return issues

    def _sample_dead_links(self, article: str, sample_size: int = 5) -> list[str]:
        links = re.findall(r'href="(https?://[^"]+)"', article)
        skip_domains = {"yoursite.com", "example.com", "placeholder.com"}
        check_links = [l for l in links if not any(d in l for d in skip_domains)]
        import random
        sample = random.sample(check_links, min(sample_size, len(check_links))) if check_links else []
        dead = []
        for url in sample:
            try:
                req = urllib.request.Request(url, method="HEAD")
                req.add_header("User-Agent", "Mozilla/5.0")
                with urllib.request.urlopen(req, timeout=8) as resp:
                    if resp.status >= 400:
                        dead.append(url)
            except Exception:
                dead.append(url)
        return dead

    def _composite_score(self, report: QualityReport, word_count: int) -> int:
        score = report.structure_score * 0.35
        score += report.keyword_relevance * 30
        ease = report.readability_ease
        if 40 <= ease <= 70:
            score += 20
        elif 30 <= ease <= 80:
            score += 10
        else:
            score += 5
        if word_count >= 2000:
            score += 15
        elif word_count >= 1500:
            score += 10
        else:
            score += max(0, (word_count / 1500) * 10)
        # E-E-A-T bonus
        score += report.eeat_score * 0.05
        issue_penalty = sum(15 if i.startswith("CRITICAL") else 8 for i in report.issues)
        warning_penalty = len(report.warnings) * 2
        score = score - issue_penalty - warning_penalty
        return max(0, min(100, int(score)))

    def _reward(self, report: QualityReport, word_count: int) -> float:
        """Calculate a continuous reward signal (-1 to +1) for RL feedback loops."""
        if report.score >= 85 and word_count >= 1800:
            return 1.0
        if report.score >= 70:
            return 0.5
        if report.score >= 50:
            return 0.0
        if report.score >= 30:
            return -0.5
        return -1.0
