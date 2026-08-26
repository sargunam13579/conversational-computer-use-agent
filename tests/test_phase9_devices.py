"""
Comprehensive Test Suite for Phase 9 — NEXUS Unified Device System & Cross-Device Control.

Tests:
1. DeviceNode models and DeviceStatusEnum (ONLINE, OFFLINE, CONNECTING, BUSY)
2. DeviceDiscoveryService
3. SecureFileTransferBridge (SHA-256 integrity verification, transfer manifest)
4. TaskHandoffEngine (workflow migration, context preservation)
5. UnifiedDeviceManager (registry, NL target resolution, access revocation)
6. Cross-Device LLM Tools Suite (5 tools)
7. FastAPI Device Routes (/api/devices/*)
8. NexusBrain integration
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from nexus.api.app import create_app
from nexus.core.brain import NexusBrain
from nexus.devices.discovery import DeviceDiscoveryService
from nexus.devices.handoff import TaskHandoffEngine
from nexus.devices.manager import UnifiedDeviceManager
from nexus.devices.transfer import SecureFileTransferBridge
from nexus.devices.types import DeviceNode, DeviceStatusEnum, DeviceType
from nexus.tools.devices.device_tools import (
    ExecuteCrossDeviceCommandTool,
    HandoffTaskTool,
    ListDevicesTool,
    ManageDeviceAccessTool,
    TransferFileCrossDeviceTool,
    get_device_tools,
)

# ===========================================================================
# 1. DATA MODELS & ENUMS
# ===========================================================================


class TestDeviceTypes:
    """Tests for device models and presence states."""

    def test_device_presence_states(self):
        assert DeviceStatusEnum.ONLINE == "ONLINE"
        assert DeviceStatusEnum.OFFLINE == "OFFLINE"
        assert DeviceStatusEnum.CONNECTING == "CONNECTING"
        assert DeviceStatusEnum.BUSY == "BUSY"

    def test_device_node_serialization(self):
        node = DeviceNode(
            device_id="phone_pixel_8",
            name="Pixel 8 Pro",
            alias="my phone",
            device_type=DeviceType.PHONE,
            status=DeviceStatusEnum.ONLINE,
            capabilities=["apps", "camera", "media"],
            os_info="Android 14",
        )
        d = node.model_dump()
        assert d["device_id"] == "phone_pixel_8"
        assert d["status"] == "ONLINE"
        assert d["device_type"] == "phone"


# ===========================================================================
# 2. DISCOVERY SERVICE TESTS
# ===========================================================================


class TestDeviceDiscoveryService:
    """Tests for local beacon discovery."""

    @pytest.mark.asyncio
    async def test_discovery_lifecycle(self):
        discovery = DeviceDiscoveryService(port=54321)
        await discovery.start()
        assert discovery.is_running is True

        discovery.register_manual_node(
            device_id="dev_tab",
            name="Galaxy Tab",
            device_type=DeviceType.TABLET,
        )
        discovered = await discovery.discover_nearby()
        assert len(discovered) == 1
        assert discovered[0].device_id == "dev_tab"

        await discovery.stop()
        assert discovery.is_running is False


# ===========================================================================
# 3. SECURE FILE TRANSFER TESTS
# ===========================================================================


class TestSecureFileTransferBridge:
    """Tests for checksum-verified cross-device file transfer."""

    @pytest.mark.asyncio
    async def test_file_transfer_integrity(self, tmp_path: Path):
        # Create test source file
        src_file = tmp_path / "report.pdf"
        file_content = b"%PDF-1.4 sample content for cross-device transfer testing"
        src_file.write_bytes(file_content)

        dest_dir = tmp_path / "received"
        bridge = SecureFileTransferBridge(storage_dir=dest_dir)

        # 1. Prepare
        manifest = await bridge.prepare_transfer(
            source_device_id="host_laptop",
            target_device_id="phone_pixel",
            file_path=src_file,
        )
        assert manifest is not None
        assert manifest.file_name == "report.pdf"
        assert len(manifest.sha256_checksum) == 64

        # 2. Complete transfer with valid bytes
        success = await bridge.complete_transfer(manifest.transfer_id, file_content)
        assert success is True
        assert (dest_dir / "report.pdf").exists()

        # 3. Tampered bytes fail verification
        tampered_success = await bridge.complete_transfer(manifest.transfer_id, b"tampered data")
        assert tampered_success is False


# ===========================================================================
# 4. TASK HANDOFF ENGINE TESTS
# ===========================================================================


class TestTaskHandoffEngine:
    """Tests for workflow migration between devices."""

    def test_handoff_lifecycle(self):
        handoff = TaskHandoffEngine()

        # 1. Create handoff
        payload = handoff.create_handoff(
            source_device_id="host_laptop",
            target_device_id="phone_pixel",
            task_description="Review Java pull request",
            open_urls=["https://github.com/org/repo/pull/12"],
            open_files=["src/Main.java"],
        )
        assert payload.handoff_id.startswith("handoff_")

        # 2. Check pending
        pending = handoff.get_pending_handoffs("phone_pixel")
        assert len(pending) == 1

        # 3. Claim handoff
        claimed = handoff.claim_handoff(payload.handoff_id)
        assert claimed is not None
        assert claimed.task_description == "Review Java pull request"

        # Now pending is empty
        assert len(handoff.get_pending_handoffs("phone_pixel")) == 0


# ===========================================================================
# 5. UNIFIED DEVICE MANAGER TESTS
# ===========================================================================


class TestUnifiedDeviceManager:
    """Tests for central device registry, natural language resolution, and revocation."""

    @pytest.mark.asyncio
    async def test_device_registry_and_resolution(self):
        manager = UnifiedDeviceManager()

        # Host laptop is pre-registered
        assert manager.get_device("host_laptop") is not None

        # Register phone
        phone_node = DeviceNode(
            device_id="phone_pixel",
            name="Pixel 8",
            alias="my phone",
            device_type=DeviceType.PHONE,
            status=DeviceStatusEnum.ONLINE,
            capabilities=["camera", "notifications", "media"],
        )
        await manager.register_device(phone_node)

        # Status transition (ONLINE -> BUSY -> ONLINE)
        assert await manager.update_status("phone_pixel", DeviceStatusEnum.BUSY) is True
        phone_dev = manager.get_device("phone_pixel")
        assert phone_dev is not None
        assert phone_dev.status == DeviceStatusEnum.BUSY

        await manager.update_status("phone_pixel", DeviceStatusEnum.ONLINE)

        # Natural language target resolution
        laptop_target = manager.resolve_target_device("open on my laptop")
        assert laptop_target is not None
        assert laptop_target.device_id == "host_laptop"

        phone_target1 = manager.resolve_target_device("send to my phone")
        assert phone_target1 is not None
        assert phone_target1.device_id == "phone_pixel"

        phone_target2 = manager.resolve_target_device("Pixel 8")
        assert phone_target2 is not None
        assert phone_target2.device_id == "phone_pixel"

        # Revocation
        assert await manager.revoke_device_access("phone_pixel") is True
        assert manager.get_device("phone_pixel") is None

        # Cannot revoke primary host laptop
        assert await manager.revoke_device_access("host_laptop") is False

    @pytest.mark.asyncio
    async def test_cross_device_command_dispatch(self):
        manager = UnifiedDeviceManager()

        phone_node = DeviceNode(
            device_id="phone_pixel",
            name="Pixel 8",
            device_type=DeviceType.PHONE,
            status=DeviceStatusEnum.ONLINE,
        )
        await manager.register_device(phone_node)

        # Execute command targeted at phone
        res = await manager.execute_cross_device_command(
            target_text_or_id="phone",
            command_type="volume_control",
            parameters={"action": "set", "level": 60},
        )
        assert res["success"] is True
        assert res["device_id"] == "phone_pixel"


# ===========================================================================
# 6. CROSS-DEVICE TOOLS SUITE TESTS
# ===========================================================================


class TestCrossDeviceToolsSuite:
    """Tests for 5 cross-device tools."""

    @pytest.mark.asyncio
    async def test_tools_suite(self, tmp_path: Path):
        manager = UnifiedDeviceManager()
        phone_node = DeviceNode(
            device_id="dev_phone",
            name="Pixel 8",
            alias="phone",
            device_type=DeviceType.PHONE,
            status=DeviceStatusEnum.ONLINE,
        )
        await manager.register_device(phone_node)

        # 1. List devices
        list_tool = ListDevicesTool(manager=manager)
        res_list = await list_tool.execute()
        assert res_list.success is True
        assert res_list.data["count"] >= 2

        # 2. Cross-device command
        cmd_tool = ExecuteCrossDeviceCommandTool(manager=manager)
        res_cmd = await cmd_tool.execute(target_device="phone", command_type="media_control")
        assert res_cmd.success is True

        # 3. Transfer file
        test_file = tmp_path / "notes.txt"
        test_file.write_text("Hello cross-device")
        xfer_tool = TransferFileCrossDeviceTool(manager=manager)
        res_xfer = await xfer_tool.execute(file_path=str(test_file), target_device="phone")
        assert res_xfer.success is True

        # 4. Handoff task
        handoff_tool = HandoffTaskTool(manager=manager)
        res_handoff = await handoff_tool.execute(
            target_device="phone",
            task_description="Continue coding",
        )
        assert res_handoff.success is True

        # 5. Manage access (ping & status)
        access_tool = ManageDeviceAccessTool(manager=manager)
        res_ping = await access_tool.execute(action="ping", device_id="phone")
        assert res_ping.success is True

        # 6. Factory
        assert len(get_device_tools()) == 5


# ===========================================================================
# 7. FASTAPI DEVICE ROUTES TESTS
# ===========================================================================


class TestFastAPIDeviceRoutes:
    """Tests for /api/devices/* endpoints."""

    @pytest.mark.asyncio
    async def test_rest_endpoints(self):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. List devices
            res_list = await ac.get("/api/devices/")
            assert res_list.status_code == 200
            assert res_list.json()["count"] >= 1

            # 2. Register new device
            res_reg = await ac.post(
                "/api/devices/register",
                json={
                    "device_id": "test_tab_1",
                    "name": "Nexus Tablet",
                    "device_type": "tablet",
                    "capabilities": ["apps"],
                },
            )
            assert res_reg.status_code == 200
            assert res_reg.json()["device"]["device_id"] == "test_tab_1"

            # 3. Update status to BUSY
            res_st = await ac.post(
                "/api/devices/status",
                json={"device_id": "test_tab_1", "status": "BUSY"},
            )
            assert res_st.status_code == 200
            assert res_st.json()["status"] == "BUSY"

            # 4. Create handoff
            res_handoff = await ac.post(
                "/api/devices/handoff",
                json={
                    "target_device": "test_tab_1",
                    "task_description": "API Test Handoff",
                },
            )
            assert res_handoff.status_code == 200

            # 5. Revoke access
            res_rev = await ac.post("/api/devices/revoke/test_tab_1")
            assert res_rev.status_code == 200
            assert res_rev.json()["success"] is True


# ===========================================================================
# 8. NEXUS BRAIN INTEGRATION TESTS
# ===========================================================================


class TestNexusBrainDeviceIntegration:
    """Tests for Brain device_manager property."""

    def test_brain_device_manager(self):
        brain = NexusBrain()
        assert brain.device_manager is not None
        assert brain.device_manager.get_device("host_laptop") is not None
