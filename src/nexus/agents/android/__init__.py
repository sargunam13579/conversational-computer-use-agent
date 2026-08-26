"""
NEXUS Android Agent Package.

Provides mobile device pairing, WebSocket bridging, HMAC security,
and mobile capabilities execution.
"""

from nexus.agents.android.agent import AndroidAgent
from nexus.agents.android.device_bridge import AndroidDeviceBridge
from nexus.agents.android.protocol import (
    AndroidCommandRequest,
    AndroidCommandResponse,
    AndroidDeviceRegistration,
    AndroidDeviceStatus,
    AndroidHeartbeat,
    AndroidNotificationBatch,
    AndroidNotificationItem,
    AndroidPairingRequest,
    AndroidPairingResponse,
    AndroidPermissionReport,
)
from nexus.agents.android.security import AndroidSecurityManager

__all__ = [
    "AndroidAgent",
    "AndroidSecurityManager",
    "AndroidDeviceBridge",
    "AndroidDeviceRegistration",
    "AndroidDeviceStatus",
    "AndroidPermissionReport",
    "AndroidHeartbeat",
    "AndroidPairingRequest",
    "AndroidPairingResponse",
    "AndroidCommandRequest",
    "AndroidCommandResponse",
    "AndroidNotificationItem",
    "AndroidNotificationBatch",
]
