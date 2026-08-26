"""
NEXUS API — Conversational Computer-Use Agent Endpoints.

Provides REST and telemetry endpoints for autonomous computer-use tasks,
live conversational steering, screen element inspection, and emergency controls.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from nexus.agents.computer_use.actions import ComputerActionExecutor
from nexus.agents.computer_use.agent import ConversationalComputerUseAgent
from nexus.agents.computer_use.protocol import (
    ActionType,
    AgentStatus,
    ComputerAction,
    SteeringInstruction,
)
from nexus.utils.logging import get_logger

log = get_logger("api.routes.computer_use")

router = APIRouter(prefix="/computer-use", tags=["Conversational Computer Use"])

# Global singleton instance of the computer use agent for live session management
_COMPUTER_USE_AGENT: ConversationalComputerUseAgent | None = None


def get_agent() -> ConversationalComputerUseAgent:
    global _COMPUTER_USE_AGENT
    if _COMPUTER_USE_AGENT is None:
        _COMPUTER_USE_AGENT = ConversationalComputerUseAgent()
    return _COMPUTER_USE_AGENT


class RunGoalRequest(BaseModel):
    goal: str = Field(..., description="The conversational computer-use goal to achieve.")
    max_steps: int = Field(default=20, ge=1, le=50, description="Max iterative steps.")
    auto_confirm: bool = Field(default=False, description="Auto-confirm standard actions.")
    conversation_id: str | None = Field(default=None, description="Optional conversation ID to append to.")


class SteerRequest(BaseModel):
    instruction: str = Field(..., description="Conversational guidance or correction instruction.")
    interrupt: bool = Field(default=True, description="Whether to interrupt current sub-action immediately.")


class DirectActionRequest(BaseModel):
    action_type: str = Field(..., description="Action primitive: click, double_click, right_click, type_text, hotkey, mouse_scroll")
    x: int | None = None
    y: int | None = None
    text: str | None = None
    key: str | None = None
    direction: str = "down"
    amount: int = 3


@router.get("/status")
async def get_computer_use_status() -> dict[str, Any]:
    """Get current status, telemetry, and step history of the computer-use agent."""
    agent = get_agent()
    return {
        "status": str(agent.status),
        "history_count": len(agent.history),
        "history": [
            {
                "step": s.step_number,
                "thought": s.thought,
                "action": str(s.action.action_type),
                "coordinates": (s.action.x, s.action.y),
                "success": s.success,
                "elapsed_seconds": s.elapsed_seconds,
            }
            for s in agent.history
        ],
    }


@router.post("/run")
async def run_computer_use_goal(req: RunGoalRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Start an autonomous conversational computer-use goal or handle stop commands."""
    agent = get_agent()
    goal_lower = req.goal.strip().lower()

    # 1. Check if user sent a cancellation or stop command
    stop_keywords = ["stop", "cancel", "halt", "quit", "exit", "stop it", "stop opening", "stop task"]
    if any(goal_lower == kw or goal_lower.startswith("stop ") or goal_lower.startswith("cancel ") for kw in stop_keywords):
        agent.request_stop()
        agent._status = AgentStatus.IDLE
        return {
            "status": "stopped",
            "narration": "I have stopped the computer-use operation for you.",
            "conversation_id": req.conversation_id,
            "steps_executed": len(agent.history),
        }

    # 2. If agent is currently busy, gracefully stop the previous task and start the new one
    if agent.status in (AgentStatus.ACTING, AgentStatus.THINKING, AgentStatus.OBSERVING):
        log.info("Agent is busy; auto-stopping prior task to fulfill new goal: %s", req.goal)
        agent.request_stop()
        await asyncio.sleep(0.3)
        agent._status = AgentStatus.IDLE

    # 3. Launch task
    result = await agent.run_goal(goal=req.goal, auto_confirm=req.auto_confirm)

    # Persist message and conversation into SQLite database with [Computer-Use] prefix
    conversation_id = req.conversation_id
    try:
        from sqlalchemy import select

        from nexus.database.engine import get_session
        from nexus.database.models import Session as DBSession
        from nexus.database.models import User
        from nexus.database.repositories.conversation import ConversationRepository

        async with get_session() as session:
            repo = ConversationRepository(session)
            conv = None
            if conversation_id:
                conv = await repo.get_conversation(conversation_id)

            if conv is None:
                user_res = await session.execute(select(User).limit(1))
                db_user = user_res.scalar_one_or_none()
                if db_user is None:
                    db_user = User(name="User")
                    session.add(db_user)
                    await session.flush()

                sess_res = await session.execute(select(DBSession).where(DBSession.user_id == db_user.id).limit(1))
                db_session = sess_res.scalar_one_or_none()
                if db_session is None:
                    db_session = DBSession(user_id=db_user.id)
                    session.add(db_session)
                    await session.flush()

                clean_goal = req.goal.strip()
                clean_summary = f"[Computer-Use] {clean_goal[:35]}" + ("..." if len(clean_goal) > 35 else "")
                conv = await repo.create_conversation(session_id=db_session.id, summary=clean_summary)
                conversation_id = conv.id

            await repo.add_message(conversation_id=conv.id, role="user", content=req.goal)
            steps_taken = len(result.get("history", []))
            assistant_content = (
                result.get("narration")
                or f"Task {result.get('status', 'completed')}. {steps_taken} autonomous steps executed on Windows."
            )
            await repo.add_message(conversation_id=conv.id, role="assistant", content=assistant_content)
            await session.commit()
    except Exception as db_err:
        log.warning("Computer-Use database persistence notice: %s", db_err)
        conversation_id = conversation_id or "cu_default"

    result["conversation_id"] = conversation_id
    return result


@router.post("/steer")
async def steer_computer_use(req: SteerRequest) -> dict[str, Any]:
    """Inject conversational guidance mid-execution into the active Computer-Use agent."""
    agent = get_agent()
    await agent.steer(SteeringInstruction(instruction=req.instruction, interrupt_current_action=req.interrupt))
    return {
        "status": "steered",
        "instruction": req.instruction,
        "message": "Conversational steering instruction queued successfully.",
    }


@router.post("/stop")
async def stop_computer_use() -> dict[str, Any]:
    """Emergency stop any currently running computer-use operation."""
    agent = get_agent()
    agent.request_stop()
    return {
        "status": "stopped",
        "message": "Emergency stop signal sent to Computer-Use Agent.",
    }


@router.get("/observe")
async def observe_screen_state(tag_elements: bool = True) -> dict[str, Any]:
    """Capture live screen state and Set-of-Marks tagged elements."""
    agent = get_agent()
    obs = await agent.observe(tag_elements=tag_elements)
    return {
        "status": "observed",
        "screen_width": obs.screen_width,
        "screen_height": obs.screen_height,
        "active_window": obs.active_window,
        "detected_elements_count": len(obs.detected_elements),
        "detected_elements": obs.detected_elements,
        "som_base64_image": obs.som_base64_image,
        "base64_image": obs.base64_image,
        "timestamp": obs.timestamp,
    }


@router.post("/action")
async def execute_direct_action(req: DirectActionRequest) -> dict[str, Any]:
    """Directly execute a single low-level computer action without full autonomous loop."""
    try:
        act_type = ActionType(req.action_type)
    except ValueError as err:
        raise HTTPException(
            status_code=400, detail=f"Unsupported action type '{req.action_type}'"
        ) from err

    executor = ComputerActionExecutor()
    action = ComputerAction(
        action_type=act_type,
        x=req.x,
        y=req.y,
        text=req.text,
        key=req.key,
        direction=req.direction,
        amount=req.amount,
    )
    result = await executor.execute(action)
    return result
