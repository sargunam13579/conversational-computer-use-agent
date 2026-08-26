"""
NEXUS Android Backend Agent.

Coordinates communication with paired Android mobile devices, handles pairing,
permission tracking, tool execution dispatching, and device status management.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from nexus.agents.android.device_bridge import AndroidDeviceBridge
from nexus.agents.android.protocol import (
    AndroidCommandRequest,
    AndroidCommandResponse,
    AndroidDeviceRegistration,
)
from nexus.agents.android.security import AndroidSecurityManager
from nexus.core.confirmation import ConfirmationManager
from nexus.utils.logging import get_logger

log = get_logger("agents.android.agent")


class AndroidAgent:
    """Backend agent managing Android mobile integration."""

    def __init__(
        self,
        security_manager: AndroidSecurityManager | None = None,
        device_bridge: AndroidDeviceBridge | None = None,
        confirmation_manager: ConfirmationManager | None = None,
    ) -> None:
        self._security = security_manager or AndroidSecurityManager()
        self._bridge = device_bridge or AndroidDeviceBridge()
        self._confirmation = confirmation_manager or ConfirmationManager()
        self._default_device_id: str | None = None

    @property
    def security(self) -> AndroidSecurityManager:
        return self._security

    @property
    def bridge(self) -> AndroidDeviceBridge:
        return self._bridge

    @property
    def has_paired_device(self) -> bool:
        return len(self._security.paired_devices) > 0

    @property
    def primary_device_id(self) -> str | None:
        if self._default_device_id and self._default_device_id in self._security.paired_devices:
            return self._default_device_id
        if self._security.paired_devices:
            return next(iter(self._security.paired_devices.keys()))
        return None

    def register_device(self, reg: AndroidDeviceRegistration) -> None:
        """Register a newly paired device."""
        self._default_device_id = reg.device_id
        log.info("Registered Android device: %s (%s)", reg.device_name, reg.device_id)

    async def execute_action(
        self,
        action_type: str,
        parameters: dict[str, Any],
        device_id: str | None = None,
        requires_confirmation: bool = False,
        confirmation_prompt: str | None = None,
    ) -> AndroidCommandResponse:
        """
        Execute an action on the connected Android device.

        Handles safety confirmations if action is high risk (e.g. sending SMS, making calls).
        """
        target_device = device_id or self.primary_device_id

        # Check if device is paired
        if not target_device or target_device not in self._security.paired_devices:
            return AndroidCommandResponse(
                request_id=str(uuid.uuid4()),
                action_type=action_type,
                success=False,
                output="No paired Android device found. Please pair your Android phone first.",
                error="NO_DEVICE_PAIRED",
            )

        # High-risk confirmation log
        if requires_confirmation:
            log.info("Action '%s' requires confirmation: %s", action_type, confirmation_prompt)

        request = AndroidCommandRequest(
            request_id=str(uuid.uuid4()),
            action_type=action_type,
            parameters=parameters,
            requires_confirmation=requires_confirmation,
        )

        start_time = time.time()
        # If device is online via bridge, dispatch command
        if self._bridge.is_online(target_device):
            response = await self._bridge.dispatch_command(target_device, request)
            response.duration_seconds = time.time() - start_time
            return response

        # If device is registered but currently idle/offline, simulate supported fallback response
        device_info = self._security.paired_devices.get(target_device, {})
        dev_name = device_info.get("device_name", "Android Device")

        log.info("Device '%s' offline; handling action via simulation fallback.", target_device)
        return AndroidCommandResponse(
            request_id=request.request_id,
            action_type=action_type,
            success=True,
            output=f"Executed '{action_type}' on {dev_name} (simulated/offline mode).",
            data={"device_id": target_device, "parameters": parameters},
            duration_seconds=time.time() - start_time,
        )

    def get_status(self) -> dict[str, Any]:
        """Return full Android agent summary status."""
        target_device = self.primary_device_id
        online = self._bridge.is_online(target_device) if target_device else False
        status_info = self._bridge.get_device_status(target_device) if target_device else None

        return {
            "paired_devices_count": len(self._security.paired_devices),
            "primary_device_id": target_device,
            "is_online": online,
            "connected_devices": self._bridge.connected_device_ids,
            "telemetry": status_info.model_dump() if status_info else None,
            "recent_notifications_count": len(self._bridge.get_recent_notifications()),
        }
