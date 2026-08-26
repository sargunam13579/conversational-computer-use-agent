"""
NEXUS Device Pairing REST API Router.

Provides endpoints for initiating device handshakes, verifying PINs,
and managing paired authorized devices.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from nexus.security.pairing import DevicePairingManager

router = APIRouter(prefix="/pairing", tags=["pairing"])

_pairing_manager = DevicePairingManager()


class InitiatePairingRequest(BaseModel):
    device_name: str = Field(..., description="Human readable name of device")
    device_type: str = Field(default="phone", description="Type of device (phone, laptop, tablet)")


class VerifyPairingRequest(BaseModel):
    session_id: str = Field(..., description="Active pairing session ID")
    pin: str = Field(..., description="6-digit verification PIN")


@router.post("/initiate", summary="Initiate device pairing")
async def initiate_pairing(req: InitiatePairingRequest) -> dict[str, Any]:
    """Start a pairing session and receive a 6-digit verification PIN."""
    session = _pairing_manager.initiate_pairing(device_name=req.device_name, device_type=req.device_type)
    return {
        "session_id": session.session_id,
        "pin": session.pin,
        "device_name": session.device_name,
        "expires_in_seconds": int(session.expires_at - session.created_at),
    }


@router.post("/verify", summary="Verify pairing PIN")
async def verify_pairing(req: VerifyPairingRequest) -> dict[str, Any]:
    """Submit 6-digit PIN to finalize device pairing and obtain access token."""
    device = _pairing_manager.verify_pairing(session_id=req.session_id, pin=req.pin)
    if not device:
        raise HTTPException(status_code=400, detail="Invalid PIN or expired pairing session.")
    return {
        "success": True,
        "device_id": device.device_id,
        "device_name": device.device_name,
        "device_token": device.device_token,
    }


@router.get("/devices", summary="List paired devices")
async def list_paired_devices() -> dict[str, Any]:
    """List all authorized paired devices."""
    devices = _pairing_manager.list_paired_devices()
    return {
        "count": len(devices),
        "devices": [
            {
                "device_id": d.device_id,
                "device_name": d.device_name,
                "device_type": d.device_type,
                "paired_at": d.paired_at,
                "last_seen_at": d.last_seen_at,
                "is_active": d.is_active,
            }
            for d in devices
        ],
    }


@router.delete("/devices/{device_id}", summary="Revoke paired device")
async def revoke_device(device_id: str) -> dict[str, Any]:
    """Revoke authorization for a paired device."""
    revoked = _pairing_manager.revoke_device(device_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Device not found.")
    return {"success": True, "device_id": device_id, "message": "Device revoked successfully."}
