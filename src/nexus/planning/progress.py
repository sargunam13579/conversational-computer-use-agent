"""
NEXUS Planning — Progress Tracking & Reporting.

Maintains real-time progress state, step timelines, percentage completion,
and emits structured event bus events for terminal UI, voice feedback, and API streams.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from rich.panel import Panel
from rich.table import Table

from nexus.planning.types import Plan, PlanStatus, PlanStep, StepStatus, TaskProgress
from nexus.utils.events import get_event_bus
from nexus.utils.logging import console, get_logger

log = get_logger("planning.progress")


def _safe_emit(coro: Any) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        pass


class ProgressTracker:
    """
    Tracks and broadcasts real-time progress for multi-step task executions.
    """

    def __init__(self) -> None:
        self._progress_map: dict[str, TaskProgress] = {}
        self._start_times: dict[str, float] = {}
        self._event_bus = get_event_bus()

    def start_tracking(self, plan: Plan) -> TaskProgress:
        """Initialize progress tracking for a new plan."""
        start_time = time.time()
        self._start_times[plan.plan_id] = start_time

        progress = TaskProgress(
            plan_id=plan.plan_id,
            status=PlanStatus.IN_PROGRESS,
            current_step_order=1 if plan.steps else 0,
            total_steps=plan.total_steps,
            percent_complete=0.0,
            current_step_description=plan.steps[0].description if plan.steps else "Initializing...",
            elapsed_seconds=0.0,
            message=f"Starting task with {plan.total_steps} steps",
            history=[
                {
                    "timestamp": start_time,
                    "event": "task_started",
                    "goal": plan.goal.description,
                    "total_steps": plan.total_steps,
                }
            ],
        )
        self._progress_map[plan.plan_id] = progress

        _safe_emit(
            self._event_bus.emit(
                "task.started",
                {
                    "plan_id": plan.plan_id,
                    "goal": plan.goal.description,
                    "total_steps": plan.total_steps,
                    "steps": [s.description for s in plan.steps],
                },
                source="progress_tracker",
            )
        )
        return progress

    def update_step_started(self, plan: Plan, step: PlanStep) -> TaskProgress:
        """Record the start of an individual plan step."""
        now = time.time()
        elapsed = now - self._start_times.get(plan.plan_id, now)
        completed = plan.completed_steps_count
        percent = (completed / max(1, plan.total_steps)) * 100.0

        progress = TaskProgress(
            plan_id=plan.plan_id,
            status=PlanStatus.IN_PROGRESS,
            current_step_order=step.order,
            total_steps=plan.total_steps,
            percent_complete=percent,
            current_step_description=step.description,
            elapsed_seconds=elapsed,
            message=f"Executing Step [{step.order}/{plan.total_steps}]: {step.description}",
            history=self._get_history(plan.plan_id),
        )
        progress.history.append(
            {
                "timestamp": now,
                "event": "step_started",
                "step_order": step.order,
                "step_id": step.step_id,
                "description": step.description,
            }
        )
        self._progress_map[plan.plan_id] = progress

        _safe_emit(
            self._event_bus.emit(
                "task.step_started",
                {
                    "plan_id": plan.plan_id,
                    "step_order": step.order,
                    "total_steps": plan.total_steps,
                    "description": step.description,
                    "tool": step.tool_name,
                },
                source="progress_tracker",
            )
        )
        return progress

    def update_step_completed(
        self, plan: Plan, step: PlanStep, output_summary: str | None = None
    ) -> TaskProgress:
        """Record the successful completion of a plan step."""
        now = time.time()
        elapsed = now - self._start_times.get(plan.plan_id, now)
        completed = plan.completed_steps_count
        percent = (completed / max(1, plan.total_steps)) * 100.0

        progress = TaskProgress(
            plan_id=plan.plan_id,
            status=PlanStatus.IN_PROGRESS,
            current_step_order=step.order,
            total_steps=plan.total_steps,
            percent_complete=percent,
            current_step_description=step.description,
            elapsed_seconds=elapsed,
            message=f"Completed Step [{step.order}/{plan.total_steps}]: {step.description}",
            history=self._get_history(plan.plan_id),
        )
        progress.history.append(
            {
                "timestamp": now,
                "event": "step_completed",
                "step_order": step.order,
                "step_id": step.step_id,
                "output_summary": output_summary or str(step.output)[:120],
            }
        )
        self._progress_map[plan.plan_id] = progress

        _safe_emit(
            self._event_bus.emit(
                "task.step_completed",
                {
                    "plan_id": plan.plan_id,
                    "step_order": step.order,
                    "total_steps": plan.total_steps,
                    "percent_complete": percent,
                    "description": step.description,
                },
                source="progress_tracker",
            )
        )
        return progress

    def update_step_failed(
        self, plan: Plan, step: PlanStep, error: str, retrying: bool = False
    ) -> TaskProgress:
        """Record a failure or retry attempt on a step."""
        now = time.time()
        elapsed = now - self._start_times.get(plan.plan_id, now)
        completed = plan.completed_steps_count
        percent = (completed / max(1, plan.total_steps)) * 100.0

        status_msg = (
            f"Step [{step.order}/{plan.total_steps}] error (retrying attempt {step.retry_count}): {error}"
            if retrying
            else f"Step [{step.order}/{plan.total_steps}] failed: {error}"
        )

        progress = TaskProgress(
            plan_id=plan.plan_id,
            status=PlanStatus.IN_PROGRESS if retrying else PlanStatus.FAILED,
            current_step_order=step.order,
            total_steps=plan.total_steps,
            percent_complete=percent,
            current_step_description=step.description,
            elapsed_seconds=elapsed,
            message=status_msg,
            history=self._get_history(plan.plan_id),
        )
        progress.history.append(
            {
                "timestamp": now,
                "event": "step_retry" if retrying else "step_failed",
                "step_order": step.order,
                "error": error,
                "retry_count": step.retry_count,
            }
        )
        self._progress_map[plan.plan_id] = progress

        _safe_emit(
            self._event_bus.emit(
                "task.step_failed",
                {
                    "plan_id": plan.plan_id,
                    "step_order": step.order,
                    "error": error,
                    "retrying": retrying,
                },
                source="progress_tracker",
            )
        )
        return progress

    def complete_tracking(
        self, plan: Plan, success: bool = True, final_message: str = ""
    ) -> TaskProgress:
        """Finalize progress tracking on plan completion or termination."""
        now = time.time()
        elapsed = now - self._start_times.get(plan.plan_id, now)

        status = (
            PlanStatus.COMPLETED
            if success
            else (
                PlanStatus.CANCELLED
                if plan.status == PlanStatus.CANCELLED
                else PlanStatus.FAILED
            )
        )

        progress = TaskProgress(
            plan_id=plan.plan_id,
            status=status,
            current_step_order=plan.total_steps,
            total_steps=plan.total_steps,
            percent_complete=100.0 if success else (plan.completed_steps_count / max(1, plan.total_steps)) * 100.0,
            current_step_description="Completed" if success else "Terminated",
            elapsed_seconds=elapsed,
            message=final_message or ("Task completed successfully" if success else "Task stopped"),
            history=self._get_history(plan.plan_id),
        )
        progress.history.append(
            {
                "timestamp": now,
                "event": "task_completed" if success else "task_terminated",
                "status": status.value,
                "message": progress.message,
            }
        )
        self._progress_map[plan.plan_id] = progress

        _safe_emit(
            self._event_bus.emit(
                "task.completed" if success else "task.terminated",
                {
                    "plan_id": plan.plan_id,
                    "success": success,
                    "status": status.value,
                    "duration_seconds": elapsed,
                    "message": progress.message,
                },
                source="progress_tracker",
            )
        )
        return progress

    def get_progress(self, plan_id: str) -> TaskProgress | None:
        """Get the current progress snapshot for a plan."""
        return self._progress_map.get(plan_id)

    def _get_history(self, plan_id: str) -> list[dict[str, Any]]:
        existing = self._progress_map.get(plan_id)
        return existing.history if existing else []

    def render_progress_panel(self, plan: Plan) -> None:
        """Render a formatted Rich UI panel of the plan and step statuses in the terminal."""
        table = Table(show_header=True, header_style="bold magenta", expand=True)
        table.add_column("#", style="dim", width=4)
        table.add_column("Status", width=12)
        table.add_column("Step Description")
        table.add_column("Tool", width=16)

        for s in plan.steps:
            if s.status == StepStatus.COMPLETED:
                st = "[bold green]✓ COMPLETED[/bold green]"
            elif s.status == StepStatus.RUNNING:
                st = "[bold yellow]⏳ RUNNING[/bold yellow]"
            elif s.status == StepStatus.FAILED:
                st = "[bold red]✗ FAILED[/bold red]"
            elif s.status == StepStatus.CANCELLED:
                st = "[bold dim red]⊘ CANCELLED[/bold dim red]"
            elif s.status == StepStatus.AWAITING_CONFIRMATION:
                st = "[bold orange3]? CONFIRM[/bold orange3]"
            elif s.status == StepStatus.AWAITING_CLARIFICATION:
                st = "[bold cyan]? CLARIFY[/bold cyan]"
            else:
                st = "[dim]PENDING[/dim]"

            table.add_row(
                str(s.order),
                st,
                s.description,
                s.tool_name or "-",
            )

        panel = Panel(
            table,
            title=f"[bold cyan]NEXUS Plan — {plan.goal.description}[/bold cyan]",
            subtitle=f"[dim]Plan ID: {plan.plan_id} | Status: {plan.status.value.upper()}[/dim]",
            border_style="blue",
        )
        console.print(panel)
