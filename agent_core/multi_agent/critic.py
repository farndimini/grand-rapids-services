from __future__ import annotations

import logging
import re

from agent_core.multi_agent.base_agent import AgentBase
from agent_core.multi_agent.context import SharedContext

log = logging.getLogger("multi_agent.critic")


class Critic(AgentBase):
    def __init__(self, model: str = "local", cost_per_call: float = 0.001):
        super().__init__(name="critic", model=model, cost_per_call=cost_per_call)

    def process(self, ctx: SharedContext, round_num: int) -> SharedContext:
        text = ctx.optimized_draft or ctx.draft
        kw = ctx.keyword

        quality = None
        try:
            from modules import validate_article_quality
            quality = validate_article_quality(text, kw)
        except Exception as exc:
            log.info(f"validate_article_quality failed, using fallback: {exc}")

        if quality:
            issues = quality.get("failures", []) + quality.get("warnings", [])
            ctx.critique = {
                "quality_score": quality.get("score", 50),
                "issues": issues,
                "suggestions": self._generate_suggestions(issues),
                "approved": quality.get("pass", False),
                "keyword_density": self._keyword_density(text, kw),
                "readability_score": self._readability_score(text),
                "word_count": len(text.split()),
                "round": round_num,
                "_quality_full": quality,
            }
        else:
            quality_score = self._score_quality(text, kw)
            issues = self._find_issues(text, kw)
            ctx.critique = {
                "quality_score": quality_score,
                "issues": issues,
                "suggestions": self._generate_suggestions(issues),
                "approved": quality_score >= 60,
                "keyword_density": self._keyword_density(text, kw),
                "readability_score": self._readability_score(text),
                "word_count": len(text.split()),
                "round": round_num,
            }

        return ctx

    def _score_quality(self, text: str, kw: str) -> int:
        score = 50
        if kw.lower() in text.lower():
            score += 15
        word_count = len(text.split())
        if word_count >= 800:
            score += 10
        if word_count >= 1500:
            score += 10
        sections = len(re.findall(r"^## ", text, re.MULTILINE))
        score += min(15, sections * 3)
        score = min(100, max(0, score))
        return score

    def _find_issues(self, text: str, kw: str) -> list[str]:
        issues = []
        word_count = len(text.split())
        if word_count < 500:
            issues.append("Content too short for meaningful coverage")
        elif word_count < 1200:
            issues.append("Consider expanding to meet search intent depth")
        kw_count = text.lower().count(kw.lower())
        if kw_count < 3:
            issues.append("Keyword appears fewer than 3 times")
        if kw_count > 20:
            issues.append("Possible keyword stuffing")
        sections = re.findall(r"^## ", text, re.MULTILINE)
        if len(sections) < 3:
            issues.append("Fewer than 3 sections — add more structure")
        if kw.lower() not in text.lower()[:500]:
            issues.append("Keyword missing from opening paragraph")
        return issues

    def _generate_suggestions(self, issues: list[str]) -> list[str]:
        suggestion_map = {
            "Content too short": "Expand each section with 2-3 supporting paragraphs",
            "Consider expanding": "Add real-world examples and case studies",
            "Keyword appears fewer": "Naturally integrate the keyword in headings and early paragraphs",
            "Possible keyword stuffing": "Replace repeated keyword instances with synonyms and pronouns",
            "Fewer than 3 sections": "Break content into more granular subsections",
            "Keyword missing from opening": "Rephrase the introduction to include the primary keyword",
        }
        suggestions = []
        for issue in issues:
            for key, val in suggestion_map.items():
                if key in issue:
                    suggestions.append(val)
                    break
            else:
                suggestions.append(f"Address: {issue}")
        return suggestions

    def _keyword_density(self, text: str, kw: str) -> float:
        words = text.lower().split()
        if not words:
            return 0.0
        kw_words = kw.lower().split()
        count = sum(1 for w in words if w in kw_words)
        return round(count / len(words) * 100, 2)

    def _readability_score(self, text: str) -> float:
        sentences = re.split(r"[.!?]+", text)
        words = text.split()
        if not sentences or not words:
            return 0.0
        avg_words = len(words) / max(len([s for s in sentences if s.strip()]), 1)
        return round(max(0.0, 100.0 - (avg_words * 2.0)), 1)
