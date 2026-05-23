from __future__ import annotations

import logging
import os
import time
from typing import Any

from agent_core.multi_agent.base_agent import AgentBase
from agent_core.multi_agent.context import SharedContext

log = logging.getLogger("multi_agent.researcher")


class Researcher(AgentBase):
    def __init__(self, model: str = "local", cost_per_call: float = 0.002):
        super().__init__(name="researcher", model=model, cost_per_call=cost_per_call)

    def process(self, ctx: SharedContext, round_num: int) -> SharedContext:
        kw = ctx.keyword

        result = None
        if not os.environ.get("SEO_AGENT_TEST_MODE"):
            try:
                from modules import analyze_competitors
                result = analyze_competitors(kw, self.model)
            except Exception as exc:
                log.info(f"analyze_competitors failed, using fallback: {exc}")

        if result:
            competitors = self._extract_competitors(result, kw)
            intent = self._extract_intent(result, kw)
            related = result.get("related_queries", self._related_queries(kw))
            ctx.research_data = {
                "keyword": kw,
                "search_volume_estimate": self._estimate_volume(kw),
                "competitors": competitors or self._find_competitors(kw),
                "related_queries": related,
                "intent": intent,
                "round": round_num,
                "_raw_serp": result,
            }
        else:
            ctx.research_data = {
                "keyword": kw,
                "search_volume_estimate": self._estimate_volume(kw),
                "competitors": self._find_competitors(kw),
                "related_queries": self._related_queries(kw),
                "intent": self._detect_intent(kw),
                "round": round_num,
            }

        return ctx

    def _extract_competitors(self, serp_result: dict, kw: str) -> list[dict[str, Any]] | None:
        competitors = serp_result.get("competitors")
        if competitors and isinstance(competitors, list):
            return competitors
        top_pages = serp_result.get("top_pages") or serp_result.get("competitor_pages")
        if top_pages and isinstance(top_pages, list):
            return [
                {"url": p.get("url", ""), "title": p.get("title", ""), "authority": p.get("authority", 30)}
                for p in top_pages[:5] if p.get("url")
            ]
        return None

    def _extract_intent(self, serp_result: dict, kw: str) -> str:
        intent = serp_result.get("dominant_search_intent")
        if intent and intent.lower() in ("commercial", "informational", "navigational", "transactional"):
            return intent.lower()
        return self._detect_intent(kw)

    def _estimate_volume(self, kw: str) -> str:
        vol_map = {
            "best": "high", "top": "high", "review": "medium",
            "what": "medium", "how": "medium", "why": "low",
            "guide": "medium", "tutorial": "medium",
        }
        for key, val in vol_map.items():
            if key in kw.lower():
                return val
        return "medium"

    def _find_competitors(self, kw: str) -> list[dict[str, Any]]:
        terms = kw.lower().split()
        domains = [
            {"url": f"example.com/{'-'.join(terms)}", "title": f"Best {kw.title()} Guide", "authority": 45},
            {"url": f"demo.org/{'-'.join(terms)}", "title": f"{kw.title()} — Complete Overview", "authority": 38},
            {"url": f"sample.net/{'-'.join(terms)}", "title": f"Top 10 {kw.title()} in 2026", "authority": 52},
        ]
        return domains

    def _related_queries(self, kw: str) -> list[str]:
        words = kw.lower().split()[:2]
        return [
            f"{' '.join(words)} for beginners",
            f"best {' '.join(words)} 2026",
            f"{' '.join(words)} vs alternatives",
            f"how to choose {' '.join(words)}",
        ]

    def _detect_intent(self, kw: str) -> str:
        commercial = {"best", "top", "review", "vs", "cheap", "price", "buy", "discount"}
        informational = {"what", "how", "why", "guide", "tutorial", "learn", "example"}
        words = set(kw.lower().split())
        if words & commercial:
            return "commercial"
        if words & informational:
            return "informational"
        return "navigational"
