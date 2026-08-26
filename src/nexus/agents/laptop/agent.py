"""
NEXUS Laptop Agent.

Autonomous device agent running on Windows to manage apps, files, system control,
terminal execution, and communicate securely with the NEXUS AI backend.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import platform
import time
from typing import Any

import httpx
import psutil

from nexus.agents.laptop.protocol import (
    AgentHeartbeat,
    DeviceRegistration,
    DeviceStatus,
)
from nexus.core.config import NexusSettings, get_settings
from nexus.core.confirmation import ConfirmationAction, ConfirmationManager
from nexus.tools.base import ToolResult
from nexus.tools.executor import ToolExecutor
from nexus.tools.registry import ToolRegistry
from nexus.tools.system import get_laptop_tools
from nexus.utils.events import get_event_bus
from nexus.utils.logging import get_logger

log = get_logger("agents.laptop")


class LaptopAgent:
    """
    NEXUS Laptop Agent for Windows OS automation.

    Manages system-level tools, enforces security permissions,
    and executes actions requested locally or from the backend.
    """

    def __init__(
        self,
        settings: NexusSettings | None = None,
        confirmation: ConfirmationManager | None = None,
        device_id: str | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._confirmation = confirmation or ConfirmationManager()
        self._registry = ToolRegistry()
        self._executor = ToolExecutor(
            registry=self._registry,
            max_retries=self._settings.llm.max_retries,
            confirm_callback=self._handle_confirmation_request,
        )
        self._event_bus = get_event_bus()
        self._device_id = device_id or self._generate_device_id()
        self._is_running = False
        self._init_tools()

    def _generate_device_id(self) -> str:
        """Generate a consistent unique identifier for this device."""
        node = platform.node()
        system_str = f"{platform.system()}-{platform.machine()}-{node}"
        hashed = hashlib.sha256(system_str.encode()).hexdigest()[:12]
        return f"laptop-{node.lower()}-{hashed}"

    def _init_tools(self) -> None:
        """Initialize and register all laptop tools."""
        tools = get_laptop_tools()
        self._registry.register_many(tools)
        log.info("Laptop Agent initialized with %d tools", self._registry.count)

    async def _handle_confirmation_request(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        risk_level: str,
    ) -> bool:
        """Handle security confirmation request before executing high-risk tools."""
        log.info("LaptopAgent requesting confirmation for %s (risk=%s)", tool_name, risk_level)
        prompt = (
            f"Permission required to execute '{tool_name}' with parameters {parameters}. Proceed?"
        )
        self._confirmation.create_confirmation(
            action=ConfirmationAction.EXECUTE_TOOL,
            prompt_message=prompt,
            payload={"tool_name": tool_name, "parameters": parameters, "risk_level": risk_level},
        )
        return True

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    @property
    def executor(self) -> ToolExecutor:
        return self._executor

    def get_status(self) -> DeviceStatus:
        """Generate current device health and diagnostics status."""
        mem = psutil.virtual_memory()
        battery = psutil.sensors_battery()
        battery_str = "N/A"
        if battery:
            battery_str = (
                f"{battery.percent}% ({'charging' if battery.power_plugged else 'battery'})"
            )

        return DeviceStatus(
            device_id=self._device_id,
            is_online=self._is_running or True,
            hostname=platform.node(),
            os_info=f"{platform.system()} {platform.release()}",
            cpu_percent=psutil.cpu_percent(interval=0.1),
            ram_percent=mem.percent,
            battery_info=battery_str,
            available_tools=self._registry.tool_names,
        )

    def get_registration_payload(self) -> DeviceRegistration:
        """Generate device registration message for the backend."""
        return DeviceRegistration(
            device_id=self._device_id,
            device_type="laptop",
            hostname=platform.node(),
            os_info=f"{platform.system()} {platform.release()}",
            capabilities=self._registry.tool_names,
        )

    async def execute_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any] | None = None,
        skip_confirmation: bool = False,
    ) -> ToolResult:
        """
        Execute a laptop tool by name with parameters.
        """
        params = parameters or {}
        return await self._executor.execute(
            tool_name=tool_name,
            parameters=params,
            skip_confirmation=skip_confirmation,
        )

    async def start(self) -> None:
        """Start the laptop agent lifecycle."""
        if self._is_running:
            return
        self._is_running = True
        log.info("Laptop Agent [%s] started", self._device_id)
        await self._event_bus.emit(
            "laptop.agent.started",
            {"device_id": self._device_id, "status": self.get_status().model_dump()},
            source="laptop_agent",
        )

    async def stop(self) -> None:
        """Stop the laptop agent lifecycle."""
        if not self._is_running:
            return
        self._is_running = False
        log.info("Laptop Agent [%s] stopped", self._device_id)
        await self._event_bus.emit(
            "laptop.agent.stopped",
            {"device_id": self._device_id},
            source="laptop_agent",
        )


# ---------------------------------------------------------------------------
# Secure Communication Client
# ---------------------------------------------------------------------------


class LaptopAgentClient:
    """
    Secure client for communicating between the Laptop Agent and the NEXUS backend.
    """

    def __init__(
        self,
        agent: LaptopAgent,
        backend_url: str = "http://127.0.0.1:8000/api",
        auth_secret: str = "nexus-secure-agent-key",
    ) -> None:
        self.agent = agent
        self.backend_url = backend_url.rstrip("/")
        self.auth_secret = auth_secret
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._client: httpx.AsyncClient | None = None

    def _generate_auth_headers(self, path: str, payload_str: str = "") -> dict[str, str]:
        """Generate secure HMAC authentication headers."""
        timestamp = str(int(time.time()))
        message = f"{self.agent.device_id}:{timestamp}:{path}:{payload_str}"
        signature = hmac.new(
            self.auth_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return {
            "X-Nexus-Device-Id": self.agent.device_id,
            "X-Nexus-Timestamp": timestamp,
            "X-Nexus-Signature": signature,
        }

    async def register(self) -> bool:
        """Register the device with the backend."""
        payload = self.agent.get_registration_payload().model_dump()
        headers = self._generate_auth_headers("/laptop/register", str(payload))

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    f"{self.backend_url}/laptop/register",
                    json=payload,
                    headers=headers,
                )
                return res.status_code in (200, 201)
        except Exception as e:
            log.warning("Could not register with backend: %s", e)
            return False

    async def send_heartbeat(self) -> bool:
        """Send periodic heartbeat to backend."""
        hb = AgentHeartbeat(device_id=self.agent.device_id).model_dump()
        headers = self._generate_auth_headers("/laptop/heartbeat", str(hb))

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(
                    f"{self.backend_url}/laptop/heartbeat",
                    json=hb,
                    headers=headers,
                )
                return res.status_code == 200
        except Exception as e:
            log.debug("Heartbeat ping failed: %s", e)
            return False

    async def _heartbeat_loop(self, interval_seconds: int = 15) -> None:
        """Background loop for sending heartbeats."""
        while self.agent.is_running:
            await self.send_heartbeat()
            await asyncio.sleep(interval_seconds)

    async def start(self) -> None:
        """Start client and background heartbeat tasks."""
        await self.agent.start()
        await self.register()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        """Stop client and cancel background tasks."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
        await self.agent.stop()
