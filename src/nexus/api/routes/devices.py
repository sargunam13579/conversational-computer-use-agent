"""
NEXUS API — Unified Device System Endpoints.

Provides REST endpoints for:
- Querying ecosystem devices and status (ONLINE, OFFLINE, CONNECTING, BUSY)
- Registering new device nodes
- Updating device status telemetry
- Revoking device access
- Cross-device command routing
- Secure file transfer preparation
- Task handoff creation and claiming
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from nexus.devices.manager import UnifiedDeviceManager
from nexus.devices.types import (
    DeviceNode,
    DeviceStatusEnum,
    DeviceType,
    FileTransferManifest,
    TaskHandoffPayload,
)

router = APIRouter(prefix="/devices", tags=["Unified Device Ecosystem"])

_device_manager = UnifiedDeviceManager()


class DeviceRegistrationRequest(BaseModel):
    device_id: str
    name: str
    alias: str | None = None
    device_type: str = "phone"
    capabilities: list[str] = Field(default_factory=list)
    os_info: str = "Android"
    ip_address: str | None = None


class DeviceStatusUpdateRequest(BaseModel):
    device_id: str
    status: str  # ONLINE, OFFLINE, CONNECTING, BUSY


class CrossDeviceCommandRequest(BaseModel):
    target_device: str
    command_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class FileTransferRequest(BaseModel):
    source_device: str = "host_laptop"
    target_device: str
    file_path: str
    destination_folder: str = "Documents"


class TaskHandoffRequest(BaseModel):
    source_device: str = "host_laptop"
    target_device: str
    task_description: str
    open_urls: list[str] = Field(default_factory=list)
    open_files: list[str] = Field(default_factory=list)
    context_state: dict[str, Any] = Field(default_factory=dict)


@router.get("/")
async def list_devices(status: str | None = None) -> dict[str, Any]:
    """List registered devices in the NEXUS ecosystem."""
    st_enum = None
    if status:
        try:
            st_enum = DeviceStatusEnum(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Must be ONLINE, OFFLINE, CONNECTING, or BUSY.",
            ) from None

    devices = _device_manager.list_devices(status=st_enum)
    return {
        "count": len(devices),
        "devices": [d.model_dump() for d in devices],
    }


@router.post("/register")
async def register_device(req: DeviceRegistrationRequest) -> dict[str, Any]:
    """Register or update a device node in the ecosystem."""
    try:
        dtype = DeviceType(req.device_type)
    except ValueError:
        dtype = DeviceType.OTHER

    node = DeviceNode(
        device_id=req.device_id,
        name=req.name,
        alias=req.alias,
        device_type=dtype,
        status=DeviceStatusEnum.ONLINE,
        capabilities=req.capabilities,
        os_info=req.os_info,
        ip_address=req.ip_address,
    )
    saved = await _device_manager.register_device(node)
    return {"success": True, "device": saved.model_dump()}


@router.post("/status")
async def update_device_status(req: DeviceStatusUpdateRequest) -> dict[str, Any]:
    """Update device presence status (ONLINE, OFFLINE, CONNECTING, BUSY)."""
    try:
        st_enum = DeviceStatusEnum(req.status)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{req.status}'. Must be ONLINE, OFFLINE, CONNECTING, or BUSY.",
        ) from None

    updated = await _device_manager.update_status(req.device_id, st_enum)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Device '{req.device_id}' not found.")

    return {"success": True, "device_id": req.device_id, "status": req.status}


@router.post("/revoke/{device_id}")
async def revoke_device_access(device_id: str) -> dict[str, Any]:
    """Revoke device ecosystem access immediately."""
    revoked = await _device_manager.revoke_device_access(device_id)
    if not revoked:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Could not revoke access for device '{device_id}'. "
                "(Primary devices cannot be revoked)."
            ),
        )
    return {"success": True, "revoked_device_id": device_id}


@router.post("/command")
async def execute_cross_device_command(req: CrossDeviceCommandRequest) -> dict[str, Any]:
    """Dispatch and execute a cross-device command."""
    res = await _device_manager.execute_cross_device_command(
        target_text_or_id=req.target_device,
        command_type=req.command_type,
        parameters=req.parameters,
    )
    if not res.get("success"):
        raise HTTPException(
            status_code=400,
            detail=res.get("error", "Cross-device command failed."),
        )
    return res


@router.post("/transfer", response_model=FileTransferManifest)
async def initiate_file_transfer(req: FileTransferRequest) -> FileTransferManifest:
    """Initiate a cross-device file transfer."""
    target_node = _device_manager.resolve_target_device(req.target_device)
    if not target_node:
        raise HTTPException(
            status_code=404,
            detail=f"Target device '{req.target_device}' not found.",
        )

    manifest = await _device_manager.transfer.prepare_transfer(
        source_device_id=req.source_device,
        target_device_id=target_node.device_id,
        file_path=req.file_path,
        destination_folder=req.destination_folder,
    )
    if not manifest:
        raise HTTPException(
            status_code=400,
            detail=f"Could not locate file '{req.file_path}' to transfer.",
        )

    return manifest


@router.post("/handoff", response_model=TaskHandoffPayload)
async def create_task_handoff(req: TaskHandoffRequest) -> TaskHandoffPayload:
    """Create task handoff payload for migrating workflow to another device."""
    target_node = _device_manager.resolve_target_device(req.target_device)
    if not target_node:
        raise HTTPException(
            status_code=404,
            detail=f"Target device '{req.target_device}' not found.",
        )

    payload = _device_manager.handoff.create_handoff(
        source_device_id=req.source_device,
        target_device_id=target_node.device_id,
        task_description=req.task_description,
        open_urls=req.open_urls,
        open_files=req.open_files,
        context_state=req.context_state,
    )
    return payload


@router.get("/handoff/{device_id}")
async def get_pending_handoffs(device_id: str) -> dict[str, Any]:
    """Retrieve pending task handoffs for target device."""
    handoffs = _device_manager.handoff.get_pending_handoffs(device_id)
    return {
        "device_id": device_id,
        "count": len(handoffs),
        "handoffs": [h.model_dump() for h in handoffs],
    }
