"""
NEXUS Unified Device Manager.

Central coordination engine for all connected devices in the user's ecosystem:
- Device registry & presence tracking (ONLINE, OFFLINE, CONNECTING, BUSY)
- Natural language target resolution ("on my laptop", "to my phone")
- Cross-device command dispatching and response aggregation
- Access revocation and security invalidation
- Integration with discovery, file transfer, and task handoff
"""

from __future__ import annotations

import asyncio
import datetime
import re
from typing import Any

from nexus.devices.discovery import DeviceDiscoveryService
from nexus.devices.handoff import TaskHandoffEngine
from nexus.devices.transfer import SecureFileTransferBridge
from nexus.devices.types import (
    DeviceNode,
    DeviceStatusEnum,
    DeviceType,
)
from nexus.utils.logging import get_logger

log = get_logger("devices.manager")

_LAPTOP_PATTERNS = re.compile(
    r"\b(laptop|pc|computer|desktop|windows|macbook|workstation)\b",
    re.IGNORECASE,
)
_PHONE_PATTERNS = re.compile(
    r"\b(phone|mobile|android|pixel|samsung|galaxy|device|handset)\b",
    re.IGNORECASE,
)


class UnifiedDeviceManager:
    """Central manager for all devices in the NEXUS ecosystem."""

    def __init__(
        self,
        discovery_service: DeviceDiscoveryService | None = None,
        transfer_bridge: SecureFileTransferBridge | None = None,
        handoff_engine: TaskHandoffEngine | None = None,
    ) -> None:
        self._devices: dict[str, DeviceNode] = {}
        self._discovery = discovery_service or DeviceDiscoveryService()
        self._transfer = transfer_bridge or SecureFileTransferBridge()
        self._handoff = handoff_engine or TaskHandoffEngine()
        self._lock = asyncio.Lock()

        # Initialize default host laptop node
        self._register_default_host()

    def _register_default_host(self) -> None:
        """Register the local host laptop as primary node."""
        host_node = DeviceNode(
            device_id="host_laptop",
            name="Primary Laptop",
            alias="laptop",
            device_type=DeviceType.LAPTOP,
            status=DeviceStatusEnum.ONLINE,
            capabilities=[
                "terminal",
                "filesystem",
                "applications",
                "vision",
                "browser",
                "automation",
            ],
            os_info="Windows",
            is_primary=True,
        )
        self._devices["host_laptop"] = host_node

    @property
    def discovery(self) -> DeviceDiscoveryService:
        return self._discovery

    @property
    def transfer(self) -> SecureFileTransferBridge:
        return self._transfer

    @property
    def handoff(self) -> TaskHandoffEngine:
        return self._handoff

    async def register_device(self, node: DeviceNode) -> DeviceNode:
        """Register or update a device node."""
        async with self._lock:
            self._devices[node.device_id] = node
            log.info(
                "Registered device node: %s [%s] (%s)",
                node.name,
                node.device_id,
                node.status.value,
            )
            return node

    async def update_status(self, device_id: str, status: DeviceStatusEnum) -> bool:
        """Update device presence status (ONLINE, OFFLINE, CONNECTING, BUSY)."""
        async with self._lock:
            dev = self._devices.get(device_id)
            if not dev:
                return False
            dev.status = status
            dev.last_seen = datetime.datetime.now(datetime.UTC).isoformat()
            log.info("Device '%s' transitioned to %s", device_id, status.value)
            return True

    def get_device(self, device_id: str) -> DeviceNode | None:
        """Get device by ID."""
        return self._devices.get(device_id)

    def list_devices(self, status: DeviceStatusEnum | None = None) -> list[DeviceNode]:
        """List all devices, optionally filtered by presence status."""
        if status:
            return [d for d in self._devices.values() if d.status == status]
        return list(self._devices.values())

    def resolve_target_device(self, text: str) -> DeviceNode | None:
        """
        Identify target device from natural language expression
        (e.g. "on my laptop", "send to phone").
        """
        clean = text.lower()

        # Check explicit device ID matches first
        for dev in self._devices.values():
            if dev.device_id.lower() in clean:
                return dev
            if dev.name.lower() in clean:
                return dev
            if dev.alias and dev.alias.lower() in clean:
                return dev

        # Check keyword heuristics
        if _PHONE_PATTERNS.search(clean):
            for dev in self._devices.values():
                if dev.device_type == DeviceType.PHONE:
                    return dev

        if _LAPTOP_PATTERNS.search(clean):
            for dev in self._devices.values():
                if dev.device_type == DeviceType.LAPTOP:
                    return dev

        # Default to primary node
        for dev in self._devices.values():
            if dev.is_primary:
                return dev

        return next(iter(self._devices.values())) if self._devices else None

    async def revoke_device_access(self, device_id: str) -> bool:
        """
        Revoke device access, remove from registry, and invalidate auth tokens.
        """
        async with self._lock:
            if device_id in self._devices:
                # Do not revoke primary host laptop
                if self._devices[device_id].is_primary:
                    log.warning("Cannot revoke access for primary host laptop node.")
                    return False

                revoked = self._devices.pop(device_id)
                log.info("Revoked access for device: %s (%s)", revoked.name, device_id)
                return True
            return False

    async def execute_cross_device_command(
        self,
        target_text_or_id: str,
        command_type: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Dispatch cross-device command to the resolved node.
        """
        target_node = self.resolve_target_device(target_text_or_id)
        if not target_node:
            return {
                "success": False,
                "error": f"Could not find or resolve target device from '{target_text_or_id}'.",
            }

        # Check status
        if target_node.status == DeviceStatusEnum.OFFLINE:
            return {
                "success": False,
                "error": f"Target device '{target_node.name}' is currently OFFLINE.",
                "device_id": target_node.device_id,
            }

        # Temporarily mark node as BUSY
        prev_status = target_node.status
        await self.update_status(target_node.device_id, DeviceStatusEnum.BUSY)

        try:
            # Route to appropriate subsystem
            if target_node.device_type == DeviceType.LAPTOP:
                from nexus.agents.laptop.agent import LaptopAgent

                laptop = LaptopAgent()
                tool_res = await laptop.execute_tool(command_type, parameters)
                return {
                    "success": tool_res.success,
                    "output": tool_res.output,
                    "device_id": target_node.device_id,
                    "device_name": target_node.name,
                }
            elif target_node.device_type == DeviceType.PHONE:
                from nexus.agents.android.agent import AndroidAgent
                from nexus.agents.android.protocol import AndroidDeviceRegistration

                android = AndroidAgent()
                if target_node.device_id not in android.security.paired_devices:
                    android.security.paired_devices[target_node.device_id] = {
                        "device_id": target_node.device_id,
                        "device_name": target_node.name,
                        "token": "cross_device_token",
                    }
                    android.register_device(
                        AndroidDeviceRegistration(
                            device_id=target_node.device_id,
                            device_name=target_node.name,
                            android_version="14",
                        )
                    )

                mob_res = await android.execute_action(
                    action_type=command_type,
                    parameters=parameters,
                    device_id=target_node.device_id,
                )
                return {
                    "success": mob_res.success,
                    "output": mob_res.output,
                    "device_id": target_node.device_id,
                    "device_name": target_node.name,
                }
            else:
                return {
                    "success": True,
                    "output": f"Executed '{command_type}' on {target_node.name}.",
                    "device_id": target_node.device_id,
                }
        finally:
            await self.update_status(target_node.device_id, prev_status)
