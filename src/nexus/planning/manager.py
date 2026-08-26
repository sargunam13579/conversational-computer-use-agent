"""
NEXUS Planning — Task Manager.

Central manager coordinating goal decomposition, task tracking, execution lifecycle,
cancellation tokens, and emergency stop systems.
"""

from __future__ import annotations

import re
from typing import Any

from nexus.core.confirmation import ConfirmationManager
from nexus.llm.router import ModelRouter
from nexus.planning.cancellation import CancellationManager
from nexus.planning.executor import PlanExecutionEngine
from nexus.planning.planner import TaskPlanner
from nexus.planning.progress import ProgressTracker
from nexus.planning.retry import RetrySystem
from nexus.planning.tool_selector import ToolSelector
from nexus.planning.types import ExecutionResult, Plan, PlanStatus, TaskGoal, TaskProgress
from nexus.planning.verifier import ResultVerifier
from nexus.tools.executor import ToolExecutor
from nexus.tools.registry import ToolRegistry
from nexus.utils.logging import get_logger

log = get_logger("planning.manager")

# Heuristic patterns identifying multi-step requests
_MULTI_STEP_PATTERNS = [
    re.compile(r"\b(?:find|search)\b.*\b(?:convert|rename|send|transfer)\b", re.IGNORECASE),
    re.compile(r"\b(?:first|then|after that|finally|and then)\b", re.IGNORECASE),
    re.compile(r"\b(?:convert\s+to\s+pdf\s+and\s+send)\b", re.IGNORECASE),
    re.compile(r"\b(?:step\s+1|step\s+2)\b", re.IGNORECASE),
    re.compile(r"\b(?:download\s+.*and\s+open)\b", re.IGNORECASE),
    re.compile(r"\b(?:create\s+.*and\s+deploy)\b", re.IGNORECASE),
]


class TaskManager:
    """
    Central task and plan management engine for NEXUS.
    """

    def __init__(
        self,
        router: ModelRouter | None = None,
        registry: ToolRegistry | None = None,
        tool_executor: ToolExecutor | None = None,
        confirmation_manager: ConfirmationManager | None = None,
    ) -> None:
        self.planner = TaskPlanner(router=router)
        self.cancellation = CancellationManager()
        self.progress = ProgressTracker()
        self.retry_system = RetrySystem()
        self.verifier = ResultVerifier()
        self.tool_selector = ToolSelector(registry=registry)
        self.tool_executor = tool_executor
        self.confirmation_manager = confirmation_manager or ConfirmationManager()

        self.execution_engine = PlanExecutionEngine(
            tool_selector=self.tool_selector,
            tool_executor=self.tool_executor,
            confirmation_manager=self.confirmation_manager,
            progress_tracker=self.progress,
            retry_system=self.retry_system,
            verifier=self.verifier,
        )

        self._plans: dict[str, Plan] = {}
        self._active_plan_id: str | None = None

    @property
    def active_plan(self) -> Plan | None:
        """Get the currently active plan if one is in progress."""
        if self._active_plan_id:
            return self._plans.get(self._active_plan_id)
        return None

    def is_multi_step_goal(self, text: str) -> bool:
        """
        Check if a user input looks like a multi-step task requiring the planning agent.
        """
        stripped = text.strip()
        for pat in _MULTI_STEP_PATTERNS:
            if pat.search(stripped):
                return True
        # Also check clauses separated by commas/and
        clauses = re.split(r",\s*|\s+and\s+|\s+then\s+", stripped)
        action_verbs = {"find", "search", "convert", "rename", "send", "transfer", "open", "delete", "copy", "verify"}
        verb_count = sum(1 for c in clauses if any(c.lower().strip().startswith(v) for v in action_verbs))
        return verb_count >= 2

    async def submit_goal(
        self, goal_text: str, context: dict[str, Any] | None = None
    ) -> Plan:
        """
        Create a new multi-step Plan for a goal and register it.
        """
        task_goal = TaskGoal(description=goal_text, context=context or {})
        plan = await self.planner.create_plan(task_goal)
        self._plans[plan.plan_id] = plan
        return plan

    async def execute_task(self, plan: Plan) -> ExecutionResult:
        """
        Execute an existing plan with cancellation management.
        """
        self._plans[plan.plan_id] = plan
        self._active_plan_id = plan.plan_id
        token = self.cancellation.create_token(plan.plan_id)

        try:
            result = await self.execution_engine.execute_plan(plan, token=token)
            return result
        finally:
            if self._active_plan_id == plan.plan_id:
                self._active_plan_id = None

    async def run_goal(
        self, goal_text: str, context: dict[str, Any] | None = None
    ) -> ExecutionResult:
        """
        High-level helper: Decomposes goal into plan and executes it immediately.
        """
        plan = await self.submit_goal(goal_text, context=context)
        return await self.execute_task(plan)

    def cancel_active_task(self, reason: str = "User requested cancellation") -> bool:
        """
        Gracefully cancel the currently active task.
        """
        if not self._active_plan_id:
            return False
        return self.cancellation.cancel_task(self._active_plan_id, reason=reason)

    def emergency_stop(self, reason: str = "NEXUS STOP emergency triggered") -> dict[str, Any]:
        """
        Immediately halt all tasks and background processes.
        """
        result = self.cancellation.emergency_stop(plan_id=self._active_plan_id, reason=reason)
        if self._active_plan_id:
            plan = self._plans.get(self._active_plan_id)
            if plan:
                plan.status = PlanStatus.CANCELLED
                plan.error = reason
            self._active_plan_id = None
        return result

    def get_task(self, plan_id: str) -> Plan | None:
        """Retrieve a plan by its ID."""
        return self._plans.get(plan_id)

    def get_task_progress(self, plan_id: str) -> TaskProgress | None:
        """Retrieve the progress metrics for a plan."""
        return self.progress.get_progress(plan_id)

    def list_tasks(self) -> list[Plan]:
        """List all tracked plans."""
        return list(self._plans.values())
