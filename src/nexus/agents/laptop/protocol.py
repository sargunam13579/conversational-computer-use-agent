"""
NEXUS Laptop Agent Protocol Models.

Defines the message format and data contracts for secure communication
between the Laptop Agent and the NEXUS AI backend.
"""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, Field


class DeviceRegistration(BaseModel):
    """Registration payload sent by the laptop agent to backend."""

    device_id: str
    device_type: str = "laptop"
    hostname: str
    os_info: str
    agent_version: str = "0.1.0"
    capabilities: list[str] = Field(default_factory=list)
    registered_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat()
    )


class DeviceStatus(BaseModel):
    """Detailed health and status report from laptop agent."""

    device_id: str
    is_online: bool = True
    hostname: str
    os_info: str
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    battery_info: str = "N/A"
    active_window: str | None = None
    available_tools: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())


class AgentHeartbeat(BaseModel):
    """Liveness heartbeat message."""

    device_id: str
    status: str = "healthy"
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())


class ToolExecutionRequest(BaseModel):
    """Request to execute a tool action on the laptop agent."""

    request_id: str
    tool_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    caller_id: str = "nexus_backend"
    skip_confirmation: bool = False
    timeout_seconds: int = 30


class ToolExecutionResponse(BaseModel):
    """Response returned after executing a tool on the laptop agent."""

    request_id: str
    tool_name: str
    success: bool
    output: str
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_seconds: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())
