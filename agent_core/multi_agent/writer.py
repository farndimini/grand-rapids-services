from __future__ import annotations

import logging
import os
import random
import re

from agent_core.multi_agent.base_agent import AgentBase
from agent_core.multi_agent.context import SharedContext

log = logging.getLogger("multi_agent.writer")


class Writer(AgentBase):
    def __init__(self, model: str = "local", cost_per_call: float = 0.003):
        super().__init__(name="writer", model=model, cost_per_call=cost_per_call)

    def process(self, ctx: SharedContext, round_num: int) -> SharedContext:
        strategy = ctx.strategy
        kw = ctx.keyword

        # Use real write_article when strategy came from the real strategist
        # (has _strategy_full).  Fall back to stub otherwise for backward
        # compatibility with standalone usage and tests.
        if "_strategy_full" in strategy and not os.environ.get("SEO_AGENT_TEST_MODE"):
            try:
                from modules import write_article
                normalized = self._normalize_strategy(strategy, kw)
                article_html = write_article(kw, normalized, self.model)
                ctx.draft = self._html_headers_to_markdown(article_html)
                return ctx
            except Exception as exc:
                log.info(f"write_article failed, using fallback: {exc}")

        ctx.draft = self._stub_generate(strategy, kw, round_num)
        return ctx

    def _normalize_strategy(self, strategy: dict, kw: str) -> dict:
        sections = strategy.get("required_sections") or strategy.get("sections") or []
        angle = strategy.get("unique_angle") or strategy.get("angle", f"All About {kw.title()}")
        length = strategy.get("ideal_length") or strategy.get("word_count_target", 1500)
        elements = strategy.get("must_have_elements", [])

        norm = {
            "ideal_length": length,
            "required_sections": sections,
            "unique_angle": angle,
            "must_have_elements": elements,
        }
        for key in ("_gap_prompt", "_gap_angles", "_ranking_brain"):
            if key in strategy:
                norm[key] = strategy[key]
        return norm

    def _html_headers_to_markdown(self, html: str) -> str:
        html = re.sub(r'(?i)<h1[^>]*>', '# ', html)
        html = re.sub(r'(?i)</h1>', '', html)
        html = re.sub(r'(?i)<h2[^>]*>', '## ', html)
        html = re.sub(r'(?i)</h2>', '', html)
        html = re.sub(r'(?i)<h3[^>]*>', '### ', html)
        html = re.sub(r'(?i)</h3>', '', html)
        return html

    def _stub_generate(self, strategy: dict, kw: str, round_num: int) -> str:
        sections = strategy.get("sections", ["Introduction", "Body", "Conclusion"])
        angle = strategy.get("angle", f"All About {kw.title()}")
        target_wc = strategy.get("word_count_target", 1500)

        paragraphs = []
        for i, sec in enumerate(sections):
            wc_per_section = target_wc // len(sections)
            body = self._generate_section(sec, kw, wc_per_section, angle, round_num)
            paragraphs.append(f"## {sec}\n\n{body}")

        return f"# {angle}\n\n" + "\n\n".join(paragraphs)

    def _generate_section(self, section: str, kw: str, target_wc: int, angle: str, round_num: int) -> str:
        seed = hash(f"{kw}-{section}-{round_num}")
        rng = random.Random(seed)
        templates = [
            f"When it comes to {kw}, understanding the nuances of {section.lower()} "
            f"can make all the difference. {self._filler(kw, rng)}",
            f"{section} is a critical aspect of any comprehensive {kw} discussion. "
            f"{self._filler(kw, rng)}",
            f"Let's explore {section.lower()} in the context of {kw}. "
            f"{self._filler(kw, rng)}",
        ]
        body = rng.choice(templates)
        current_wc = len(body.split())
        while current_wc < target_wc:
            body += f" {self._filler(kw, rng)}"
            current_wc = len(body.split())
        return body

    def _filler(self, kw: str, rng: random.Random) -> str:
        phrases = [
            f"Users searching for {kw} often look for comprehensive, well-structured content.",
            f"Industry experts recommend evaluating multiple factors when considering {kw}.",
            f"The landscape of {kw} continues to evolve, presenting new opportunities and challenges.",
            f"Understanding {kw} requires a multi-faceted approach that considers various perspectives.",
            f"Research indicates that {kw} will remain a key topic for the foreseeable future.",
        ]
        return rng.choice(phrases)
