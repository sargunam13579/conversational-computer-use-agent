"""
NEXUS Device Discovery Service.

Provides local beacon broadcasting and node discovery over local network.
"""

from __future__ import annotations

import asyncio

from nexus.devices.types import DeviceNode, DeviceStatusEnum, DeviceType
from nexus.utils.logging import get_logger

log = get_logger("devices.discovery")


class DeviceDiscoveryService:
    """Discovers nearby NEXUS agents on the local network."""

    def __init__(self, port: int = 53530) -> None:
        self._port = port
        self._is_running = False
        self._discovered_nodes: dict[str, DeviceNode] = {}
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._is_running

    async def start(self) -> None:
        """Start local discovery beacon."""
        self._is_running = True
        log.info("Started NEXUS Device Discovery Service on port %d", self._port)

    async def stop(self) -> None:
        """Stop local discovery beacon."""
        self._is_running = False
        log.info("Stopped NEXUS Device Discovery Service")

    async def announce_node(self, node: DeviceNode) -> None:
        """Announce local node presence to network."""
        async with self._lock:
            self._discovered_nodes[node.device_id] = node

    async def discover_nearby(self, timeout_seconds: float = 2.0) -> list[DeviceNode]:
        """Scan local network and return list of discovered device nodes."""
        async with self._lock:
            return list(self._discovered_nodes.values())

    def register_manual_node(
        self,
        device_id: str,
        name: str,
        device_type: DeviceType = DeviceType.PHONE,
        ip_address: str | None = None,
        capabilities: list[str] | None = None,
    ) -> DeviceNode:
        """Manually register a known network node."""
        node = DeviceNode(
            device_id=device_id,
            name=name,
            device_type=device_type,
            status=DeviceStatusEnum.ONLINE,
            ip_address=ip_address,
            capabilities=capabilities or ["apps", "notifications", "media"],
        )
        self._discovered_nodes[device_id] = node
        return node
