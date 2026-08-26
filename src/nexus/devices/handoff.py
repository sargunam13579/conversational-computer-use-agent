"""
NEXUS Task Handoff Engine.

Enables seamless migration of active multi-step workflows, open URLs,
target files, and context states between laptop and mobile nodes.
"""

from __future__ import annotations

import uuid
from typing import Any

from nexus.devices.types import TaskHandoffPayload
from nexus.utils.logging import get_logger

log = get_logger("devices.handoff")


class TaskHandoffEngine:
    """Manages active task state migration across devices."""

    def __init__(self) -> None:
        self._active_handoffs: dict[str, TaskHandoffPayload] = {}

    def create_handoff(
        self,
        source_device_id: str,
        target_device_id: str,
        task_description: str,
        context_state: dict[str, Any] | None = None,
        open_urls: list[str] | None = None,
        open_files: list[str] | None = None,
    ) -> TaskHandoffPayload:
        """Package current workflow state for handoff."""
        handoff_id = f"handoff_{uuid.uuid4().hex[:12]}"
        payload = TaskHandoffPayload(
            handoff_id=handoff_id,
            source_device_id=source_device_id,
            target_device_id=target_device_id,
            task_description=task_description,
            context_state=context_state or {},
            open_urls=open_urls or [],
            open_files=open_files or [],
        )
        self._active_handoffs[handoff_id] = payload
        log.info(
            "Created task handoff '%s' from '%s' to '%s': %s",
            handoff_id,
            source_device_id,
            target_device_id,
            task_description,
        )
        return payload

    def claim_handoff(self, handoff_id: str) -> TaskHandoffPayload | None:
        """Claim and resume handoff payload on destination device."""
        payload = self._active_handoffs.pop(handoff_id, None)
        if payload:
            log.info("Claimed task handoff '%s' for execution.", handoff_id)
        return payload

    def get_pending_handoffs(self, target_device_id: str) -> list[TaskHandoffPayload]:
        """List all pending handoffs intended for target device."""
        return [h for h in self._active_handoffs.values() if h.target_device_id == target_device_id]
