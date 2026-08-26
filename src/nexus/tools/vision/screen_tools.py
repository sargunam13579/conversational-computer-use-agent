"""
NEXUS Vision & Screen Tools.

Provides LLM tools for:
- Describing screen contents
- Locating UI elements
- Clicking UI elements
- Typing into input fields
- Extracting text via OCR
- Identifying active windows
"""

from __future__ import annotations

import importlib
import platform
import time
from typing import Any

from nexus.tools.base import BaseTool, RiskLevel, TargetDevice, ToolResult
from nexus.utils.logging import get_logger
from nexus.vision.analyzer import ScreenAnalyzer
from nexus.vision.capture import ScreenCaptureController
from nexus.vision.ocr import ScreenOCR

log = get_logger("tools.vision.screen")

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


# ---------------------------------------------------------------------------
# Describe Screen
# ---------------------------------------------------------------------------


class DescribeScreenTool(BaseTool):
    """Describe what is currently displayed on the laptop screen."""

    def __init__(self, analyzer: ScreenAnalyzer | None = None) -> None:
        self._analyzer = analyzer or ScreenAnalyzer()

    @property
    def name(self) -> str:
        return "describe_screen"

    @property
    def description(self) -> str:
        return (
            "Analyze and describe what is currently visible on the laptop screen: "
            "the active application, open documents, buttons, input fields, menus, "
            "and text content."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "crop_to_active_window": {
                    "type": "boolean",
                    "description": (
                        "Whether to focus analysis exclusively on the foreground "
                        "window (default: false)."
                    ),
                },
            },
            "required": [],
        }

    @property
    def category(self) -> str:
        return "vision"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(self, crop_to_active_window: bool = False, **kwargs: Any) -> ToolResult:
        report = await self._analyzer.analyze_screen(crop_to_active_window=crop_to_active_window)
        return ToolResult.ok(
            report.description,
            app_name=report.app_name,
            window_title=report.window_title,
            buttons=report.buttons,
            input_fields=report.input_fields,
            menus=report.menus,
            ocr_text_preview=report.ocr_text_preview,
        )


# ---------------------------------------------------------------------------
# Locate UI Element
# ---------------------------------------------------------------------------


class LocateElementTool(BaseTool):
    """Locate a UI element on screen by name or label."""

    def __init__(self, analyzer: ScreenAnalyzer | None = None) -> None:
        self._analyzer = analyzer or ScreenAnalyzer()

    @property
    def name(self) -> str:
        return "locate_ui_element"

    @property
    def description(self) -> str:
        return (
            "Find the position and coordinates of a specific UI element on the laptop screen "
            "(e.g. 'Run button', 'Search box', 'File menu', 'Submit')."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "element_name": {
                    "type": "string",
                    "description": (
                        "Name, label, or keyword of the UI element to find "
                        "(e.g. 'Run', 'Search', 'Close')."
                    ),
                },
                "element_type": {
                    "type": "string",
                    "enum": ["button", "input_field", "menu_item", "tab", "checkbox", "any"],
                    "description": "Optional element type filter (default: 'any').",
                },
            },
            "required": ["element_name"],
        }

    @property
    def category(self) -> str:
        return "vision"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self, element_name: str = "", element_type: str = "any", **kwargs: Any
    ) -> ToolResult:
        if not element_name:
            return ToolResult.fail("Parameter 'element_name' is required.")
        target_type = None if element_type == "any" else element_type
        element, explanation = self._analyzer.locate_element(element_name, element_type=target_type)

        if not element:
            return ToolResult.fail(explanation)

        cx, cy = element.center
        return ToolResult.ok(
            explanation,
            name=element.name,
            type=element.element_type.value,
            x=element.x,
            y=element.y,
            cx=cx,
            cy=cy,
            width=element.width,
            height=element.height,
            relative_position=element.relative_position,
        )


# ---------------------------------------------------------------------------
# Click UI Element
# ---------------------------------------------------------------------------


class ClickElementTool(BaseTool):
    """Click on a specific UI element or screen coordinates."""

    def __init__(self, analyzer: ScreenAnalyzer | None = None) -> None:
        self._analyzer = analyzer or ScreenAnalyzer()

    @property
    def name(self) -> str:
        return "click_ui_element"

    @property
    def description(self) -> str:
        return (
            "Click on a UI element on screen by its label/name (e.g. 'Run', 'Submit', 'OK') "
            "or direct screen coordinates (x, y)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "element_name": {
                    "type": "string",
                    "description": "Label or name of the UI element to click (e.g. 'Run').",
                },
                "x": {
                    "type": "integer",
                    "description": "Optional direct X screen coordinate.",
                },
                "y": {
                    "type": "integer",
                    "description": "Optional direct Y screen coordinate.",
                },
                "double_click": {
                    "type": "boolean",
                    "description": "Whether to perform a double click (default: false).",
                },
            },
            "required": [],
        }

    @property
    def category(self) -> str:
        return "vision"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self,
        element_name: str | None = None,
        x: int | None = None,
        y: int | None = None,
        double_click: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        target_x, target_y = x, y
        target_label = element_name

        if target_x is None or target_y is None:
            if not element_name:
                return ToolResult.fail(
                    "Please provide either 'element_name' or '(x, y)' coordinates to click."
                )
            element, _ = self._analyzer.locate_element(element_name)
            if not element:
                return ToolResult.fail(f"Could not find UI element '{element_name}' to click.")
            target_x, target_y = element.center
            target_label = element.name

        # Perform mouse click via ctypes or pyautogui
        if platform.system() == "Windows":
            try:
                import ctypes

                user32 = ctypes.windll.user32
                user32.SetCursorPos(target_x, target_y)
                time.sleep(0.05)

                user32.mouse_event(MOUSEEVENTF_LEFTDOWN, target_x, target_y, 0, 0)
                user32.mouse_event(MOUSEEVENTF_LEFTUP, target_x, target_y, 0, 0)

                if double_click:
                    time.sleep(0.1)
                    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, target_x, target_y, 0, 0)
                    user32.mouse_event(MOUSEEVENTF_LEFTUP, target_x, target_y, 0, 0)
            except Exception as e:
                log.warning("ctypes click failed: %s, trying pyautogui fallback", e)
                try:
                    pyautogui: Any = importlib.import_module("pyautogui")

                    if double_click:
                        pyautogui.doubleClick(target_x, target_y)
                    else:
                        pyautogui.click(target_x, target_y)
                except Exception as py_err:
                    return ToolResult.fail(f"Mouse click failed: {py_err}")

        action_name = "Double-clicked" if double_click else "Clicked"
        return ToolResult.ok(
            f"Successfully {action_name.lower()} '{target_label}' at (x={target_x}, y={target_y}).",
            label=target_label,
            x=target_x,
            y=target_y,
        )


# ---------------------------------------------------------------------------
# Type into Element
# ---------------------------------------------------------------------------


class TypeIntoElementTool(BaseTool):
    """Type text into an input field or active element."""

    def __init__(self, analyzer: ScreenAnalyzer | None = None) -> None:
        self._analyzer = analyzer or ScreenAnalyzer()

    @property
    def name(self) -> str:
        return "type_into_element"

    @property
    def description(self) -> str:
        return "Focus an input field on screen and type text into it."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to type into the element.",
                },
                "element_name": {
                    "type": "string",
                    "description": "Optional name of the input field to click and focus first.",
                },
                "press_enter": {
                    "type": "boolean",
                    "description": "Whether to press Enter after typing (default: false).",
                },
            },
            "required": ["text"],
        }

    @property
    def category(self) -> str:
        return "vision"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self,
        text: str = "",
        element_name: str | None = None,
        press_enter: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        if not text:
            return ToolResult.fail("Parameter 'text' cannot be empty.")
        if element_name:
            element, _ = self._analyzer.locate_element(element_name, element_type="input_field")
            if element:
                cx, cy = element.center
                if platform.system() == "Windows":
                    import ctypes

                    ctypes.windll.user32.SetCursorPos(cx, cy)
                    ctypes.windll.user32.mouse_event(0x0002, cx, cy, 0, 0)
                    ctypes.windll.user32.mouse_event(0x0004, cx, cy, 0, 0)
                    time.sleep(0.1)

        if platform.system() == "Windows":
            try:
                pyautogui: Any = importlib.import_module("pyautogui")

                pyautogui.write(text, interval=0.01)
                if press_enter:
                    pyautogui.press("enter")
            except Exception:
                # PowerShell fallback SendKeys
                import subprocess

                ps_script = f"""
                $wsh = New-Object -ComObject WScript.Shell
                $wsh.SendKeys('{text}')
                """
                if press_enter:
                    ps_script += "\n$wsh.SendKeys('{ENTER}')"
                subprocess.run(
                    ["powershell", "-Command", ps_script], capture_output=True, timeout=5
                )

        target_label = element_name or "active element"
        msg = f"Successfully typed text into '{target_label}' ({len(text)} characters)."
        return ToolResult.ok(
            msg,
            text_length=len(text),
        )


# ---------------------------------------------------------------------------
# Read Screen Text (OCR)
# ---------------------------------------------------------------------------


class ReadScreenTextTool(BaseTool):
    """Read all visible text from the screen using OCR."""

    def __init__(
        self,
        capture_ctrl: ScreenCaptureController | None = None,
        ocr_engine: ScreenOCR | None = None,
    ) -> None:
        self._capture = capture_ctrl or ScreenCaptureController()
        self._ocr = ocr_engine or ScreenOCR()

    @property
    def name(self) -> str:
        return "read_screen_text"

    @property
    def description(self) -> str:
        return (
            "Extract and read all visible text and captions currently displayed on the "
            "laptop screen via OCR."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "crop_to_active_window": {
                    "type": "boolean",
                    "description": (
                        "Whether to extract text only from active foreground "
                        "window (default: false)."
                    ),
                },
            },
            "required": [],
        }

    @property
    def category(self) -> str:
        return "vision"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(self, crop_to_active_window: bool = False, **kwargs: Any) -> ToolResult:
        cap_res = await self._capture.capture(crop_to_active_window=crop_to_active_window)
        if not cap_res.success:
            return ToolResult.fail(f"Could not capture screen for OCR: {cap_res.error}")

        target_img = cap_res.image_path or cap_res.image
        if target_img is None:
            return ToolResult.fail("No screenshot image available for OCR.")

        ocr_res = await self._ocr.recognize(target_img)
        summary = (
            f"Extracted {ocr_res.word_count} words across {ocr_res.line_count} lines:\n\n"
            f"{ocr_res.full_text or '(No visible text detected)'}"
        )
        return ToolResult.ok(
            summary,
            full_text=ocr_res.full_text,
            word_count=ocr_res.word_count,
            line_count=ocr_res.line_count,
        )


# ---------------------------------------------------------------------------
# Get Active Window
# ---------------------------------------------------------------------------


class GetActiveWindowTool(BaseTool):
    """Get information about the current foreground window."""

    def __init__(self, capture_ctrl: ScreenCaptureController | None = None) -> None:
        self._capture = capture_ctrl or ScreenCaptureController()

    @property
    def name(self) -> str:
        return "get_active_window"

    @property
    def description(self) -> str:
        return (
            "Get details about the current active foreground window: "
            "title, process name, PID, and dimensions."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    @property
    def category(self) -> str:
        return "vision"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(self, **kwargs: Any) -> ToolResult:
        win = self._capture.get_active_window_info()
        if not win:
            return ToolResult.ok("No active foreground window detected.", active=False)

        info_text = (
            f"Active Window: '{win.title}'\n"
            f"Process: {win.process_name} (PID: {win.pid})\n"
            f"Bounds: x={win.x}, y={win.y}, width={win.width}, height={win.height}"
        )
        return ToolResult.ok(
            info_text,
            title=win.title,
            process=win.process_name,
            pid=win.pid,
            bounds=win.bounds,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_vision_tools() -> list[BaseTool]:
    """Return all vision and screen automation tools."""
    return [
        DescribeScreenTool(),
        LocateElementTool(),
        ClickElementTool(),
        TypeIntoElementTool(),
        ReadScreenTextTool(),
        GetActiveWindowTool(),
    ]
