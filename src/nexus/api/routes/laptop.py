"""
NEXUS API — Laptop Agent Endpoints.

Provides REST endpoints for device status, tool listings, remote tool execution,
and agent heartbeat synchronization.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from nexus.agents.laptop.protocol import (
    AgentHeartbeat,
    DeviceRegistration,
    DeviceStatus,
    ToolExecutionRequest,
    ToolExecutionResponse,
)
from nexus.tools.system import get_laptop_tools
from nexus.utils.logging import get_logger

log = get_logger("api.routes.laptop")

router = APIRouter(prefix="/laptop", tags=["Laptop Agent"])

# In-memory registry of connected devices
_REGISTERED_DEVICES: dict[str, DeviceRegistration] = {}
_DEVICE_HEARTBEATS: dict[str, float] = {}


class ToolListResponse(BaseModel):
    """List of tools supported by laptop agent."""

    count: int
    tools: list[dict[str, Any]]


@router.get("/status", response_model=DeviceStatus)
async def get_laptop_status(request: Request) -> DeviceStatus:
    """Get the current laptop agent diagnostics and hardware status."""
    brain = getattr(request.app.state, "brain", None)
    if brain and hasattr(brain, "laptop_agent") and brain.laptop_agent:
        return brain.laptop_agent.get_status()

    # Fallback to local agent instance
    from nexus.agents.laptop.agent import LaptopAgent

    agent = LaptopAgent()
    return agent.get_status()


@router.get("/tools", response_model=ToolListResponse)
async def list_laptop_tools() -> ToolListResponse:
    """List all registered tools available on the laptop agent."""
    tools = get_laptop_tools()
    schemas = [t.to_schema() for t in tools]
    return ToolListResponse(count=len(schemas), tools=schemas)


@router.post("/register")
async def register_device(registration: DeviceRegistration) -> dict[str, Any]:
    """Register a laptop agent device with the backend."""
    _REGISTERED_DEVICES[registration.device_id] = registration
    _DEVICE_HEARTBEATS[registration.device_id] = time.time()
    log.info("Registered laptop agent: %s (%s)", registration.device_id, registration.hostname)
    return {
        "status": "registered",
        "device_id": registration.device_id,
        "message": f"Successfully registered laptop '{registration.hostname}'.",
    }


@router.post("/heartbeat")
async def receive_heartbeat(heartbeat: AgentHeartbeat) -> dict[str, Any]:
    """Receive heartbeat pulse from laptop agent."""
    _DEVICE_HEARTBEATS[heartbeat.device_id] = time.time()
    return {"status": "ok", "timestamp": heartbeat.timestamp}


@router.post("/execute", response_model=ToolExecutionResponse)
async def execute_laptop_tool(
    exec_req: ToolExecutionRequest,
    request: Request,
    x_nexus_device_id: str | None = Header(default=None),
) -> ToolExecutionResponse:
    """
    Execute a tool on the laptop agent safely.
    """
    start_time = time.time()
    brain = getattr(request.app.state, "brain", None)

    if brain and hasattr(brain, "laptop_agent") and brain.laptop_agent:
        agent = brain.laptop_agent
    else:
        from nexus.agents.laptop.agent import LaptopAgent

        agent = LaptopAgent()

    log.info(
        "API execution request for tool '%s' (req_id=%s)",
        exec_req.tool_name,
        exec_req.request_id,
    )

    result = await agent.execute_tool(
        tool_name=exec_req.tool_name,
        parameters=exec_req.parameters,
        skip_confirmation=exec_req.skip_confirmation,
    )

    duration = time.time() - start_time
    return ToolExecutionResponse(
        request_id=exec_req.request_id,
        tool_name=exec_req.tool_name,
        success=result.success,
        output=result.output,
        data=result.data,
        error=result.error,
        duration_seconds=round(duration, 3),
    )
