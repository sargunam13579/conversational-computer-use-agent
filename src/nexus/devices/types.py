"""
NEXUS Unified Device System — Data Models and Enums.

Defines the 4 presence states, device types, telemetry records,
task handoff payloads, and file transfer contracts.
"""

from __future__ import annotations

import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DeviceStatusEnum(StrEnum):
    """The 4 mandatory device presence states."""

    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    CONNECTING = "CONNECTING"
    BUSY = "BUSY"


class DeviceType(StrEnum):
    """Device hardware category."""

    LAPTOP = "laptop"
    PHONE = "phone"
    TABLET = "tablet"
    SERVER = "server"
    OTHER = "other"


class DeviceNode(BaseModel):
    """Representation of an interconnected device in the NEXUS ecosystem."""

    device_id: str
    name: str
    alias: str | None = None  # e.g. "my laptop", "work laptop", "pixel", "phone"
    device_type: DeviceType = DeviceType.OTHER
    status: DeviceStatusEnum = DeviceStatusEnum.OFFLINE
    capabilities: list[str] = Field(default_factory=list)
    os_info: str = "Unknown"
    ip_address: str | None = None
    is_primary: bool = False
    auth_token_hash: str | None = None
    last_seen: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskHandoffPayload(BaseModel):
    """Data payload for migrating active tasks, URLs, and context across devices."""

    handoff_id: str
    source_device_id: str
    target_device_id: str
    task_description: str
    context_state: dict[str, Any] = Field(default_factory=dict)
    open_urls: list[str] = Field(default_factory=list)
    open_files: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())


class FileTransferManifest(BaseModel):
    """Manifest for secure cross-device file transfers."""

    transfer_id: str
    source_device_id: str
    target_device_id: str
    file_name: str
    file_size_bytes: int
    sha256_checksum: str
    destination_folder: str = "Documents"
    status: str = "pending"  # pending, in_progress, completed, failed
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())
