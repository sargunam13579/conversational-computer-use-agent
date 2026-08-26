"""
NEXUS Android Mobile Tools for LLM & Agents.

Exposes official Android device capabilities to the NEXUS Brain:
- App launching
- Accessibility UI interaction
- Notification reading
- Media & volume control
- Alarms & timers
- Device settings
- Hardware actions (flashlight, battery)
- File management
- Camera capture
- Call & SMS assistance with confirmation
"""

from __future__ import annotations

from typing import Any

from nexus.agents.android.agent import AndroidAgent
from nexus.tools.base import BaseTool, RiskLevel, TargetDevice, ToolResult
from nexus.utils.logging import get_logger

log = get_logger("tools.android.mobile")

# Default shared agent instance
_default_android_agent = AndroidAgent()


# ---------------------------------------------------------------------------
# 1. Launch App Tool
# ---------------------------------------------------------------------------


class AndroidLaunchAppTool(BaseTool):
    """Launch an application on the connected Android phone."""

    def __init__(self, agent: AndroidAgent | None = None) -> None:
        self._agent = agent or _default_android_agent

    @property
    def name(self) -> str:
        return "android_launch_app"

    @property
    def description(self) -> str:
        return "Launch an application on the connected Android device by app or package name."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": (
                        "Name or package of the app to launch "
                        "(e.g. 'Spotify', 'WhatsApp', 'com.google.android.youtube')."
                    ),
                },
            },
            "required": ["app_name"],
        }

    @property
    def category(self) -> str:
        return "android"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.ANDROID

    async def execute(self, app_name: str = "", **kwargs: Any) -> ToolResult:
        if not app_name:
            return ToolResult.fail("Parameter 'app_name' is required.")

        res = await self._agent.execute_action(
            action_type="launch_app",
            parameters={"app_name": app_name},
        )
        if res.success:
            return ToolResult.ok(
                f"Successfully launched '{app_name}' on Android device.",
                app_name=app_name,
            )
        return ToolResult.fail(res.error or res.output)


# ---------------------------------------------------------------------------
# 2. UI Interaction Tool (Accessibility)
# ---------------------------------------------------------------------------


class AndroidUIInteractTool(BaseTool):
    """Interact with Android UI via Accessibility Service (click, scroll, type, gestures)."""

    def __init__(self, agent: AndroidAgent | None = None) -> None:
        self._agent = agent or _default_android_agent

    @property
    def name(self) -> str:
        return "android_ui_interact"

    @property
    def description(self) -> str:
        return (
            "Perform accessibility UI actions on Android device: 'click', 'type', 'scroll', "
            "'back', 'home', or 'recents'."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["click", "type", "scroll", "back", "home", "recents"],
                    "description": "UI action to perform.",
                },
                "target_text": {
                    "type": "string",
                    "description": "Text, button label, or content description to click/type into.",
                },
                "input_text": {
                    "type": "string",
                    "description": "Text to type if action is 'type'.",
                },
                "direction": {
                    "type": "string",
                    "enum": ["down", "up", "left", "right"],
                    "description": "Scroll direction (default: down).",
                },
            },
            "required": ["action"],
        }

    @property
    def category(self) -> str:
        return "android"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.ANDROID

    async def execute(
        self,
        action: str = "click",
        target_text: str | None = None,
        input_text: str | None = None,
        direction: str = "down",
        **kwargs: Any,
    ) -> ToolResult:
        res = await self._agent.execute_action(
            action_type="ui_interact",
            parameters={
                "action": action,
                "target_text": target_text,
                "input_text": input_text,
                "direction": direction,
            },
        )
        if res.success:
            return ToolResult.ok(f"Android UI action '{action}' completed.", data=res.data)
        return ToolResult.fail(res.error or res.output)


# ---------------------------------------------------------------------------
# 3. Read Notifications Tool
# ---------------------------------------------------------------------------


class AndroidReadNotificationsTool(BaseTool):
    """Read recent notifications from Android device with NotificationListener permission."""

    def __init__(self, agent: AndroidAgent | None = None) -> None:
        self._agent = agent or _default_android_agent

    @property
    def name(self) -> str:
        return "android_read_notifications"

    @property
    def description(self) -> str:
        return "Read recent notifications received on the connected Android phone."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of recent notifications to retrieve (default: 10).",
                },
            },
            "required": [],
        }

    @property
    def category(self) -> str:
        return "android"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.ANDROID

    async def execute(self, limit: int = 10, **kwargs: Any) -> ToolResult:
        notifs = self._agent.bridge.get_recent_notifications(limit=limit)
        if not notifs:
            return ToolResult.ok("No unread mobile notifications.", count=0, notifications=[])

        lines = [f"Recent Android Notifications ({len(notifs)}):"]
        for n in notifs:
            lines.append(f"- [{n.app_name}] {n.title}: {n.text}")

        return ToolResult.ok(
            "\n".join(lines),
            count=len(notifs),
            notifications=[n.model_dump() for n in notifs],
        )


# ---------------------------------------------------------------------------
# 4. Media Control Tool
# ---------------------------------------------------------------------------


class AndroidMediaControlTool(BaseTool):
    """Control active audio/media playback on Android phone."""

    def __init__(self, agent: AndroidAgent | None = None) -> None:
        self._agent = agent or _default_android_agent

    @property
    def name(self) -> str:
        return "android_media_control"

    @property
    def description(self) -> str:
        return "Control media playback on Android: 'play', 'pause', 'toggle', 'next', 'previous'."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["play", "pause", "toggle", "next", "previous"],
                    "description": "Media transport action.",
                },
            },
            "required": ["action"],
        }

    @property
    def category(self) -> str:
        return "android"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.ANDROID

    async def execute(self, action: str = "toggle", **kwargs: Any) -> ToolResult:
        res = await self._agent.execute_action(
            action_type="media_control",
            parameters={"action": action},
        )
        if res.success:
            return ToolResult.ok(f"Media action '{action}' executed on phone.")
        return ToolResult.fail(res.error or res.output)


# ---------------------------------------------------------------------------
# 5. Volume Control Tool
# ---------------------------------------------------------------------------


class AndroidVolumeControlTool(BaseTool):
    """Adjust or mute volume on Android phone."""

    def __init__(self, agent: AndroidAgent | None = None) -> None:
        self._agent = agent or _default_android_agent

    @property
    def name(self) -> str:
        return "android_volume_control"

    @property
    def description(self) -> str:
        return "Adjust Android phone volume: 'set', 'step_up', 'step_down', 'mute', 'unmute'."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["set", "step_up", "step_down", "mute", "unmute"],
                    "description": "Volume action to perform.",
                },
                "level": {
                    "type": "integer",
                    "description": "Target volume level (0 to 100).",
                },
                "stream": {
                    "type": "string",
                    "enum": ["media", "ring", "alarm", "notification"],
                    "description": "Audio stream (default: media).",
                },
            },
            "required": ["action"],
        }

    @property
    def category(self) -> str:
        return "android"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.ANDROID

    async def execute(
        self,
        action: str = "set",
        level: int | None = None,
        stream: str = "media",
        **kwargs: Any,
    ) -> ToolResult:
        res = await self._agent.execute_action(
            action_type="volume_control",
            parameters={"action": action, "level": level, "stream": stream},
        )
        if res.success:
            return ToolResult.ok(f"Android volume updated ({action}).")
        return ToolResult.fail(res.error or res.output)


# ---------------------------------------------------------------------------
# 6. Set Alarm / Reminder Tool
# ---------------------------------------------------------------------------


class AndroidSetAlarmTool(BaseTool):
    """Set an alarm, countdown timer, or reminder on Android phone."""

    def __init__(self, agent: AndroidAgent | None = None) -> None:
        self._agent = agent or _default_android_agent

    @property
    def name(self) -> str:
        return "android_set_alarm"

    @property
    def description(self) -> str:
        return "Set an alarm, timer, or reminder on the connected Android phone."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["alarm", "timer", "reminder"],
                    "description": "Type of alert to set.",
                },
                "hour": {"type": "integer", "description": "Hour (0-23) for alarm."},
                "minutes": {"type": "integer", "description": "Minute (0-59) for alarm."},
                "seconds": {"type": "integer", "description": "Seconds for timer."},
                "message": {"type": "string", "description": "Alert message."},
            },
            "required": ["type"],
        }

    @property
    def category(self) -> str:
        return "android"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.ANDROID

    async def execute(
        self,
        type: str = "alarm",
        hour: int | None = None,
        minutes: int | None = None,
        seconds: int | None = None,
        message: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        res = await self._agent.execute_action(
            action_type="set_alarm",
            parameters={
                "type": type,
                "hour": hour,
                "minutes": minutes,
                "seconds": seconds,
                "message": message,
            },
        )
        if res.success:
            return ToolResult.ok(f"Android {type} set successfully.")
        return ToolResult.fail(res.error or res.output)


# ---------------------------------------------------------------------------
# 7. Open Settings Tool
# ---------------------------------------------------------------------------


class AndroidOpenSettingsTool(BaseTool):
    """Open specific system settings page on Android phone."""

    def __init__(self, agent: AndroidAgent | None = None) -> None:
        self._agent = agent or _default_android_agent

    @property
    def name(self) -> str:
        return "android_open_settings"

    @property
    def description(self) -> str:
        return (
            "Open specific settings page on Android "
            "(e.g. 'wifi', 'bluetooth', 'battery', 'accessibility')."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "setting": {
                    "type": "string",
                    "enum": [
                        "wifi",
                        "bluetooth",
                        "battery",
                        "accessibility",
                        "display",
                        "sound",
                        "general",
                    ],
                    "description": "Settings section to open.",
                },
            },
            "required": ["setting"],
        }

    @property
    def category(self) -> str:
        return "android"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.ANDROID

    async def execute(self, setting: str = "general", **kwargs: Any) -> ToolResult:
        res = await self._agent.execute_action(
            action_type="open_settings",
            parameters={"setting": setting},
        )
        if res.success:
            return ToolResult.ok(f"Opened Android {setting} settings.")
        return ToolResult.fail(res.error or res.output)


# ---------------------------------------------------------------------------
# 8. Device Actions Tool (Flashlight, Battery, Vibration)
# ---------------------------------------------------------------------------


class AndroidDeviceActionTool(BaseTool):
    """Perform hardware actions on Android phone (flashlight, vibrate, battery info)."""

    def __init__(self, agent: AndroidAgent | None = None) -> None:
        self._agent = agent or _default_android_agent

    @property
    def name(self) -> str:
        return "android_device_action"

    @property
    def description(self) -> str:
        return (
            "Perform device actions: 'flashlight_on', 'flashlight_off', 'vibrate', 'get_battery'."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["flashlight_on", "flashlight_off", "vibrate", "get_battery"],
                    "description": "Hardware action.",
                },
            },
            "required": ["action"],
        }

    @property
    def category(self) -> str:
        return "android"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.ANDROID

    async def execute(self, action: str = "get_battery", **kwargs: Any) -> ToolResult:
        res = await self._agent.execute_action(
            action_type="device_action",
            parameters={"action": action},
        )
        if res.success:
            return ToolResult.ok(f"Device action '{action}' completed.", data=res.data)
        return ToolResult.fail(res.error or res.output)


# ---------------------------------------------------------------------------
# 9. Manage Files Tool
# ---------------------------------------------------------------------------


class AndroidManageFilesTool(BaseTool):
    """Manage files on Android storage (list, read, delete)."""

    def __init__(self, agent: AndroidAgent | None = None) -> None:
        self._agent = agent or _default_android_agent

    @property
    def name(self) -> str:
        return "android_manage_files"

    @property
    def description(self) -> str:
        return "Manage files on Android storage: 'list', 'read_info', 'delete'."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "read_info", "delete"],
                    "description": "File operation.",
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file path (e.g. 'Download', 'Documents').",
                },
            },
            "required": ["action"],
        }

    @property
    def category(self) -> str:
        return "android"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.ANDROID

    async def execute(
        self,
        action: str = "list",
        path: str = "Download",
        **kwargs: Any,
    ) -> ToolResult:
        req_confirm = action == "delete"
        res = await self._agent.execute_action(
            action_type="manage_files",
            parameters={"action": action, "path": path},
            requires_confirmation=req_confirm,
        )
        if res.success:
            return ToolResult.ok(
                f"Android file action '{action}' on '{path}' succeeded.",
                data=res.data,
            )
        return ToolResult.fail(res.error or res.output)


# ---------------------------------------------------------------------------
# 10. Camera Capture Tool
# ---------------------------------------------------------------------------


class AndroidCameraCaptureTool(BaseTool):
    """Capture a photo on-demand with active camera permission."""

    def __init__(self, agent: AndroidAgent | None = None) -> None:
        self._agent = agent or _default_android_agent

    @property
    def name(self) -> str:
        return "android_capture_photo"

    @property
    def description(self) -> str:
        return "Capture a photo using phone camera (requires camera permission)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "lens": {
                    "type": "string",
                    "enum": ["back", "front"],
                    "description": "Camera lens (default: back).",
                },
            },
            "required": [],
        }

    @property
    def category(self) -> str:
        return "android"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.ANDROID

    async def execute(self, lens: str = "back", **kwargs: Any) -> ToolResult:
        res = await self._agent.execute_action(
            action_type="capture_photo",
            parameters={"lens": lens},
        )
        if res.success:
            return ToolResult.ok(f"Photo captured using {lens} camera.", data=res.data)
        return ToolResult.fail(res.error or res.output)


# ---------------------------------------------------------------------------
# 11. Call & SMS Assistant Tool (With Mandatory Confirmation)
# ---------------------------------------------------------------------------


class AndroidCallSmsTool(BaseTool):
    """Assist with sending SMS or initiating a call with mandatory confirmation."""

    def __init__(self, agent: AndroidAgent | None = None) -> None:
        self._agent = agent or _default_android_agent

    @property
    def name(self) -> str:
        return "android_send_sms_or_call"

    @property
    def description(self) -> str:
        return "Draft or send an SMS, or initiate a phone call on Android (requires confirmation)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["send_sms", "call"],
                    "description": "Communication action.",
                },
                "phone_number": {
                    "type": "string",
                    "description": "Target recipient phone number.",
                },
                "message": {
                    "type": "string",
                    "description": "SMS message text (for send_sms action).",
                },
            },
            "required": ["action", "phone_number"],
        }

    @property
    def category(self) -> str:
        return "android"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.HIGH

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.ANDROID

    async def execute(
        self,
        action: str = "send_sms",
        phone_number: str = "",
        message: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        if not phone_number:
            return ToolResult.fail("Parameter 'phone_number' is required.")

        res = await self._agent.execute_action(
            action_type=action,
            parameters={"phone_number": phone_number, "message": message},
            requires_confirmation=True,
            confirmation_prompt=f"Confirm executing {action} to {phone_number}?",
        )
        if res.success:
            return ToolResult.ok(f"Android action '{action}' to {phone_number} initiated.")
        return ToolResult.fail(res.error or res.output)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_android_tools(agent: AndroidAgent | None = None) -> list[BaseTool]:
    """Return all Android mobile automation tools."""
    ag = agent or _default_android_agent
    return [
        AndroidLaunchAppTool(agent=ag),
        AndroidUIInteractTool(agent=ag),
        AndroidReadNotificationsTool(agent=ag),
        AndroidMediaControlTool(agent=ag),
        AndroidVolumeControlTool(agent=ag),
        AndroidSetAlarmTool(agent=ag),
        AndroidOpenSettingsTool(agent=ag),
        AndroidDeviceActionTool(agent=ag),
        AndroidManageFilesTool(agent=ag),
        AndroidCameraCaptureTool(agent=ag),
        AndroidCallSmsTool(agent=ag),
    ]
