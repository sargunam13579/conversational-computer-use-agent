"""
NEXUS Conversational Computer-Use Tools.

Exposes atomic computer-use controls and autonomous closed-loop goal execution
to the NEXUS Tool Registry and Planners.
"""

from __future__ import annotations

from typing import Any

from nexus.agents.computer_use.actions import ComputerActionExecutor
from nexus.agents.computer_use.agent import ConversationalComputerUseAgent
from nexus.agents.computer_use.protocol import ActionType, ComputerAction
from nexus.tools.base import BaseTool, RiskLevel, TargetDevice, ToolResult
from nexus.utils.logging import get_logger

log = get_logger("tools.computer_use")


class ComputerClickTool(BaseTool):
    """Click on a specific screen coordinate (x, y) or active focus."""

    def __init__(self, executor: ComputerActionExecutor | None = None) -> None:
        self._executor = executor or ComputerActionExecutor()

    @property
    def name(self) -> str:
        return "computer_click"

    @property
    def description(self) -> str:
        return (
            "Click on the computer screen at exact pixel coordinates (x, y) or current mouse position. "
            "Supports left, right, or double-click."
        )

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "x": {
                    "type": "integer",
                    "description": "Horizontal pixel coordinate (0 to screen width).",
                },
                "y": {
                    "type": "integer",
                    "description": "Vertical pixel coordinate (0 to screen height).",
                },
                "button": {
                    "type": "string",
                    "enum": ["left", "right", "double"],
                    "default": "left",
                    "description": "Mouse button action to perform.",
                },
            },
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        x = kwargs.get("x")
        y = kwargs.get("y")
        button = kwargs.get("button", "left")

        if button == "double":
            action_type = ActionType.DOUBLE_CLICK
        elif button == "right":
            action_type = ActionType.RIGHT_CLICK
        else:
            action_type = ActionType.CLICK

        action = ComputerAction(action_type=action_type, x=x, y=y)
        res = await self._executor.execute(action)
        return ToolResult(
            success=res.get("success", True),
            output=f"Executed {button} click at ({x}, {y})",
            data=res,
        )


class ComputerTypeTool(BaseTool):
    """Type text into the currently focused window or field."""

    def __init__(self, executor: ComputerActionExecutor | None = None) -> None:
        self._executor = executor or ComputerActionExecutor()

    @property
    def name(self) -> str:
        return "computer_type"

    @property
    def description(self) -> str:
        return "Type text into the currently focused application or input field on screen."

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["text"],
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The string text content to type into the focused element.",
                },
            },
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        text = kwargs.get("text", "")
        action = ComputerAction(action_type=ActionType.TYPE_TEXT, text=text)
        res = await self._executor.execute(action)
        return ToolResult(
            success=res.get("success", True),
            output=f"Typed {len(text)} characters onto screen",
            data=res,
        )


class ComputerHotkeyTool(BaseTool):
    """Send keyboard shortcuts or special keys to the active application."""

    def __init__(self, executor: ComputerActionExecutor | None = None) -> None:
        self._executor = executor or ComputerActionExecutor()

    @property
    def name(self) -> str:
        return "computer_hotkey"

    @property
    def description(self) -> str:
        return "Send keyboard shortcut combination (e.g. 'ctrl+s', 'alt+f4', 'win+r') or single key (e.g. 'enter', 'esc')."

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["key"],
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Key name or hotkey combination (e.g., 'enter', 'ctrl+c', 'ctrl+v', 'alt+tab').",
                },
            },
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        key = kwargs.get("key", "")
        if "+" in key:
            action = ComputerAction(action_type=ActionType.HOTKEY, key=key)
        else:
            action = ComputerAction(action_type=ActionType.KEY_PRESS, key=key)
        res = await self._executor.execute(action)
        return ToolResult(
            success=res.get("success", True),
            output=f"Sent keyboard combination '{key}'",
            data=res,
        )


class ComputerScrollTool(BaseTool):
    """Scroll the active window or specific screen location."""

    def __init__(self, executor: ComputerActionExecutor | None = None) -> None:
        self._executor = executor or ComputerActionExecutor()

    @property
    def name(self) -> str:
        return "computer_scroll"

    @property
    def description(self) -> str:
        return "Scroll up or down on the active window or at specific screen coordinates."

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down"],
                    "default": "down",
                    "description": "Direction to scroll.",
                },
                "amount": {
                    "type": "integer",
                    "default": 3,
                    "description": "Number of scroll clicks/steps.",
                },
                "x": {
                    "type": "integer",
                    "description": "Optional X coordinate where scroll should occur.",
                },
                "y": {
                    "type": "integer",
                    "description": "Optional Y coordinate where scroll should occur.",
                },
            },
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        direction = kwargs.get("direction", "down")
        amount = kwargs.get("amount", 3)
        x = kwargs.get("x")
        y = kwargs.get("y")
        action = ComputerAction(action_type=ActionType.MOUSE_SCROLL, direction=direction, amount=amount, x=x, y=y)
        res = await self._executor.execute(action)
        return ToolResult(
            success=res.get("success", True),
            output=f"Scrolled {direction} by {amount} steps",
            data=res,
        )


class AutonomousComputerUseGoalTool(BaseTool):
    """Execute a complete end-to-end task autonomously via closed-loop Computer-Use."""

    def __init__(self, agent: ConversationalComputerUseAgent | None = None) -> None:
        self._agent = agent

    @property
    def name(self) -> str:
        return "execute_computer_use_goal"

    @property
    def description(self) -> str:
        return (
            "Autonomously accomplish a high-level desktop computer-use goal using closed-loop "
            "screen perception, visual UI grounding, mouse clicks, and typing (e.g. 'Open Excel and create a budget table')."
        )

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["goal"],
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "The natural language computer-use task or objective to accomplish.",
                },
                "max_steps": {
                    "type": "integer",
                    "default": 20,
                    "description": "Maximum visual iteration steps to prevent runaway loops.",
                },
            },
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        goal = kwargs.get("goal", "")
        max_steps = kwargs.get("max_steps", 20)

        agent = self._agent or ConversationalComputerUseAgent(max_steps=max_steps)
        result = await agent.run_goal(goal=goal)

        status = result.get("status", "unknown")
        steps = result.get("steps_executed", 0)
        return ToolResult(
            success=(status == "completed"),
            output=f"Computer-Use goal execution finished with status '{status}' across {steps} visual steps.",
            data=result,
        )


def get_computer_use_tools() -> list[BaseTool]:
    """Return collection of all computer-use tools."""
    return [
        ComputerClickTool(),
        ComputerTypeTool(),
        ComputerHotkeyTool(),
        ComputerScrollTool(),
        AutonomousComputerUseGoalTool(),
    ]
