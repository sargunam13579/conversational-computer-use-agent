"""
NEXUS Planning & Multi-Step Agent — Data Types and Models.

Defines schemas for task goals, plan steps, plan status, execution metrics,
progress tracking, and verification criteria.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StepStatus(StrEnum):
    """Execution status of an individual plan step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    AWAITING_CLARIFICATION = "awaiting_clarification"


class PlanStatus(StrEnum):
    """Lifecycle status of a multi-step plan."""

    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RiskLevel(StrEnum):
    """Risk severity of an action step."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TaskGoal:
    """The original or clarified user goal."""

    description: str
    context: dict[str, Any] = field(default_factory=dict)
    user_id: str | None = None
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "context": self.context,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass
class PlanStep:
    """An individual actionable step within a plan."""

    step_id: str = field(default_factory=lambda: f"step_{uuid.uuid4().hex[:8]}")
    order: int = 1
    description: str = ""
    tool_name: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    risk_level: RiskLevel = RiskLevel.LOW
    requires_confirmation: bool = False
    confirmation_prompt: str | None = None
    requires_clarification: bool = False
    clarification_question: str | None = None
    is_verification: bool = False
    retry_count: int = 0
    max_retries: int = 2
    output: Any = None
    error: str | None = None
    started_at: float | None = None
    completed_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "order": self.order,
            "description": self.description,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "risk_level": self.risk_level.value,
            "requires_confirmation": self.requires_confirmation,
            "confirmation_prompt": self.confirmation_prompt,
            "requires_clarification": self.requires_clarification,
            "clarification_question": self.clarification_question,
            "is_verification": self.is_verification,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class Plan:
    """A sequence of steps designed to accomplish a TaskGoal."""

    goal: TaskGoal
    plan_id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    steps: list[PlanStep] = field(default_factory=list)
    status: PlanStatus = PlanStatus.PLANNING
    current_step_index: int = 0
    context_variables: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    error: str | None = None

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def completed_steps_count(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)

    @property
    def is_finished(self) -> bool:
        return self.status in (PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.CANCELLED)

    def get_step(self, step_id: str) -> PlanStep | None:
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal.to_dict(),
            "status": self.status.value,
            "current_step_index": self.current_step_index,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps_count,
            "steps": [s.to_dict() for s in self.steps],
            "context_variables": self.context_variables,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


@dataclass
class TaskProgress:
    """Real-time progress metrics for an executing task."""

    plan_id: str
    status: PlanStatus
    current_step_order: int
    total_steps: int
    percent_complete: float
    current_step_description: str
    elapsed_seconds: float
    message: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "status": self.status.value,
            "current_step_order": self.current_step_order,
            "total_steps": self.total_steps,
            "percent_complete": round(self.percent_complete, 2),
            "current_step_description": self.current_step_description,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "message": self.message,
            "history": self.history,
        }


@dataclass
class VerificationResult:
    """Outcome of verifying a step or task result."""

    verified: bool
    details: str
    target_artifact: str | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "details": self.details,
            "target_artifact": self.target_artifact,
            "confidence": self.confidence,
        }


@dataclass
class ExecutionResult:
    """Final result of task execution."""

    success: bool
    plan_id: str
    goal: str
    final_output: str
    steps_executed: int
    total_steps: int
    duration_seconds: float
    error: str | None = None
    verification: VerificationResult | None = None
    context_variables: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "plan_id": self.plan_id,
            "goal": self.goal,
            "final_output": self.final_output,
            "steps_executed": self.steps_executed,
            "total_steps": self.total_steps,
            "duration_seconds": round(self.duration_seconds, 2),
            "error": self.error,
            "verification": self.verification.to_dict() if self.verification else None,
            "context_variables": self.context_variables,
        }
