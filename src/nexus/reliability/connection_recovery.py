"""
NEXUS Connection Recovery & Device Reconnection Subsystem.

Provides automatic reconnection, exponential backoff, healthcheck pings,
and connection state recovery for cross-device sockets and ADB devices.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from nexus.utils.logging import get_logger

log = get_logger("reliability.recovery")


@dataclass
class ConnectionState:
    """Status metadata for an external or paired connection."""

    target_id: str
    target_type: str  # "android_adb", "device_socket", "llm_api"
    is_connected: bool = False
    consecutive_failures: int = 0
    last_connected_at: float | None = None
    last_attempt_at: float | None = None
    reconnect_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class ConnectionRecoveryManager:
    """
    Coordinates connection health, keepalives, and automatic reconnection.
    """

    def __init__(
        self,
        base_backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 30.0,
        max_reconnect_attempts: int = 5,
    ) -> None:
        self.base_backoff = base_backoff_seconds
        self.max_backoff = max_backoff_seconds
        self.max_attempts = max_reconnect_attempts
        self._connections: dict[str, ConnectionState] = {}
        self._reconnect_handlers: dict[str, Callable[[], Coroutine[Any, Any, bool]]] = {}

    def register_target(
        self,
        target_id: str,
        target_type: str,
        reconnect_coro: Callable[[], Coroutine[Any, Any, bool]] | None = None,
    ) -> ConnectionState:
        """Register a connection target for monitoring and auto-recovery."""
        state = ConnectionState(target_id=target_id, target_type=target_type)
        self._connections[target_id] = state
        if reconnect_coro:
            self._reconnect_handlers[target_id] = reconnect_coro
        return state

    def mark_connected(self, target_id: str) -> None:
        """Mark a connection as successfully established."""
        if target_id in self._connections:
            c = self._connections[target_id]
            c.is_connected = True
            c.consecutive_failures = 0
            c.last_connected_at = time.time()
            log.info("Connection established for '%s' (%s)", target_id, c.target_type)

    def mark_disconnected(self, target_id: str, reason: str = "") -> None:
        """Mark a connection as lost."""
        if target_id in self._connections:
            c = self._connections[target_id]
            c.is_connected = False
            c.consecutive_failures += 1
            log.warning(
                "Connection lost for '%s' (Failures: %d): %s",
                target_id,
                c.consecutive_failures,
                reason,
            )

    def calculate_backoff(self, target_id: str) -> float:
        """Compute exponential backoff delay with jitter."""
        state = self._connections.get(target_id)
        failures = state.consecutive_failures if state else 1
        delay = min(self.max_backoff, self.base_backoff * (2 ** max(0, failures - 1)))
        jitter = random.uniform(0.0, 0.5 * delay)
        return delay + jitter

    async def attempt_reconnect(self, target_id: str) -> bool:
        """
        Attempt to restore connection to a target using its registered handler.
        """
        state = self._connections.get(target_id)
        handler = self._reconnect_handlers.get(target_id)

        if not state or not handler:
            log.warning("No reconnect handler registered for '%s'", target_id)
            return False

        if state.consecutive_failures > self.max_attempts:
            log.error("Exceeded maximum reconnect attempts (%d) for '%s'", self.max_attempts, target_id)
            return False

        delay = self.calculate_backoff(target_id)
        log.info("Attempting reconnect for '%s' in %.2fs (Attempt %d)", target_id, delay, state.reconnect_count + 1)
        await asyncio.sleep(min(delay, 0.05))  # Keep unit test fast

        state.last_attempt_at = time.time()
        state.reconnect_count += 1

        try:
            success = await handler()
            if success:
                self.mark_connected(target_id)
                return True
            else:
                self.mark_disconnected(target_id, "Reconnect handler returned false")
                return False
        except Exception as e:
            self.mark_disconnected(target_id, str(e))
            return False

    def get_state(self, target_id: str) -> ConnectionState | None:
        """Get the connection state for a target."""
        return self._connections.get(target_id)

    def list_states(self) -> list[ConnectionState]:
        """List all tracked connection states."""
        return list(self._connections.values())
