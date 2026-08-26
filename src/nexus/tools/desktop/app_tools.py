"""
NEXUS Desktop Application Automation Tools.

Provides high-level tools for active application interaction, scrolling,
reading UI elements, and executing multi-step workflows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nexus.automation.app_controller import DesktopAppController
from nexus.automation.ui_interaction import DesktopUIInteraction
from nexus.automation.workflow import MultiStepWorkflowEngine
from nexus.tools.base import BaseTool, RiskLevel, TargetDevice, ToolResult
from nexus.utils.logging import get_logger

if TYPE_CHECKING:
    from nexus.vision.ui_detector import UIElementDetector

log = get_logger("tools.desktop.app")


# ---------------------------------------------------------------------------
# Interact Desktop App
# ---------------------------------------------------------------------------


class InteractAppTool(BaseTool):
    """Interact with elements or send shortcuts to the active desktop application."""

    def __init__(
        self,
        app_ctrl: DesktopAppController | None = None,
        ui_interact: DesktopUIInteraction | None = None,
    ) -> None:
        self._app_ctrl = app_ctrl or DesktopAppController()
        self._ui_interact = ui_interact or DesktopUIInteraction(app_controller=self._app_ctrl)

    @property
    def name(self) -> str:
        return "interact_desktop_app"

    @property
    def description(self) -> str:
        return (
            "Interact with the active desktop application: click a UI button/element, "
            "focus window, or send a hotkey shortcut (e.g. 'ctrl+s', 'alt+f4')."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "element_name": {
                    "type": "string",
                    "description": "Name or label of the UI element to click (e.g. 'Save', 'Run').",
                },
                "hotkey": {
                    "type": "string",
                    "description": "Optional keyboard shortcut to send (e.g. 'ctrl+s', 'alt+f4').",
                },
                "app_name": {
                    "type": "string",
                    "description": "Optional application name to focus first.",
                },
            },
            "required": [],
        }

    @property
    def category(self) -> str:
        return "desktop"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self,
        element_name: str | None = None,
        hotkey: str | None = None,
        app_name: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        if app_name:
            self._app_ctrl.focus_app(app_name)

        if element_name:
            success = self._ui_interact.click_element(element_name)
            if success:
                return ToolResult.ok(f"Successfully clicked '{element_name}' in desktop app.")
            return ToolResult.fail(f"Could not find or click element '{element_name}'.")

        if hotkey:
            keys = [k.strip().lower() for k in hotkey.split("+")]
            success = self._ui_interact.send_hotkey(*keys)
            if success:
                return ToolResult.ok(f"Successfully sent hotkey '{hotkey}'.")
            return ToolResult.fail(f"Could not send hotkey '{hotkey}'.")

        active = self._app_ctrl.get_active_app()
        if active:
            msg = (
                f"Active application: '{active.name}' "
                f"(Title: '{active.window_title}', PID: {active.pid})."
            )
            return ToolResult.ok(
                msg,
                name=active.name,
                title=active.window_title,
                pid=active.pid,
            )

        return ToolResult.fail("Please provide either 'element_name', 'hotkey', or 'app_name'.")


# ---------------------------------------------------------------------------
# Scroll Desktop App
# ---------------------------------------------------------------------------


class ScrollAppTool(BaseTool):
    """Scroll the active desktop application window."""

    def __init__(self, ui_interact: DesktopUIInteraction | None = None) -> None:
        self._ui_interact = ui_interact or DesktopUIInteraction()

    @property
    def name(self) -> str:
        return "scroll_desktop_app"

    @property
    def description(self) -> str:
        return "Scroll the active desktop application window up or down."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["down", "up"],
                    "description": "Scroll direction (default: down).",
                },
                "clicks": {
                    "type": "integer",
                    "description": "Number of scroll wheel steps (default: 5).",
                },
            },
            "required": [],
        }

    @property
    def category(self) -> str:
        return "desktop"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(self, direction: str = "down", clicks: int = 5, **kwargs: Any) -> ToolResult:
        success = self._ui_interact.scroll(direction=direction, clicks=clicks)
        if success:
            return ToolResult.ok(f"Scrolled active desktop window {direction} ({clicks} steps).")
        return ToolResult.fail("Could not scroll desktop window.")


# ---------------------------------------------------------------------------
# Read App Content
# ---------------------------------------------------------------------------


class ReadAppContentTool(BaseTool):
    """Read visible interactive elements and text from the active application."""

    def __init__(
        self,
        app_ctrl: DesktopAppController | None = None,
        detector: UIElementDetector | None = None,
    ) -> None:
        self._app_ctrl = app_ctrl or DesktopAppController()
        self._detector = detector

    def _get_detector(self) -> Any:
        if self._detector is None:
            from nexus.vision.ui_detector import UIElementDetector

            self._detector = UIElementDetector()
        return self._detector

    @property
    def name(self) -> str:
        return "read_app_content"

    @property
    def description(self) -> str:
        return (
            "Read all visible buttons, input fields, menus, and text from the active application."
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
        return "desktop"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(self, **kwargs: Any) -> ToolResult:
        active = self._app_ctrl.get_active_app()
        win_title = active.window_title if active else None
        detector = self._get_detector()
        elements = detector.detect_elements(window_title=win_title)

        buttons = [e.name for e in elements if e.element_type.value == "button" and e.name]
        inputs = [e.name for e in elements if e.element_type.value == "input_field" and e.name]
        menus = [e.name for e in elements if "menu" in e.element_type.value and e.name]

        summary = (
            f"Active Window: '{win_title or 'Desktop'}'\n"
            f"Buttons ({len(buttons)}): {', '.join(buttons[:10]) or 'None'}\n"
            f"Inputs ({len(inputs)}): {', '.join(inputs[:10]) or 'None'}\n"
            f"Menus ({len(menus)}): {', '.join(menus[:10]) or 'None'}"
        )
        return ToolResult.ok(
            summary,
            window_title=win_title,
            buttons=buttons,
            inputs=inputs,
            menus=menus,
            total_elements=len(elements),
        )


# ---------------------------------------------------------------------------
# Multi-Step Workflow Tool
# ---------------------------------------------------------------------------


class MultiStepTaskTool(BaseTool):
    """Execute high-level chained workflows (e.g. search and read, search and download)."""

    def __init__(self, workflow_engine: MultiStepWorkflowEngine | None = None) -> None:
        self._engine = workflow_engine or MultiStepWorkflowEngine()

    @property
    def name(self) -> str:
        return "execute_multistep_task"

    @property
    def description(self) -> str:
        return (
            "Execute end-to-end multi-step tasks across browser and system. "
            "Task types: 'search_and_read' (search web + report), "
            "'search_and_download' (search + identify file + download + verify + move to folder)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_type": {
                    "type": "string",
                    "enum": ["search_and_read", "search_and_download"],
                    "description": "Type of multi-step workflow to run.",
                },
                "query": {
                    "type": "string",
                    "description": "Search query keywords.",
                },
                "file_extension": {
                    "type": "string",
                    "description": "Target file extension for download (default: 'pdf').",
                },
                "destination_folder": {
                    "type": "string",
                    "description": "Target folder for downloaded file (default: 'Documents').",
                },
            },
            "required": ["task_type", "query"],
        }

    @property
    def category(self) -> str:
        return "desktop"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self,
        task_type: str = "search_and_read",
        query: str = "",
        file_extension: str = "pdf",
        destination_folder: str = "Documents",
        **kwargs: Any,
    ) -> ToolResult:
        if not query:
            return ToolResult.fail("Parameter 'query' is required.")

        if task_type == "search_and_read":
            result = await self._engine.execute_web_search_and_read(query=query)
            if result.success:
                return ToolResult.ok(result.summary, data=result.final_data)
            return ToolResult.fail(result.summary)

        elif task_type == "search_and_download":
            result = await self._engine.execute_search_download_and_file(
                search_query=query,
                file_extension=file_extension,
                destination_folder=destination_folder,
            )
            if result.success:
                return ToolResult.ok(result.summary, data=result.final_data)
            return ToolResult.fail(result.summary)

        return ToolResult.fail(
            f"Unknown task_type '{task_type}'. Valid: search_and_read, search_and_download."
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_desktop_automation_tools() -> list[BaseTool]:
    """Return all desktop automation tools."""
    return [
        InteractAppTool(),
        ScrollAppTool(),
        ReadAppContentTool(),
        MultiStepTaskTool(),
    ]
