"""
NEXUS Accessibility & Custom Commands REST API Router.

Provides endpoints for custom voice command macros and audio feedback preferences.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from nexus.accessibility.audio_feedback import AudioFeedbackManager
from nexus.accessibility.custom_commands import CustomCommandManager

router = APIRouter(prefix="/accessibility", tags=["accessibility"])

_custom_cmd_mgr = CustomCommandManager()
_audio_mgr = AudioFeedbackManager()


class CreateCommandRequest(BaseModel):
    phrase: str = Field(..., description="Voice trigger phrase (e.g., 'morning routine')")
    actions: list[str] = Field(..., description="List of sub-commands or instructions to execute")
    description: str = Field(default="", description="Optional description of the macro")


class EarconTestRequest(BaseModel):
    earcon_type: str = Field(default="success", description="Earcon tone type (wake, success, error, confirmation, emergency_stop)")


@router.get("/commands", summary="List custom voice commands")
async def list_custom_commands() -> dict[str, Any]:
    """Get all configured custom voice shortcuts and macros."""
    cmds = _custom_cmd_mgr.list_commands()
    return {
        "count": len(cmds),
        "commands": [
            {
                "phrase": c.phrase,
                "actions": c.actions,
                "description": c.description,
                "enabled": c.enabled,
            }
            for c in cmds
        ],
    }


@router.post("/commands", summary="Create a custom voice command")
async def create_custom_command(req: CreateCommandRequest) -> dict[str, Any]:
    """Register a new custom voice macro."""
    cmd = _custom_cmd_mgr.register_command(
        phrase=req.phrase,
        actions=req.actions,
        description=req.description,
    )
    return {
        "success": True,
        "phrase": cmd.phrase,
        "actions_count": len(cmd.actions),
        "message": f"Custom command '{cmd.phrase}' registered successfully.",
    }


@router.delete("/commands/{phrase}", summary="Delete a custom voice command")
async def delete_custom_command(phrase: str) -> dict[str, Any]:
    """Remove a custom voice command."""
    removed = _custom_cmd_mgr.remove_command(phrase)
    if not removed:
        raise HTTPException(status_code=404, detail="Command phrase not found.")
    return {"success": True, "phrase": phrase, "message": "Command removed."}


@router.post("/audio/earcon", summary="Test audio feedback earcon")
async def test_earcon(req: EarconTestRequest) -> dict[str, Any]:
    """Play a test audio earcon sound."""
    _audio_mgr.play_earcon(req.earcon_type, async_play=True)
    return {"success": True, "earcon": req.earcon_type, "message": f"Played earcon '{req.earcon_type}'."}
