"""
NEXUS Planning — Goal Decomposition & Task Planner.

Decomposes high-level user requests into sequenced, dependency-aware PlanStep items,
assesses action risks, generates verification checkpoints, and detects missing information.
"""

from __future__ import annotations

import json
import re
from typing import Any

from nexus.llm.providers.base import LLMMessage, ModelTier
from nexus.llm.router import ModelRouter
from nexus.planning.types import (
    Plan,
    PlanStep,
    RiskLevel,
    TaskGoal,
)
from nexus.utils.logging import get_logger

log = get_logger("planning.planner")

# High-risk action keywords requiring explicit confirmation
_RISKY_PATTERNS = [
    (re.compile(r"\b(?:delete|remove|erase|wipe|format|drop)\b", re.IGNORECASE), RiskLevel.HIGH, "delete or erase data"),
    (re.compile(r"\b(?:overwrite|replace\s+all)\b", re.IGNORECASE), RiskLevel.MEDIUM, "overwrite existing files"),
    (re.compile(r"\b(?:reboot|shutdown|restart|kill\s+process)\b", re.IGNORECASE), RiskLevel.HIGH, "perform system state alteration"),
    (re.compile(r"\b(?:send\s+password|share\s+token|export\s+credentials)\b", re.IGNORECASE), RiskLevel.CRITICAL, "export or transmit sensitive credentials"),
]


class TaskPlanner:
    """
    Analyzes complex user goals and compiles executable step-by-step plans.
    """

    def __init__(self, router: ModelRouter | None = None) -> None:
        self._router = router

    async def create_plan(
        self, goal: str | TaskGoal, context: dict[str, Any] | None = None
    ) -> Plan:
        """
        Create a detailed execution plan for a goal.
        """
        task_goal = goal if isinstance(goal, TaskGoal) else TaskGoal(description=goal, context=context or {})
        plan = Plan(goal=task_goal)

        # Attempt LLM-assisted decomposition if a model is available
        if self._router and self._router.has_providers:
            try:
                llm_plan = await self._decompose_with_llm(task_goal)
                if llm_plan and len(llm_plan) > 0:
                    plan.steps = llm_plan
                    self._post_process_plan(plan)
                    return plan
            except Exception as e:
                log.warning("LLM planning fallback to heuristic decomposition: %s", e)

        # Fallback to deterministic heuristic decomposition
        plan.steps = self._decompose_heuristically(task_goal)
        self._post_process_plan(plan)
        return plan

    def _post_process_plan(self, plan: Plan) -> None:
        """
        Assign order indices, evaluate risk levels, and ensure verification checkpoints exist.
        """
        for i, step in enumerate(plan.steps, start=1):
            step.order = i
            # Check for risk
            risk, prompt = self.assess_step_risk(step.description)
            if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                step.risk_level = risk
                step.requires_confirmation = True
                step.confirmation_prompt = prompt or f"Confirm action: {step.description}?"

        # Ensure final verification step exists if not already present
        if plan.steps and not plan.steps[-1].is_verification:
            verif_step = PlanStep(
                order=len(plan.steps) + 1,
                description=f"Verify completion of goal: {plan.goal.description}",
                is_verification=True,
                dependencies=[plan.steps[-1].step_id],
            )
            plan.steps.append(verif_step)

    def assess_step_risk(self, description: str) -> tuple[RiskLevel, str | None]:
        """
        Evaluate description for risky or destructive actions.
        """
        for pattern, level, reason in _RISKY_PATTERNS:
            if pattern.search(description):
                return level, f"This step will {reason}. Are you sure you want to proceed?"
        return RiskLevel.LOW, None

    def check_missing_clarifications(self, goal_text: str) -> tuple[bool, str | None]:
        """
        Detect if a user goal lacks critical parameters that require asking the user before execution.
        """
        text = goal_text.lower()

        if "send to phone" in text and "which phone" in text:
            return True, "Which phone would you like to send this to?"
        if "convert it" in text and not any(ext in text for ext in ["pdf", "word", "image", "png", "text", "html"]):
            return True, "What format would you like to convert it to (e.g., PDF)?"

        return False, None

    async def _decompose_with_llm(self, goal: TaskGoal) -> list[PlanStep]:
        """
        Use an LLM to generate structured sequential steps.
        """
        assert self._router is not None

        prompt = f"""You are the NEXUS AI Agent Planner. Break down the user's goal into discrete sequential steps.
Goal: "{goal.description}"

Respond ONLY with a JSON array of step objects:
[
  {{
    "description": "Step description",
    "tool_name": "tool_name_or_null",
    "parameters": {{}},
    "requires_confirmation": false,
    "is_verification": false
  }}
]
"""
        messages = [
            LLMMessage(role="system", content="You are a planning engine that returns JSON."),
            LLMMessage(role="user", content=prompt),
        ]

        response = await self._router.generate(messages=messages, tier=ModelTier.FAST)
        content = response.content or "[]"

        # Clean markdown wrappers if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        data = json.loads(content)
        steps: list[PlanStep] = []
        for i, item in enumerate(data, start=1):
            step = PlanStep(
                order=i,
                description=item.get("description", f"Step {i}"),
                tool_name=item.get("tool_name"),
                parameters=item.get("parameters", {}),
                requires_confirmation=item.get("requires_confirmation", False),
                is_verification=item.get("is_verification", False),
            )
            steps.append(step)
        return steps

    def _decompose_heuristically(self, goal: TaskGoal) -> list[PlanStep]:
        """
        Deterministic rule-based planning for multi-step goals.
        """
        text = goal.description.strip()
        lower = text.lower()
        steps: list[PlanStep] = []

        # Example scenario: "find my latest resume, convert it to PDF, rename it Shanmuga_Resume, and send it to my phone."
        if "resume" in lower or ("find" in lower and "pdf" in lower and ("phone" in lower or "transfer" in lower or "send" in lower)):
            steps.append(
                PlanStep(
                    order=1,
                    description="Search for resume document in user workspace",
                    tool_name="find_files",
                    parameters={"query": "resume", "pattern": "*.docx"},
                )
            )
            steps.append(
                PlanStep(
                    order=2,
                    description="Identify the most recent resume version",
                    tool_name="find_files",
                    parameters={"sort_by": "modified", "limit": 1},
                )
            )
            steps.append(
                PlanStep(
                    order=3,
                    description="Convert document to PDF format",
                    tool_name="convert_document",
                    parameters={"source": "{{step_2.output}}", "target_format": "pdf"},
                )
            )

            # Check if rename was requested
            rename_match = re.search(r"rename\s+(?:it\s+)?(?:to\s+)?([A-Za-z0-9_-]+)", text, re.IGNORECASE)
            new_name = rename_match.group(1) if rename_match else "Shanmuga_Resume"

            steps.append(
                PlanStep(
                    order=4,
                    description=f"Rename converted PDF to {new_name}.pdf",
                    tool_name="rename_file",
                    parameters={"source": "{{step_3.output}}", "new_name": f"{new_name}.pdf"},
                )
            )
            steps.append(
                PlanStep(
                    order=5,
                    description="Transfer file to phone",
                    tool_name="transfer_file",
                    parameters={"file_path": "{{step_4.output}}", "target_device": "phone"},
                )
            )
            steps.append(
                PlanStep(
                    order=6,
                    description="Verify delivery and file integrity",
                    tool_name="verify_delivery",
                    is_verification=True,
                    parameters={"target_device": "phone", "file": f"{new_name}.pdf"},
                )
            )
            return steps

        # Generic multi-command splitting on 'and', 'then', commas
        clauses = re.split(r",\s*(?:and\s+)?|\s+and\s+|\s+then\s+", text)
        cleaned_clauses = [c.strip() for c in clauses if len(c.strip()) > 3]

        if not cleaned_clauses:
            cleaned_clauses = [text]

        for i, clause in enumerate(cleaned_clauses, start=1):
            step = PlanStep(
                order=i,
                description=clause.capitalize(),
            )
            steps.append(step)

        return steps
