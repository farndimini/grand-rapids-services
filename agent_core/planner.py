"""
agent_core/planner.py — Agent Planning Layer
=============================================
Transforms the pipeline from hardcoded sequence into an adaptive,
stateful, decision-making agent.

Features:
  • Explicit plan generation based on keyword, niche, SERP, budget
  • Dynamic replanning when conditions change
  • Policy-driven decisions (rewrite, retry, model switch, cost control)
  • Checkpoint/resume support
  • Execution graph generation from plan

Usage:
    from agent_core.planner import AgentPlanner, Policy
    planner = AgentPlanner()
    plan = planner.create_plan(keyword="best CRM", niche="tech", budget_mode=False)
    print(plan.steps)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any

from agent_core.metrics_collector import get_collector

log = logging.getLogger("agent_core.planner")

PLAN_DIR = Path(__file__).resolve().parent.parent / "plans"


class StepType(Enum):
    FETCH_SERP = auto()
    DETECT_INTENT = auto()
    IDENTIFY_GAPS = auto()
    GENERATE_OUTLINE = auto()
    GENERATE_ARTICLE = auto()
    VALIDATE = auto()
    REWRITE_WEAK = auto()
    CTR_OPTIMIZE = auto()
    CLUSTER_BUILD = auto()
    CALENDAR_BUILD = auto()


@dataclass
class PlanStep:
    step_type: StepType
    name: str
    params: dict[str, Any] = field(default_factory=dict)
    condition: str = ""         # gate condition: e.g., "quality < 70"
    fallback_step: str = ""     # jump target on failure
    retries: int = 2
    timeout_sec: float = 90.0


@dataclass
class Plan:
    plan_id: str
    keyword: str
    niche: str
    model: str
    budget_mode: bool
    steps: list[PlanStep] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    adaptive_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Policy:
    """Decision policies for the planner."""
    min_quality_score: int = 65
    max_rewrite_attempts: int = 2
    rewrite_threshold: int = 60
    retry_provider_on_error: bool = True
    switch_model_on_hallucination: bool = True
    budget_max_cost_usd: float = 0.05
    timeout_per_stage: float = 90.0
    enable_cluster: bool = True
    enable_calendar: bool = True


class AgentPlanner:
    """Adaptive planning engine for SEO content generation."""

    def __init__(self, policy: Policy | None = None):
        self.policy = policy or Policy()
        self._history: list[Plan] = []

    def create_plan(
        self,
        keyword: str,
        niche: str = "",
        model: str = "local",
        budget_mode: bool = False,
        serp_difficulty: str = "medium",
        **context,
    ) -> Plan:
        """Generate an adaptive execution plan."""
        plan_id = f"plan_{keyword.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        steps: list[PlanStep] = []

        # Step 1: SERP fetch
        steps.append(PlanStep(
            step_type=StepType.FETCH_SERP,
            name="fetch_serp",
            params={"keyword": keyword, "max_competitors": 5},
            retries=2,
            timeout_sec=30.0,
        ))

        # Step 2: Intent detection
        steps.append(PlanStep(
            step_type=StepType.DETECT_INTENT,
            name="detect_intent",
            params={"keyword": keyword},
            retries=1,
        ))

        # Step 3: Gap identification (depends on SERP)
        steps.append(PlanStep(
            step_type=StepType.IDENTIFY_GAPS,
            name="identify_gaps",
            params={"keyword": keyword},
            retries=1,
        ))

        # Step 4: Outline generation
        steps.append(PlanStep(
            step_type=StepType.GENERATE_OUTLINE,
            name="generate_outline",
            params={"keyword": keyword, "niche": niche},
            retries=1,
        ))

        # Step 5: Article generation
        steps.append(PlanStep(
            step_type=StepType.GENERATE_ARTICLE,
            name="generate_article",
            params={"keyword": keyword, "model": model, "budget_mode": budget_mode},
            retries=1,
            timeout_sec=120.0,
        ))

        # Step 6: Validation
        steps.append(PlanStep(
            step_type=StepType.VALIDATE,
            name="validate_article",
            params={"keyword": keyword},
            condition=f"quality >= {self.policy.rewrite_threshold}",
            fallback_step="rewrite_weak",
            retries=0,
        ))

        # Step 7: Conditional rewrite
        steps.append(PlanStep(
            step_type=StepType.REWRITE_WEAK,
            name="rewrite_weak",
            params={"keyword": keyword, "max_attempts": self.policy.max_rewrite_attempts},
            condition=f"quality < {self.policy.rewrite_threshold}",
            fallback_step="generate_article",  # retry from article
            retries=1,
        ))

        # Step 8: CTR optimization
        steps.append(PlanStep(
            step_type=StepType.CTR_OPTIMIZE,
            name="optimize_ctr",
            params={"keyword": keyword, "model": model},
            retries=1,
        ))

        # Adaptive branching: cluster + calendar
        if self.policy.enable_cluster and not budget_mode:
            steps.append(PlanStep(
                step_type=StepType.CLUSTER_BUILD,
                name="build_cluster",
                params={"keyword": keyword, "niche": niche, "model": model},
                retries=1,
            ))

        if self.policy.enable_calendar and not budget_mode:
            steps.append(PlanStep(
                step_type=StepType.CALENDAR_BUILD,
                name="build_calendar",
                params={"keyword": keyword, "niche": niche, "model": model},
                retries=1,
            ))

        # Adjustments based on difficulty
        adaptive = {}
        if serp_difficulty == "high":
            adaptive["target_length"] = 2500
            adaptive["required_sections"] = 8
        elif serp_difficulty == "low":
            adaptive["target_length"] = 1200
            adaptive["required_sections"] = 4
        else:
            adaptive["target_length"] = 1800
            adaptive["required_sections"] = 6

        plan = Plan(
            plan_id=plan_id,
            keyword=keyword,
            niche=niche,
            model=model,
            budget_mode=budget_mode,
            steps=steps,
            adaptive_params=adaptive,
        )

        self._history.append(plan)
        self._save_plan(plan)
        log.info(f"[Planner] Created plan {plan_id} with {len(steps)} steps")
        get_collector().increment("plans_created")
        return plan

    def replan_on_failure(self, plan: Plan, failed_step: str, failure_reason: str) -> Plan:
        """Create a modified plan after a step failure."""
        new_steps = []
        for s in plan.steps:
            new_steps.append(s)
            if s.name == failed_step and s.fallback_step:
                # Insert fallback step
                fb = next((x for x in plan.steps if x.name == s.fallback_step), None)
                if fb:
                    new_steps.append(PlanStep(
                        step_type=fb.step_type,
                        name=f"{fb.name}_retry",
                        params={**fb.params, "_retry_reason": failure_reason},
                        retries=max(0, fb.retries - 1),
                        timeout_sec=fb.timeout_sec * 1.2,
                    ))

        new_plan = Plan(
            plan_id=f"{plan.plan_id}_replan",
            keyword=plan.keyword,
            niche=plan.niche,
            model=plan.model,
            budget_mode=plan.budget_mode,
            steps=new_steps,
            adaptive_params={**plan.adaptive_params, "replan": True, "failure": failure_reason},
        )
        self._history.append(new_plan)
        self._save_plan(new_plan)
        log.info(f"[Planner] Replanned after '{failed_step}' failure")
        return new_plan

    def _save_plan(self, plan: Plan) -> None:
        PLAN_DIR.mkdir(parents=True, exist_ok=True)
        path = PLAN_DIR / f"{plan.plan_id}.json"
        payload = {
            "plan_id": plan.plan_id,
            "keyword": plan.keyword,
            "niche": plan.niche,
            "model": plan.model,
            "budget_mode": plan.budget_mode,
            "created_at": plan.created_at,
            "adaptive_params": plan.adaptive_params,
            "steps": [
                {
                    "name": s.name,
                    "type": s.step_type.name,
                    "params": s.params,
                    "condition": s.condition,
                    "fallback_step": s.fallback_step,
                    "retries": s.retries,
                    "timeout_sec": s.timeout_sec,
                }
                for s in plan.steps
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def visualize_text(self, plan: Plan) -> str:
        """Return ASCII visualization of the plan."""
        lines = [
            f"Plan: {plan.plan_id}",
            f"Keyword: {plan.keyword}  Niche: {plan.niche}  Model: {plan.model}",
            f"Budget mode: {plan.budget_mode}  Adaptive: {plan.adaptive_params}",
            "─" * 50,
        ]
        for i, step in enumerate(plan.steps, 1):
            cond = f"  IF {step.condition}" if step.condition else ""
            fb = f"  ELSE→{step.fallback_step}" if step.fallback_step else ""
            lines.append(f"  {i}. [{step.step_type.name:15s}] {step.name}{cond}{fb}")
        return "\n".join(lines)

    @classmethod
    def load_plan(cls, plan_id: str) -> Plan | None:
        path = PLAN_DIR / f"{plan_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Plan(
                plan_id=data["plan_id"],
                keyword=data["keyword"],
                niche=data.get("niche", ""),
                model=data["model"],
                budget_mode=data.get("budget_mode", False),
                adaptive_params=data.get("adaptive_params", {}),
                steps=[
                    PlanStep(
                        step_type=StepType[s["type"]],
                        name=s["name"],
                        params=s.get("params", {}),
                        condition=s.get("condition", ""),
                        fallback_step=s.get("fallback_step", ""),
                        retries=s.get("retries", 2),
                        timeout_sec=s.get("timeout_sec", 90.0),
                    )
                    for s in data.get("steps", [])
                ],
                created_at=data.get("created_at", datetime.now().isoformat()),
            )
        except (json.JSONDecodeError, KeyError):
            return None
