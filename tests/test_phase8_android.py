"""
Comprehensive Test Suite for Phase 8 — NEXUS Android Mobile Agent.

Tests:
1. AndroidSecurityManager (pairing codes, HMAC signing, token authorization)
2. AndroidDeviceBridge (status telemetry, notification buffering, command dispatch)
3. AndroidAgent (registration, execution routing, offline fallbacks)
4. Android LLM Tools Suite (11 mobile tools)
5. FastAPI Android Routes (REST endpoints and WebSocket handling)
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from nexus.agents.android.agent import AndroidAgent
from nexus.agents.android.device_bridge import AndroidDeviceBridge
from nexus.agents.android.protocol import (
    AndroidCommandRequest,
    AndroidCommandResponse,
    AndroidDeviceRegistration,
    AndroidDeviceStatus,
    AndroidNotificationBatch,
    AndroidNotificationItem,
    AndroidPermissionReport,
)
from nexus.agents.android.security import AndroidSecurityManager
from nexus.api.app import create_app
from nexus.tools.android.mobile_tools import (
    AndroidCallSmsTool,
    AndroidCameraCaptureTool,
    AndroidDeviceActionTool,
    AndroidLaunchAppTool,
    AndroidManageFilesTool,
    AndroidMediaControlTool,
    AndroidOpenSettingsTool,
    AndroidReadNotificationsTool,
    AndroidSetAlarmTool,
    AndroidUIInteractTool,
    AndroidVolumeControlTool,
    get_android_tools,
)

# ===========================================================================
# 1. ANDROID SECURITY & PAIRING TESTS
# ===========================================================================


class TestAndroidSecurityManager:
    """Tests for pairing codes, tokens, and HMAC signing."""

    def test_pairing_code_generation_and_verification(self):
        sec = AndroidSecurityManager()

        code = sec.generate_pairing_code(expiry_seconds=60)
        assert len(code) == 6
        assert code.isupper() or code.isalnum()

        # Valid verification
        token = sec.verify_pairing_code(code, "dev_pixel_8", "Pixel 8 Pro")
        assert token is not None
        assert len(token) > 20
        assert sec.is_device_authorized("dev_pixel_8", token) is True

        # Reusing code should fail
        fail_token = sec.verify_pairing_code(code, "dev_pixel_8", "Pixel 8 Pro")
        assert fail_token is None

    def test_hmac_signing_and_verification(self):
        sec = AndroidSecurityManager(secret_key="nexus_test_secret_key_123")
        payload = b'{"action": "launch_app", "app": "Spotify"}'

        sig = sec.sign_payload(payload)
        assert isinstance(sig, str)
        assert len(sig) == 64  # SHA256 hex string

        assert sec.verify_signature(payload, sig) is True
        assert sec.verify_signature(b'{"tampered": true}', sig) is False

    def test_unpair_device(self):
        sec = AndroidSecurityManager()
        code = sec.generate_pairing_code()
        token = sec.verify_pairing_code(code, "dev_1", "Test Phone")
        assert token is not None

        assert sec.unpair_device("dev_1") is True
        assert sec.is_device_authorized("dev_1", token) is False


# ===========================================================================
# 2. ANDROID DEVICE BRIDGE TESTS
# ===========================================================================


class TestAndroidDeviceBridge:
    """Tests for WebSocket connection tracking, telemetry, and notifications."""

    @pytest.mark.asyncio
    async def test_connection_and_telemetry(self):
        bridge = AndroidDeviceBridge()

        mock_ws = AsyncMock()
        await bridge.register_connection("pixel_8", mock_ws)
        assert bridge.is_online("pixel_8") is True
        assert bridge.active_connections_count == 1

        # Telemetry update
        status = AndroidDeviceStatus(
            device_id="pixel_8",
            device_name="Pixel 8",
            battery_percent=85,
            is_charging=True,
            current_volume=60,
        )
        await bridge.update_device_status(status)

        retrieved = bridge.get_device_status("pixel_8")
        assert retrieved is not None
        assert retrieved.battery_percent == 85
        assert retrieved.is_charging is True

        # Notifications
        notif = AndroidNotificationItem(
            id="n1",
            package_name="com.whatsapp",
            app_name="WhatsApp",
            title="Alice",
            text="Meeting at 3 PM",
        )
        await bridge.add_notifications([notif])
        recent = bridge.get_recent_notifications()
        assert len(recent) == 1
        assert recent[0].title == "Alice"

        # Teardown connection
        await bridge.unregister_connection("pixel_8")
        assert bridge.is_online("pixel_8") is False

    @pytest.mark.asyncio
    async def test_command_dispatch_and_resolution(self):
        bridge = AndroidDeviceBridge()
        mock_ws = AsyncMock()
        await bridge.register_connection("phone_1", mock_ws)

        cmd = AndroidCommandRequest(
            request_id="cmd_123",
            action_type="launch_app",
            parameters={"app_name": "YouTube"},
        )

        # Simulate response in background
        async def mock_device_worker():
            resp = AndroidCommandResponse(
                request_id="cmd_123",
                action_type="launch_app",
                success=True,
                output="Launched YouTube",
            )
            bridge.handle_command_response(resp)

        import asyncio

        asyncio.create_task(mock_device_worker())

        result = await bridge.dispatch_command("phone_1", cmd)
        assert result.success is True
        assert result.output == "Launched YouTube"


# ===========================================================================
# 3. ANDROID AGENT TESTS
# ===========================================================================


class TestAndroidAgent:
    """Tests for backend agent coordination and action execution."""

    @pytest.mark.asyncio
    async def test_agent_action_routing(self):
        agent = AndroidAgent()

        # Pair device first
        code = agent.security.generate_pairing_code()
        agent.security.verify_pairing_code(code, "dev_galaxy", "Galaxy S24")
        reg = AndroidDeviceRegistration(
            device_id="dev_galaxy",
            device_name="Galaxy S24",
            android_version="14",
        )
        agent.register_device(reg)

        assert agent.has_paired_device is True
        assert agent.primary_device_id == "dev_galaxy"

        # Execute action (offline simulation fallback)
        res = await agent.execute_action(
            action_type="volume_control",
            parameters={"action": "set", "level": 70},
        )
        assert res.success is True
        assert "Executed 'volume_control'" in res.output

        status = agent.get_status()
        assert status["paired_devices_count"] == 1


# ===========================================================================
# 4. ANDROID LLM TOOLS SUITE TESTS
# ===========================================================================


class TestAndroidToolsSuite:
    """Tests for all 11 Android tools."""

    @pytest.mark.asyncio
    async def test_all_mobile_tools(self):
        agent = AndroidAgent()
        code = agent.security.generate_pairing_code()
        agent.security.verify_pairing_code(code, "dev_phone", "Android Test Phone")

        # 1. Launch App
        launch_tool = AndroidLaunchAppTool(agent=agent)
        res_launch = await launch_tool.execute(app_name="Spotify")
        assert res_launch.success is True

        # 2. UI Interact
        ui_tool = AndroidUIInteractTool(agent=agent)
        res_ui = await ui_tool.execute(action="click", target_text="Play")
        assert res_ui.success is True

        # 3. Read Notifications
        notif_tool = AndroidReadNotificationsTool(agent=agent)
        res_notif = await notif_tool.execute()
        assert res_notif.success is True

        # 4. Media Control
        media_tool = AndroidMediaControlTool(agent=agent)
        res_media = await media_tool.execute(action="play")
        assert res_media.success is True

        # 5. Volume Control
        vol_tool = AndroidVolumeControlTool(agent=agent)
        res_vol = await vol_tool.execute(action="set", level=80)
        assert res_vol.success is True

        # 6. Set Alarm
        alarm_tool = AndroidSetAlarmTool(agent=agent)
        res_alarm = await alarm_tool.execute(type="alarm", hour=7, minutes=30)
        assert res_alarm.success is True

        # 7. Open Settings
        settings_tool = AndroidOpenSettingsTool(agent=agent)
        res_settings = await settings_tool.execute(setting="bluetooth")
        assert res_settings.success is True

        # 8. Device Action
        action_tool = AndroidDeviceActionTool(agent=agent)
        res_action = await action_tool.execute(action="flashlight_on")
        assert res_action.success is True

        # 9. Manage Files
        files_tool = AndroidManageFilesTool(agent=agent)
        res_files = await files_tool.execute(action="list", path="Download")
        assert res_files.success is True

        # 10. Camera Capture
        camera_tool = AndroidCameraCaptureTool(agent=agent)
        res_cam = await camera_tool.execute(lens="back")
        assert res_cam.success is True

        # 11. Call & SMS
        sms_tool = AndroidCallSmsTool(agent=agent)
        res_sms = await sms_tool.execute(
            action="send_sms",
            phone_number="+1234567890",
            message="Hello from NEXUS",
        )
        assert res_sms.success is True

    def test_factory(self):
        tools = get_android_tools()
        assert len(tools) == 11


# ===========================================================================
# 5. FASTAPI ANDROID ROUTES TESTS
# ===========================================================================


class TestFastAPIAndroidRoutes:
    """Tests for REST and WebSocket endpoints on /api/android/*."""

    @pytest.mark.asyncio
    async def test_rest_endpoints(self):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Initiate pairing
            res_init = await ac.post("/api/android/pair/initiate")
            assert res_init.status_code == 200
            data_init = res_init.json()
            code = data_init["pairing_code"]
            assert len(code) == 6

            # 2. Confirm pairing
            res_conf = await ac.post(
                "/api/android/pair/confirm",
                json={
                    "device_id": "test_pixel",
                    "device_name": "Google Pixel 8",
                    "pairing_code": code,
                },
            )
            assert res_conf.status_code == 200
            token = res_conf.json()["auth_token"]
            assert token is not None

            # 3. Get status
            res_status = await ac.get("/api/android/status")
            assert res_status.status_code == 200
            assert res_status.json()["paired_devices_count"] >= 1

            # 4. Post notifications batch
            batch = AndroidNotificationBatch(
                device_id="test_pixel",
                notifications=[
                    AndroidNotificationItem(
                        id="n99",
                        package_name="com.slack",
                        app_name="Slack",
                        title="Dev Channel",
                        text="Build passing",
                    )
                ],
            )
            res_notif = await ac.post("/api/android/notifications", json=batch.model_dump())
            assert res_notif.status_code == 200
            assert res_notif.json()["received_count"] == 1

            # 5. Report permissions
            perm_report = AndroidPermissionReport(
                device_id="test_pixel",
                accessibility_enabled=True,
                microphone_granted=True,
            )
            res_perm = await ac.post("/api/android/permissions", json=perm_report.model_dump())
            assert res_perm.status_code == 200
            assert res_perm.json()["success"] is True
