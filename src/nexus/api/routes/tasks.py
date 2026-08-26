"""
NEXUS API — Planning & Multi-Step Task Routes.

Endpoints for submitting multi-step tasks, retrieving progress, managing plan steps,
and triggering graceful or emergency cancellations.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from nexus.planning.manager import TaskManager
from nexus.utils.logging import get_logger

log = get_logger("api.routes.tasks")

router = APIRouter(prefix="/tasks", tags=["Tasks & Planning"])

# Module-level singleton
_task_manager = TaskManager()


def get_task_manager() -> TaskManager:
    """Get the task manager instance."""
    return _task_manager


# --- Request & Response Models ---


class SubmitTaskRequest(BaseModel):
    goal: str = Field(..., description="High-level user goal description")
    context: dict[str, Any] = Field(default_factory=dict, description="Context variables")
    execute_now: bool = Field(default=True, description="Whether to execute immediately upon planning")


class CancelTaskRequest(BaseModel):
    reason: str = Field(default="User requested cancellation", description="Reason for cancellation")


class EmergencyStopRequest(BaseModel):
    reason: str = Field(default="EMERGENCY STOP triggered via API", description="Reason for emergency stop")


# --- Routes ---


@router.post("", response_model=dict[str, Any])
async def submit_task(req: SubmitTaskRequest, request: Request) -> dict[str, Any]:
    """Submit a high-level goal, generate a multi-step plan, and optionally execute it."""
    mgr = _task_manager
    if request and hasattr(request.app.state, "brain"):
        brain = request.app.state.brain
        if hasattr(brain, "task_manager") and brain.task_manager:
            mgr = brain.task_manager

    plan = await mgr.submit_goal(goal_text=req.goal, context=req.context)

    if req.execute_now:
        exec_result = await mgr.execute_task(plan)
        return {
            "plan": plan.to_dict(),
            "execution": exec_result.to_dict(),
        }

    return {
        "plan": plan.to_dict(),
        "execution": None,
    }


@router.get("", response_model=dict[str, Any])
async def list_tasks(request: Request) -> dict[str, Any]:
    """List all tracked plans and their current execution status."""
    mgr = _task_manager
    if hasattr(request.app.state, "brain"):
        brain = request.app.state.brain
        if hasattr(brain, "task_manager") and brain.task_manager:
            mgr = brain.task_manager

    plans = mgr.list_tasks()
    return {
        "count": len(plans),
        "tasks": [p.to_dict() for p in plans],
    }


@router.get("/{task_id}", response_model=dict[str, Any])
async def get_task_details(task_id: str, request: Request) -> dict[str, Any]:
    """Get the full plan and step details for a specific task."""
    mgr = _task_manager
    if hasattr(request.app.state, "brain"):
        brain = request.app.state.brain
        if hasattr(brain, "task_manager") and brain.task_manager:
            mgr = brain.task_manager

    plan = mgr.get_task(task_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    progress = mgr.get_task_progress(task_id)
    return {
        "task": plan.to_dict(),
        "progress": progress.to_dict() if progress else None,
    }


@router.post("/{task_id}/execute", response_model=dict[str, Any])
async def execute_task_by_id(task_id: str, request: Request) -> dict[str, Any]:
    """Execute a previously submitted plan."""
    mgr = _task_manager
    if hasattr(request.app.state, "brain"):
        brain = request.app.state.brain
        if hasattr(brain, "task_manager") and brain.task_manager:
            mgr = brain.task_manager

    plan = mgr.get_task(task_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    result = await mgr.execute_task(plan)
    return {
        "task": plan.to_dict(),
        "result": result.to_dict(),
    }


@router.post("/{task_id}/cancel", response_model=dict[str, Any])
async def cancel_task_by_id(
    task_id: str, req: CancelTaskRequest, request: Request
) -> dict[str, Any]:
    """Gracefully cancel an active task."""
    mgr = _task_manager
    if hasattr(request.app.state, "brain"):
        brain = request.app.state.brain
        if hasattr(brain, "task_manager") and brain.task_manager:
            mgr = brain.task_manager

    success = mgr.cancellation.cancel_task(task_id, reason=req.reason)
    if not success:
        raise HTTPException(status_code=404, detail=f"Active task '{task_id}' not found or already stopped")

    return {
        "success": True,
        "task_id": task_id,
        "reason": req.reason,
    }


@router.post("/emergency/stop", response_model=dict[str, Any])
async def trigger_emergency_stop(
    req: EmergencyStopRequest, request: Request
) -> dict[str, Any]:
    """Immediately halt all active tasks and background operations."""
    mgr = _task_manager
    if hasattr(request.app.state, "brain"):
        brain = request.app.state.brain
        if hasattr(brain, "task_manager") and brain.task_manager:
            mgr = brain.task_manager

    result = mgr.emergency_stop(reason=req.reason)
    return {
        "emergency_stop": True,
        "details": result,
    }
