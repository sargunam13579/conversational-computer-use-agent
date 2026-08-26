"""
NEXUS Cross-Device LLM Tools.

Exposes unified cross-device operations to the NEXUS Brain:
- Listing connected devices and presence status (ONLINE, OFFLINE, CONNECTING, BUSY)
- Executing cross-device commands (e.g. laptop executing command initiated from phone)
- Transferring files securely across devices
- Handing off workflows and active context across nodes
- Managing device access and revoking pairing permissions
"""

from __future__ import annotations

import contextlib
from typing import Any

from nexus.devices.manager import UnifiedDeviceManager
from nexus.devices.types import DeviceStatusEnum
from nexus.tools.base import BaseTool, RiskLevel, TargetDevice, ToolResult
from nexus.utils.logging import get_logger

log = get_logger("tools.devices")

# Shared default manager
_default_device_manager = UnifiedDeviceManager()


# ---------------------------------------------------------------------------
# 1. List Devices Tool
# ---------------------------------------------------------------------------


class ListDevicesTool(BaseTool):
    """List all registered devices in the NEXUS ecosystem and their statuses."""

    def __init__(self, manager: UnifiedDeviceManager | None = None) -> None:
        self._manager = manager or _default_device_manager

    @property
    def name(self) -> str:
        return "list_devices"

    @property
    def description(self) -> str:
        return (
            "List all registered devices in the NEXUS ecosystem (Laptop, Android phone, etc.) "
            "along with their status (ONLINE, OFFLINE, CONNECTING, BUSY) and capabilities."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "status_filter": {
                    "type": "string",
                    "enum": ["ONLINE", "OFFLINE", "CONNECTING", "BUSY"],
                    "description": "Optional status filter.",
                },
            },
            "required": [],
        }

    @property
    def category(self) -> str:
        return "devices"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LOCAL

    async def execute(self, status_filter: str | None = None, **kwargs: Any) -> ToolResult:
        st_enum = None
        if status_filter:
            with contextlib.suppress(ValueError):
                st_enum = DeviceStatusEnum(status_filter)

        devices = self._manager.list_devices(status=st_enum)
        if not devices:
            return ToolResult.ok("No devices found.", count=0, devices=[])

        lines = [f"Registered Ecosystem Devices ({len(devices)}):"]
        for d in devices:
            lines.append(
                f"- [{d.status.value}] {d.name} ({d.device_type.value}) "
                f"- ID: {d.device_id}, OS: {d.os_info}"
            )

        return ToolResult.ok(
            "\n".join(lines),
            count=len(devices),
            devices=[d.model_dump() for d in devices],
        )


# ---------------------------------------------------------------------------
# 2. Cross-Device Command Tool
# ---------------------------------------------------------------------------


class ExecuteCrossDeviceCommandTool(BaseTool):
    """Execute an action on a specific target device in the ecosystem."""

    def __init__(self, manager: UnifiedDeviceManager | None = None) -> None:
        self._manager = manager or _default_device_manager

    @property
    def name(self) -> str:
        return "cross_device_command"

    @property
    def description(self) -> str:
        return (
            "Dispatch and execute a command on a remote device "
            "(e.g. 'open my timetable project on my laptop', 'flashlight on on my phone')."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target_device": {
                    "type": "string",
                    "description": (
                        "Target device name, alias, or ID (e.g. 'laptop', 'phone', 'Pixel 8')."
                    ),
                },
                "command_type": {
                    "type": "string",
                    "description": "The command or tool name to execute on target device.",
                },
                "parameters": {
                    "type": "object",
                    "description": "Parameters for the command.",
                },
            },
            "required": ["target_device", "command_type"],
        }

    @property
    def category(self) -> str:
        return "devices"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LOCAL

    async def execute(
        self,
        target_device: str = "",
        command_type: str = "",
        parameters: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        if not target_device or not command_type:
            return ToolResult.fail("Parameters 'target_device' and 'command_type' are required.")

        res = await self._manager.execute_cross_device_command(
            target_text_or_id=target_device,
            command_type=command_type,
            parameters=parameters or {},
        )
        if res.get("success"):
            dev_label = res.get("device_name", target_device)
            out = res.get("output", "")
            return ToolResult.ok(
                f"Command executed on {dev_label}: {out}",
                data=res,
            )
        return ToolResult.fail(res.get("error", "Cross-device command failed."))


# ---------------------------------------------------------------------------
# 3. Transfer File Cross Device Tool
# ---------------------------------------------------------------------------


class TransferFileCrossDeviceTool(BaseTool):
    """Transfer a file securely between laptop and phone."""

    def __init__(self, manager: UnifiedDeviceManager | None = None) -> None:
        self._manager = manager or _default_device_manager

    @property
    def name(self) -> str:
        return "transfer_file_cross_device"

    @property
    def description(self) -> str:
        return "Transfer a file securely between devices with SHA-256 integrity verification."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_device": {
                    "type": "string",
                    "description": "Source device name or ID (default: current host laptop).",
                },
                "target_device": {
                    "type": "string",
                    "description": "Target device name or ID (e.g. 'phone', 'Pixel 8').",
                },
                "file_path": {
                    "type": "string",
                    "description": "Path of the file to transfer.",
                },
                "destination_folder": {
                    "type": "string",
                    "description": "Destination folder on target device (default: Documents).",
                },
            },
            "required": ["file_path", "target_device"],
        }

    @property
    def category(self) -> str:
        return "devices"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LOCAL

    async def execute(
        self,
        file_path: str = "",
        target_device: str = "",
        source_device: str = "host_laptop",
        destination_folder: str = "Documents",
        **kwargs: Any,
    ) -> ToolResult:
        if not file_path or not target_device:
            return ToolResult.fail("Parameters 'file_path' and 'target_device' are required.")

        target_node = self._manager.resolve_target_device(target_device)
        if not target_node:
            return ToolResult.fail(f"Could not resolve target device '{target_device}'.")

        manifest = await self._manager.transfer.prepare_transfer(
            source_device_id=source_device,
            target_device_id=target_node.device_id,
            file_path=file_path,
            destination_folder=destination_folder,
        )
        if not manifest:
            return ToolResult.fail(f"Could not locate file '{file_path}' to transfer.")

        return ToolResult.ok(
            f"Transfer initiated for '{manifest.file_name}' to {target_node.name} "
            f"(SHA-256: {manifest.sha256_checksum[:8]}...).",
            transfer_id=manifest.transfer_id,
            file_name=manifest.file_name,
            size_bytes=manifest.file_size_bytes,
        )


# ---------------------------------------------------------------------------
# 4. Task Handoff Tool
# ---------------------------------------------------------------------------


class HandoffTaskTool(BaseTool):
    """Migrate active workflow, open URLs, and context state to another device."""

    def __init__(self, manager: UnifiedDeviceManager | None = None) -> None:
        self._manager = manager or _default_device_manager

    @property
    def name(self) -> str:
        return "handoff_task"

    @property
    def description(self) -> str:
        return "Migrate an active task, browsing session, or context state to another device."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target_device": {
                    "type": "string",
                    "description": (
                        "Target device name or ID to migrate to (e.g. 'phone', 'laptop')."
                    ),
                },
                "task_description": {
                    "type": "string",
                    "description": "Summary description of the task being handed off.",
                },
                "open_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of URLs to open on destination device.",
                },
                "open_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of files relevant to the task.",
                },
            },
            "required": ["target_device", "task_description"],
        }

    @property
    def category(self) -> str:
        return "devices"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LOCAL

    async def execute(
        self,
        target_device: str = "",
        task_description: str = "",
        open_urls: list[str] | None = None,
        open_files: list[str] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        target_node = self._manager.resolve_target_device(target_device)
        if not target_node:
            return ToolResult.fail(f"Could not resolve destination device '{target_device}'.")

        payload = self._manager.handoff.create_handoff(
            source_device_id="host_laptop",
            target_device_id=target_node.device_id,
            task_description=task_description,
            open_urls=open_urls,
            open_files=open_files,
        )
        return ToolResult.ok(
            f"Successfully created task handoff to {target_node.name}: '{task_description}'",
            handoff_id=payload.handoff_id,
            target_device=target_node.name,
        )


# ---------------------------------------------------------------------------
# 5. Manage Device Access Tool
# ---------------------------------------------------------------------------


class ManageDeviceAccessTool(BaseTool):
    """Manage device settings, ping, or revoke device access."""

    def __init__(self, manager: UnifiedDeviceManager | None = None) -> None:
        self._manager = manager or _default_device_manager

    @property
    def name(self) -> str:
        return "manage_device_access"

    @property
    def description(self) -> str:
        return "Manage device ecosystem access: 'status', 'ping', or 'revoke'."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "ping", "revoke"],
                    "description": "Management action.",
                },
                "device_id": {
                    "type": "string",
                    "description": "Device ID or name to operate on.",
                },
            },
            "required": ["action"],
        }

    @property
    def category(self) -> str:
        return "devices"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LOCAL

    async def execute(
        self,
        action: str = "status",
        device_id: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        act = action.lower().strip()
        if act == "revoke":
            if not device_id:
                return ToolResult.fail("Parameter 'device_id' is required to revoke access.")
            node = self._manager.resolve_target_device(device_id)
            if not node:
                return ToolResult.fail(f"Device '{device_id}' not found.")

            revoked = await self._manager.revoke_device_access(node.device_id)
            if revoked:
                return ToolResult.ok(f"Successfully revoked access for device '{node.name}'.")
            return ToolResult.fail(f"Cannot revoke access for primary device '{node.name}'.")

        elif act == "ping":
            if not device_id:
                return ToolResult.fail("Parameter 'device_id' is required for ping.")
            node = self._manager.resolve_target_device(device_id)
            if not node:
                return ToolResult.fail(f"Device '{device_id}' not found.")
            return ToolResult.ok(f"Device '{node.name}' is {node.status.value}.")

        devices = self._manager.list_devices()
        return ToolResult.ok(
            f"Device Ecosystem: {len(devices)} registered devices.",
            devices=[d.model_dump() for d in devices],
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_device_tools(manager: UnifiedDeviceManager | None = None) -> list[BaseTool]:
    """Return all cross-device tools."""
    mgr = manager or _default_device_manager
    return [
        ListDevicesTool(manager=mgr),
        ExecuteCrossDeviceCommandTool(manager=mgr),
        TransferFileCrossDeviceTool(manager=mgr),
        HandoffTaskTool(manager=mgr),
        ManageDeviceAccessTool(manager=mgr),
    ]
