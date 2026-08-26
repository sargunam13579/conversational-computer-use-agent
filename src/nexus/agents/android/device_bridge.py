"""
NEXUS Android Device Bridge.

Manages bidirectional WebSocket connections, notification stream buffering,
and asynchronous command dispatching to Android devices.
"""

from __future__ import annotations

import asyncio
from typing import Any

from nexus.agents.android.protocol import (
    AndroidCommandRequest,
    AndroidCommandResponse,
    AndroidDeviceStatus,
    AndroidNotificationItem,
)
from nexus.utils.logging import get_logger

log = get_logger("agents.android.device_bridge")


class AndroidDeviceBridge:
    """Handles real-time communication and push messaging with connected Android clients."""

    def __init__(self) -> None:
        self._active_connections: dict[str, Any] = {}  # device_id -> WebSocket/Handler
        self._pending_commands: dict[str, asyncio.Future[AndroidCommandResponse]] = {}
        self._latest_status: dict[str, AndroidDeviceStatus] = {}  # device_id -> status
        self._notification_buffer: list[AndroidNotificationItem] = []
        self._max_notifications = 100
        self._lock = asyncio.Lock()

    @property
    def active_connections_count(self) -> int:
        return len(self._active_connections)

    @property
    def connected_device_ids(self) -> list[str]:
        return list(self._active_connections.keys())

    async def register_connection(self, device_id: str, connection: Any) -> None:
        """Register active WebSocket connection for a device."""
        async with self._lock:
            self._active_connections[device_id] = connection
            log.info("Registered active Android connection: %s", device_id)

    async def unregister_connection(self, device_id: str) -> None:
        """Unregister closed WebSocket connection."""
        async with self._lock:
            if device_id in self._active_connections:
                del self._active_connections[device_id]
                log.info("Unregistered Android connection: %s", device_id)

    def is_online(self, device_id: str) -> bool:
        """Check if device has an active connection."""
        return device_id in self._active_connections

    async def update_device_status(self, status: AndroidDeviceStatus) -> None:
        """Update cached status telemetry from device."""
        async with self._lock:
            self._latest_status[status.device_id] = status

    def get_device_status(self, device_id: str) -> AndroidDeviceStatus | None:
        """Retrieve latest status telemetry for device."""
        return self._latest_status.get(device_id)

    async def add_notifications(self, items: list[AndroidNotificationItem]) -> None:
        """Buffer incoming mobile notifications."""
        async with self._lock:
            self._notification_buffer.extend(items)
            if len(self._notification_buffer) > self._max_notifications:
                self._notification_buffer = self._notification_buffer[-self._max_notifications :]

    def get_recent_notifications(self, limit: int = 20) -> list[AndroidNotificationItem]:
        """Get most recent buffered notifications."""
        return list(reversed(self._notification_buffer))[:limit]

    async def dispatch_command(
        self,
        device_id: str,
        command: AndroidCommandRequest,
    ) -> AndroidCommandResponse:
        """
        Send a command to the connected Android device and await response.
        """
        conn = self._active_connections.get(device_id)
        if not conn:
            return AndroidCommandResponse(
                request_id=command.request_id,
                action_type=command.action_type,
                success=False,
                output="Device is currently offline.",
                error="DEVICE_OFFLINE",
            )

        loop = asyncio.get_running_loop()
        future: asyncio.Future[AndroidCommandResponse] = loop.create_future()
        self._pending_commands[command.request_id] = future

        try:
            # Send message through connection (supports send_json on FastAPI WebSocket or mock)
            if hasattr(conn, "send_json"):
                await conn.send_json(command.model_dump())
            elif hasattr(conn, "send_text"):
                await conn.send_text(command.model_dump_json())

            # Await response with timeout
            response = await asyncio.wait_for(future, timeout=command.timeout_seconds)
            return response
        except TimeoutError:
            return AndroidCommandResponse(
                request_id=command.request_id,
                action_type=command.action_type,
                success=False,
                output=f"Command timed out after {command.timeout_seconds}s",
                error="TIMEOUT",
            )
        finally:
            self._pending_commands.pop(command.request_id, None)

    def handle_command_response(self, response: AndroidCommandResponse) -> None:
        """Resolve pending future with command response from device."""
        future = self._pending_commands.get(response.request_id)
        if future and not future.done():
            future.set_result(response)
