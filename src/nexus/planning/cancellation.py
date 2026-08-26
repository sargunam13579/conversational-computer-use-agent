"""
NEXUS Planning — Cancellation & Emergency Stop System.

Provides thread-safe and asyncio-aware cancellation tokens, soft graceful
cancellation, and immediate hard emergency stop capabilities.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from nexus.utils.events import get_event_bus
from nexus.utils.logging import get_logger

log = get_logger("planning.cancellation")


def _safe_emit(coro: Any) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        pass


class CancellationType(StrEnum):
    """Type of cancellation signal."""

    NONE = "none"
    GRACEFUL = "graceful"
    EMERGENCY = "emergency"


# Exact or uppercase patterns indicating emergency hard stop
_EMERGENCY_STOP_PATTERNS = [
    re.compile(r"^NEXUS\s+STOP!?$", re.ASCII),
    re.compile(r"^EMERGENCY\s+STOP!?$", re.IGNORECASE),
    re.compile(r"^KILL\s+(?:ALL|SWITCH|TASK|EXECUTION)!?$", re.IGNORECASE),
    re.compile(r"^STOP\s+EVERYTHING!?$", re.IGNORECASE),
    re.compile(r"^HALT\s+(?:ALL|IMMEDIATELY)!?$", re.IGNORECASE),
]

# Soft graceful cancellation patterns
_GRACEFUL_STOP_PATTERNS = [
    re.compile(r"^(?:nexus\s+)?stop(?:\s+please|\s+the\s+task|\s+now)?\.?$", re.IGNORECASE),
    re.compile(r"^(?:nexus\s+)?cancel(?:\s+the\s+task|\s+this|\s+action|\s+please)?\.?$", re.IGNORECASE),
    re.compile(r"^(?:nexus\s+)?abort(?:\s+mission|\s+task|\s+operation|\s+please)?\.?$", re.IGNORECASE),
    re.compile(r"^(?:please\s+)?stop(?:\s+what\s+you(?:'re|\s+are)\s+doing|\s+please)?\.?$", re.IGNORECASE),
    re.compile(r"^(?:pause|hold\s+on|wait\s+stop)\.?$", re.IGNORECASE),
]


@dataclass
class CancellationToken:
    """Token inspected by executing tasks/steps to respect cancellation requests."""

    is_cancelled: bool = False
    is_emergency: bool = False
    reason: str = ""
    cancelled_at: float | None = None
    _event: asyncio.Event = field(default_factory=asyncio.Event)

    def cancel(self, reason: str = "User requested cancellation") -> None:
        """Signal graceful cancellation."""
        self.is_cancelled = True
        self.reason = reason
        self._event.set()

    def emergency_stop(self, reason: str = "Emergency stop triggered") -> None:
        """Signal hard emergency stop."""
        self.is_cancelled = True
        self.is_emergency = True
        self.reason = reason
        self._event.set()

    def check(self) -> None:
        """Raise an exception if cancellation is requested."""
        if self.is_emergency:
            raise EmergencyStopError(f"Execution halted by EMERGENCY STOP: {self.reason}")
        if self.is_cancelled:
            raise TaskCancelledError(f"Execution cancelled: {self.reason}")


class TaskCancelledError(Exception):
    """Raised when a task or step is gracefully cancelled."""


class EmergencyStopError(Exception):
    """Raised when an immediate emergency kill switch is triggered."""


# Backward compatibility aliases
TaskCancelledException = TaskCancelledError
EmergencyStopException = EmergencyStopError


class CancellationManager:
    """
    Manages cancellation tokens, active task cancellations, and emergency stops.
    """

    def __init__(self) -> None:
        self._tokens: dict[str, CancellationToken] = {}
        self._active_async_tasks: dict[str, set[asyncio.Task[Any]]] = {}
        self._global_emergency: bool = False
        self._event_bus = get_event_bus()

    def create_token(self, plan_id: str) -> CancellationToken:
        """Create and track a cancellation token for a plan."""
        token = CancellationToken()
        self._tokens[plan_id] = token
        self._active_async_tasks[plan_id] = set()
        return token

    def get_token(self, plan_id: str) -> CancellationToken | None:
        """Retrieve token for a plan."""
        return self._tokens.get(plan_id)

    def register_async_task(self, plan_id: str, task: asyncio.Task[Any]) -> None:
        """Track a running asyncio task for forceful cancellation if needed."""
        if plan_id not in self._active_async_tasks:
            self._active_async_tasks[plan_id] = set()
        self._active_async_tasks[plan_id].add(task)
        task.add_done_callback(
            lambda t: self._active_async_tasks.get(plan_id, set()).discard(t)
        )

    def cancel_task(self, plan_id: str, reason: str = "User requested cancellation") -> bool:
        """
        Request graceful cancellation of a plan.
        Safe-to-stop actions halt cleanly.
        """
        token = self._tokens.get(plan_id)
        if not token:
            return False

        log.info("Graceful cancellation requested for plan %s: %s", plan_id, reason)
        token.cancel(reason)
        _safe_emit(
            self._event_bus.emit(
                "task.cancelled",
                {"plan_id": plan_id, "reason": reason, "type": "graceful"},
                source="cancellation_manager",
            )
        )
        return True

    def emergency_stop(
        self, plan_id: str | None = None, reason: str = "EMERGENCY STOP"
    ) -> dict[str, Any]:
        """
        Trigger an immediate hard emergency stop.

        Aborts immediately, cancels all running asyncio tasks,
        and halts execution across the specified plan or all active plans.
        """
        self._global_emergency = True
        cancelled_plans: list[str] = []
        cancelled_tasks_count = 0

        target_plan_ids = [plan_id] if plan_id and plan_id in self._tokens else list(self._tokens.keys())

        for pid in target_plan_ids:
            token = self._tokens.get(pid)
            if token:
                token.emergency_stop(reason)
                cancelled_plans.append(pid)

            # Cancel active asyncio tasks immediately
            tasks = self._active_async_tasks.get(pid, set())
            for t in list(tasks):
                if not t.done():
                    t.cancel()
                    cancelled_tasks_count += 1

        log.warning(
            "EMERGENCY STOP executed across %d plan(s) and %d task(s): %s",
            len(cancelled_plans),
            cancelled_tasks_count,
            reason,
        )

        _safe_emit(
            self._event_bus.emit(
                "task.emergency_stopped",
                {
                    "plans": cancelled_plans,
                    "tasks_cancelled": cancelled_tasks_count,
                    "reason": reason,
                },
                source="cancellation_manager",
            )
        )

        return {
            "emergency": True,
            "plans_stopped": cancelled_plans,
            "tasks_cancelled": cancelled_tasks_count,
            "reason": reason,
        }

    def detect_cancellation_intent(self, text: str) -> CancellationType:
        """
        Analyze user input to detect emergency stop vs graceful cancellation.

        Returns:
            CancellationType.EMERGENCY, CancellationType.GRACEFUL, or CancellationType.NONE
        """
        stripped = text.strip()

        # Check for emergency uppercase or specific emergency keywords
        for pat in _EMERGENCY_STOP_PATTERNS:
            if pat.search(stripped):
                return CancellationType.EMERGENCY

        # Check for graceful cancellation
        for pat in _GRACEFUL_STOP_PATTERNS:
            if pat.search(stripped):
                return CancellationType.GRACEFUL

        return CancellationType.NONE

    def cleanup(self, plan_id: str) -> None:
        """Clean up resources associated with a finished plan."""
        self._tokens.pop(plan_id, None)
        self._active_async_tasks.pop(plan_id, None)
