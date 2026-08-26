"""
NEXUS API — Android Agent Hub Endpoints.

Provides REST and WebSocket endpoints for:
- Mobile device pairing initiation and verification
- Device telemetry status
- Remote command dispatching
- Notification stream synchronization
- Real-time WebSocket connection handling
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from nexus.agents.android.agent import AndroidAgent
from nexus.agents.android.protocol import (
    AndroidCommandResponse,
    AndroidDeviceRegistration,
    AndroidDeviceStatus,
    AndroidNotificationBatch,
    AndroidPairingRequest,
    AndroidPairingResponse,
    AndroidPermissionReport,
)

router = APIRouter(prefix="/android", tags=["Android Agent"])

_android_agent = AndroidAgent()


class PairingInitiateResponse(BaseModel):
    pairing_code: str
    expires_in_seconds: int
    qr_payload: str


class CommandDispatchRequest(BaseModel):
    action_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    device_id: str | None = None
    requires_confirmation: bool = False


@router.post("/pair/initiate", response_model=PairingInitiateResponse)
async def initiate_pairing() -> PairingInitiateResponse:
    """Generate pairing code and QR payload for Android mobile client."""
    code = _android_agent.security.generate_pairing_code(expiry_seconds=300)
    qr_data = f"nexus://pair?code={code}"
    return PairingInitiateResponse(
        pairing_code=code,
        expires_in_seconds=300,
        qr_payload=qr_data,
    )


@router.post("/pair/confirm", response_model=AndroidPairingResponse)
async def confirm_pairing(req: AndroidPairingRequest) -> AndroidPairingResponse:
    """Verify pairing code and register Android device."""
    token = _android_agent.security.verify_pairing_code(
        code=req.pairing_code,
        device_id=req.device_id,
        device_name=req.device_name,
    )

    if not token:
        raise HTTPException(status_code=400, detail="Invalid or expired pairing code.")

    # Register registration model
    reg = AndroidDeviceRegistration(
        device_id=req.device_id,
        device_name=req.device_name,
        android_version="14",
    )
    _android_agent.register_device(reg)

    return AndroidPairingResponse(
        success=True,
        device_id=req.device_id,
        auth_token=token,
    )


@router.get("/status")
async def get_status() -> dict[str, Any]:
    """Get connected mobile device status and telemetry."""
    return _android_agent.get_status()


@router.post("/command", response_model=AndroidCommandResponse)
async def dispatch_command(req: CommandDispatchRequest) -> AndroidCommandResponse:
    """Dispatch action command to Android device."""
    res = await _android_agent.execute_action(
        action_type=req.action_type,
        parameters=req.parameters,
        device_id=req.device_id,
        requires_confirmation=req.requires_confirmation,
    )
    return res


@router.get("/notifications")
async def get_notifications(limit: int = 20) -> dict[str, Any]:
    """Get recent notifications captured from mobile device."""
    notifs = _android_agent.bridge.get_recent_notifications(limit=limit)
    return {
        "count": len(notifs),
        "notifications": [n.model_dump() for n in notifs],
    }


@router.post("/notifications")
async def receive_notifications(batch: AndroidNotificationBatch) -> dict[str, Any]:
    """Receive notification stream batch from Android client."""
    await _android_agent.bridge.add_notifications(batch.notifications)
    return {"success": True, "received_count": len(batch.notifications)}


@router.post("/permissions")
async def report_permissions(report: AndroidPermissionReport) -> dict[str, Any]:
    """Receive runtime permission report from Android device."""
    # Update status telemetry
    target_status = _android_agent.bridge.get_device_status(report.device_id)
    if target_status:
        target_status.permissions = report
    return {"success": True, "device_id": report.device_id}


@router.websocket("/ws/{device_id}")
async def android_websocket(websocket: WebSocket, device_id: str) -> None:
    """Real-time bidirectional WebSocket connection for Android client."""
    await websocket.accept()
    await _android_agent.bridge.register_connection(device_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "heartbeat":
                hb = AndroidDeviceStatus.model_validate(data.get("status", {}))
                await _android_agent.bridge.update_device_status(hb)
                await websocket.send_json(
                    {"type": "heartbeat_ack", "timestamp": data.get("timestamp")}
                )

            elif msg_type == "command_response":
                resp = AndroidCommandResponse.model_validate(data.get("response", {}))
                _android_agent.bridge.handle_command_response(resp)

            elif msg_type == "notifications":
                batch = AndroidNotificationBatch.model_validate(data.get("batch", {}))
                await _android_agent.bridge.add_notifications(batch.notifications)

    except WebSocketDisconnect:
        await _android_agent.bridge.unregister_connection(device_id)
    except Exception:
        await _android_agent.bridge.unregister_connection(device_id)
