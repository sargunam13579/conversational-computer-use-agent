"""
NEXUS Android Agent Protocol Models.

Defines data contracts and message schemas for secure communication
between the Android mobile client and the NEXUS backend.
"""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, Field


class AndroidDeviceRegistration(BaseModel):
    """Registration payload sent by Android client upon first pairing."""

    device_id: str
    device_name: str  # e.g. "Pixel 8 Pro", "Samsung Galaxy S24"
    android_version: str  # e.g. "14", "15"
    sdk_int: int = 34
    app_version: str = "1.0.0"
    manufacturer: str = "Google"
    model: str = "Pixel"
    capabilities: list[str] = Field(default_factory=list)
    registered_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat()
    )


class AndroidPermissionReport(BaseModel):
    """Current runtime permission states on the Android device."""

    device_id: str
    accessibility_enabled: bool = False
    notification_listener_enabled: bool = False
    microphone_granted: bool = False
    camera_granted: bool = False
    storage_granted: bool = False
    sms_granted: bool = False
    phone_granted: bool = False
    notifications_post_granted: bool = False
    battery_optimization_ignored: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())


class AndroidDeviceStatus(BaseModel):
    """Real-time health and status telemetry from the Android device."""

    device_id: str
    device_name: str
    is_online: bool = True
    battery_percent: int = 100
    is_charging: bool = False
    current_volume: int = 50
    current_media_state: str = "paused"  # playing, paused, stopped
    active_foreground_app: str | None = None
    active_wifi_ssid: str | None = None
    permissions: AndroidPermissionReport | None = None
    available_tools: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())


class AndroidHeartbeat(BaseModel):
    """Periodic keep-alive heartbeat message."""

    device_id: str
    battery_percent: int = 100
    is_charging: bool = False
    status: str = "healthy"
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())


class AndroidPairingRequest(BaseModel):
    """Device pairing initiation request."""

    device_id: str
    device_name: str
    pairing_code: str
    public_key: str | None = None


class AndroidPairingResponse(BaseModel):
    """Response returned upon successful pairing verification."""

    success: bool
    device_id: str
    auth_token: str
    backend_version: str = "1.0.0"
    message: str = "Pairing successful"


class AndroidCommandRequest(BaseModel):
    """Command dispatch payload sent from backend to Android client."""

    request_id: str
    action_type: str  # launch_app, ui_click, media_control, volume, alarm, etc.
    parameters: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False
    timeout_seconds: int = 30
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())


class AndroidCommandResponse(BaseModel):
    """Result returned by Android client after executing a command."""

    request_id: str
    action_type: str
    success: bool
    output: str
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_seconds: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())


class AndroidNotificationItem(BaseModel):
    """A captured mobile notification."""

    id: str
    package_name: str
    app_name: str
    title: str
    text: str
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())
    is_ongoing: bool = False
    category: str | None = None


class AndroidNotificationBatch(BaseModel):
    """Batch of notifications pushed from device to backend."""

    device_id: str
    notifications: list[AndroidNotificationItem] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())
