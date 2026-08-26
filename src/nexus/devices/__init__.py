"""
NEXUS Unified Device System Package.

Provides device registry, presence tracking (ONLINE, OFFLINE, CONNECTING, BUSY),
cross-device command execution, secure file transfer, and task handoff.
"""

from nexus.devices.discovery import DeviceDiscoveryService
from nexus.devices.handoff import TaskHandoffEngine
from nexus.devices.manager import UnifiedDeviceManager
from nexus.devices.transfer import SecureFileTransferBridge
from nexus.devices.types import (
    DeviceNode,
    DeviceStatusEnum,
    DeviceType,
    FileTransferManifest,
    TaskHandoffPayload,
)

__all__ = [
    "DeviceStatusEnum",
    "DeviceType",
    "DeviceNode",
    "TaskHandoffPayload",
    "FileTransferManifest",
    "DeviceDiscoveryService",
    "SecureFileTransferBridge",
    "TaskHandoffEngine",
    "UnifiedDeviceManager",
]
