from __future__ import annotations

import logging
import os
import re

from agent_core.multi_agent.base_agent import AgentBase
from agent_core.multi_agent.context import SharedContext

log = logging.getLogger("multi_agent.optimizer")


class Optimizer(AgentBase):
    def __init__(self, model: str = "local", cost_per_call: float = 0.002):
        super().__init__(name="optimizer", model=model, cost_per_call=cost_per_call)

    def process(self, ctx: SharedContext, round_num: int) -> SharedContext:
        draft = ctx.draft
        kw = ctx.keyword
        if not draft:
            ctx.optimized_draft = ""
            return ctx

        optimized = draft

        # Real CTR optimization via modules
        ctr_data = None
        if not os.environ.get("SEO_AGENT_TEST_MODE"):
            try:
                from modules import optimize_ctr
                ctr_data = optimize_ctr(kw, draft[:600], self.model)
            except Exception as exc:
                log.info(f"optimize_ctr skipped: {exc}")

        optimized = self._ensure_keyword_in_headers(optimized, kw)
        optimized = self._add_schema_markers(optimized)
        optimized = self._improve_readability(optimized)
        optimized = self._add_transition_phrases(optimized, kw)

        # Embed recommended title/meta from CTR optimization
        if ctr_data:
            rec_title = ctr_data.get("recommended_title", "")
            rec_desc = ctr_data.get("recommended_description", "")
            if rec_title:
                optimized = f"<!-- META_TITLE: {rec_title} -->\n{optimized}"
            if rec_desc:
                optimized = f"<!-- META_DESCRIPTION: {rec_desc} -->\n{optimized}"

        ctx.optimized_draft = optimized
        return ctx

    def _ensure_keyword_in_headers(self, text: str, kw: str) -> str:
        lines = text.split("\n")
        result = []
        for line in lines:
            if (line.startswith("## ") or line.startswith("### ")) and kw.lower() not in line.lower():
                line = f"{line} — {kw.title()} Insights"
            result.append(line)
        return "\n".join(result)

    def _add_schema_markers(self, text: str) -> str:
        sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
        tagged = []
        for sec in sections:
            if sec.startswith("## Introduction"):
                sec = sec.replace("## Introduction", "## Introduction\n\n<!-- SCHEMA:Article -->", 1)
            elif sec.startswith("## FAQ"):
                sec = sec.replace("## FAQ", "## FAQ\n\n<!-- SCHEMA:FAQPage -->", 1)
            tagged.append(sec)
        return "".join(tagged)

    def _improve_readability(self, text: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        improved = []
        for s in sentences:
            if len(s.split()) > 30:
                mid = len(s) // 2
                split_at = s.rfind(" ", 0, mid)
                if split_at > 0:
                    s = s[:split_at] + ".\n" + s[split_at + 1:]
            improved.append(s)
        return " ".join(improved)

    def _add_transition_phrases(self, text: str, kw: str) -> str:
        paragraphs = text.split("\n\n")
        result = []
        transitions = [
            f"Furthermore, when evaluating {kw}, it's important to consider",
            f"Building on this analysis of {kw},",
            f"Another critical aspect of {kw} is",
            f"To fully understand {kw}, one must also examine",
        ]
        for i, para in enumerate(paragraphs):
            if i > 0 and para.strip() and not para.startswith("##") and not para.startswith("<!--"):
                prefix = transitions[i % len(transitions)]
                para = f"{prefix} {para.lstrip()}"
            result.append(para)
        return "\n\n".join(result)

    def _compute_readability_score(self, text: str) -> float:
        words = text.split()
        sentences = re.split(r"[.!?]+", text)
        if not sentences or not words:
            return 0.0
        avg_words_per_sentence = len(words) / max(len(sentences), 1)
        return max(0.0, min(100.0, 100.0 - (avg_words_per_sentence * 1.5)))
