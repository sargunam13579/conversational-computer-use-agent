"""
NEXUS Conversational Computer-Use Agent Protocol.

Defines the action types, data structures, and state representations
for visual computer-use execution and conversational steering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ActionType(StrEnum):
    """Computer-Use action primitives."""

    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    MIDDLE_CLICK = "middle_click"
    MOUSE_MOVE = "mouse_move"
    MOUSE_DRAG = "mouse_drag"
    MOUSE_SCROLL = "mouse_scroll"
    TYPE_TEXT = "type_text"
    CLIPBOARD_PASTE = "clipboard_paste"
    KEY_PRESS = "key_press"
    HOTKEY = "hotkey"
    OPEN_APP = "open_app"
    FOCUS_WINDOW = "focus_window"
    SWITCH_WINDOW = "switch_window"
    WINDOW_MINIMIZE = "window_minimize"
    WINDOW_MAXIMIZE = "window_maximize"
    WINDOW_CLOSE = "window_close"
    WAIT = "wait"
    INSPECT_SCREEN = "inspect_screen"
    SCREENSHOT = "screenshot"
    ASK_USER = "ask_user"
    FINISH = "finish"


class AgentStatus(StrEnum):
    """Execution status of the computer-use agent."""

    IDLE = "idle"
    OBSERVING = "observing"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING_USER = "waiting_user"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class Coordinate:
    """Screen coordinate position."""

    x: int
    y: int

    def to_tuple(self) -> tuple[int, int]:
        return (self.x, self.y)


@dataclass
class ComputerAction:
    """An atomic computer-use action to execute."""

    action_type: ActionType
    x: int | None = None
    y: int | None = None
    end_x: int | None = None
    end_y: int | None = None
    text: str | None = None
    app_name: str | None = None
    key: str | None = None
    keys: list[str] | None = None
    direction: str = "down"
    clicks: int = 1
    amount: int = 3
    seconds: float = 1.0
    reasoning: str = ""
    target_element_id: str | None = None
    requires_confirmation: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScreenObservation:
    """Screen state observation including visual and structural metadata."""

    screenshot_path: str | None = None
    som_screenshot_path: str | None = None
    base64_image: str | None = None
    som_base64_image: str | None = None
    active_window: str = ""
    screen_width: int = 1920
    screen_height: int = 1080
    detected_elements: list[dict[str, Any]] = field(default_factory=list)
    ocr_text_snippets: list[str] = field(default_factory=list)
    timestamp: float = 0.0


@dataclass
class StepRecord:
    """Execution trace of a single computer-use step."""

    step_number: int
    observation: ScreenObservation
    thought: str
    action: ComputerAction
    action_result: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: str | None = None
    elapsed_seconds: float = 0.0


@dataclass
class SteeringInstruction:
    """Live conversational steering instruction provided by the user."""

    instruction: str
    interrupt_current_action: bool = False
    user_confirmed: bool | None = None
    new_target: str | None = None
