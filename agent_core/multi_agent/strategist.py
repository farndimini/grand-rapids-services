from __future__ import annotations

import logging
import os
from typing import Any

from agent_core.multi_agent.base_agent import AgentBase
from agent_core.multi_agent.context import SharedContext

log = logging.getLogger("multi_agent.strategist")


class Strategist(AgentBase):
    def __init__(self, model: str = "local", cost_per_call: float = 0.002):
        super().__init__(name="strategist", model=model, cost_per_call=cost_per_call)

    def process(self, ctx: SharedContext, round_num: int) -> SharedContext:
        rd = ctx.research_data
        kw = ctx.keyword
        intent = rd.get("intent", "informational")

        result = None
        if not os.environ.get("SEO_AGENT_TEST_MODE"):
            try:
                from modules import decide_strategy
                competitor_data = rd.get("_raw_serp", rd)
                articles_written = 0
                result = decide_strategy(kw, competitor_data, articles_written, self.model)
            except Exception as exc:
                log.info(f"decide_strategy failed, using fallback: {exc}")

        if result:
            angle = result.get("unique_angle", "") or self._fallback_angle(kw, intent)
            sections = result.get("required_sections", []) or self._fallback_sections(intent)
            word_target = result.get("ideal_length", 0) or self._word_target(intent)
            tone = result.get("tone", "") or self._tone_for_intent(intent)

            ctx.strategy = {
                "keyword": kw,
                "angle": angle,
                "sections": sections,
                "word_count_target": word_target,
                "tone": tone,
                "competitors_to_target": [c["url"] for c in rd.get("competitors", []) if isinstance(c, dict)],
                "related_queries_to_include": rd.get("related_queries", []),
                "round": round_num,
                "unique_angle": angle,
                "required_sections": sections,
                "ideal_length": result.get("ideal_length", word_target),
                "must_have_elements": result.get("must_have_elements", []),
                "_strategy_full": result,
            }
        else:
            ctx.strategy = self._stub_strategy(rd, kw, intent, round_num)

        return ctx

    def _stub_strategy(self, rd: dict, kw: str, intent: str, round_num: int) -> dict:
        return {
            "keyword": kw,
            "angle": self._fallback_angle(kw, intent),
            "sections": self._fallback_sections(intent),
            "word_count_target": self._word_target(intent),
            "tone": self._tone_for_intent(intent),
            "competitors_to_target": [c["url"] for c in rd.get("competitors", []) if isinstance(c, dict)],
            "related_queries_to_include": rd.get("related_queries", []),
            "round": round_num,
        }

    def _fallback_angle(self, kw: str, intent: str) -> str:
        if intent == "commercial":
            return f"Why {kw.title()} Is the Smart Choice in 2026"
        elif intent == "informational":
            return f"Everything You Need to Know About {kw.title()}"
        return f"{kw.title()} — The Definitive Resource"

    def _fallback_sections(self, intent: str) -> list[str]:
        if intent == "commercial":
            return ["Introduction", "Key Features", "Comparison", "Pricing Guide", "Verdict"]
        elif intent == "informational":
            return ["Introduction", "What Is It", "How It Works", "Key Considerations", "FAQ"]
        return ["Introduction", "Overview", "Deep Dive", "Resources"]

    def _word_target(self, intent: str) -> int:
        return 2500 if intent == "commercial" else 1800 if intent == "informational" else 1200

    def _tone_for_intent(self, intent: str) -> str:
        return "persuasive_authoritative" if intent == "commercial" else "educational_clear" if intent == "informational" else "neutral_comprehensive"
