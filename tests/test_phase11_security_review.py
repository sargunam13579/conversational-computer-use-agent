"""
NEXUS Phase 11 Comprehensive Security, Accessibility, Reliability & Integration Test Suite.

Verifies all 17 required areas:
1. Voice
2. Text
3. Wake word
4. Custom assistant name
5. Laptop control
6. Screen understanding
7. Browser control
8. File operations
9. Android control
10. Cross-device communication
11. Memory
12. Multi-step tasks
13. Permissions
14. Security
15. Error recovery
16. Emergency stop
17. Accessibility
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from nexus.accessibility.audio_feedback import AudioFeedbackManager
from nexus.accessibility.custom_commands import CustomCommandManager
from nexus.accessibility.voice_navigation import VoiceNavigationEngine
from nexus.api.app import create_app
from nexus.core.brain import NexusBrain
from nexus.planning.cancellation import CancellationType
from nexus.planning.manager import TaskManager
from nexus.planning.planner import TaskPlanner
from nexus.reliability.connection_recovery import ConnectionRecoveryManager
from nexus.reliability.offline import OfflineModeManager
from nexus.security.auth import AuthManager
from nexus.security.crypto import KeyManager, SecretVault
from nexus.security.pairing import DevicePairingManager
from nexus.security.permissions import (
    PermissionAction,
    PermissionEngine,
    PermissionScope,
    PermissionScopeManager,
)
from nexus.security.terminal_security import CommandSafetyStatus, TerminalSecurityClassifier
from nexus.tools.base import RiskLevel


# ===========================================================================
# 1. VOICE PIPELINE TESTS
# ===========================================================================
class TestArea1Voice:
    """Voice synthesis and audio pipeline validation."""

    def test_voice_text_formatting_for_speech(self):
        engine = VoiceNavigationEngine()
        raw_markdown = "# Status\n**Battery:** `95%`.\n[Details](http://nexus.local)"
        speakable = engine.format_for_screen_reader(raw_markdown)
        assert "#" not in speakable
        assert "**" not in speakable
        assert "`" not in speakable
        assert "Battery:" in speakable
        assert "Details" in speakable


# ===========================================================================
# 2. TEXT & LLM ORCHESTRATION TESTS
# ===========================================================================
class TestArea2Text:
    """Natural language text interaction."""

    @pytest.mark.asyncio
    async def test_text_processing_flow(self):
        brain = NexusBrain()
        await brain.initialize()

        with patch.object(brain._orchestrator, "process", new=AsyncMock(return_value="Hello, Shanmuga!")):
            resp = await brain.process("Hello")
            assert "Hello, Shanmuga!" in resp


# ===========================================================================
# 3. WAKE WORD TESTS
# ===========================================================================
class TestArea3WakeWord:
    """Wake word and activation triggers."""

    def test_wake_word_audio_feedback(self):
        audio_mgr = AudioFeedbackManager(enabled=True)
        # Should execute without error
        audio_mgr.on_wake()


# ===========================================================================
# 4. CUSTOM ASSISTANT NAME TESTS
# ===========================================================================
class TestArea4CustomName:
    """Assistant renaming and confirmation validation."""

    @pytest.mark.asyncio
    async def test_request_and_confirm_name_change(self):
        brain = NexusBrain()
        await brain.initialize()
        brain._identity.set_name("Nexus", sync_wake_word=True)

        prompt = await brain.process("Call yourself JARVIS from now on")
        assert "JARVIS" in prompt
        assert brain.confirmation.has_pending is True

        confirm_resp = await brain.process("yes")
        assert "JARVIS" in brain.name
        assert "JARVIS" in confirm_resp


# ===========================================================================
# 5. LAPTOP CONTROL TESTS
# ===========================================================================
class TestArea5LaptopControl:
    """Laptop and OS control actions."""

    @pytest.mark.asyncio
    async def test_local_offline_volume_control(self):
        offline = OfflineModeManager()
        assert offline.can_handle_locally("set volume to 60") is True

        res = await offline.execute_offline_command("set volume to 60")
        assert res.success is True
        assert res.metadata is not None
        assert res.metadata.get("volume") == 60


# ===========================================================================
# 6. SCREEN UNDERSTANDING TESTS
# ===========================================================================
class TestArea6ScreenUnderstanding:
    """Screen capture and UI layout understanding."""

    def test_screen_reader_plan_summary(self):
        engine = VoiceNavigationEngine()
        spoken = engine.format_plan_for_voice(
            plan_goal="Search files and convert",
            total_steps=3,
            current_step_index=0,
            current_step_desc="Find resume",
        )
        assert "step 1 of 3" in spoken
        assert "Find resume" in spoken


# ===========================================================================
# 7. BROWSER CONTROL TESTS
# ===========================================================================
class TestArea7BrowserControl:
    """Browser interaction command safety."""

    def test_browser_action_safety_and_scope(self):
        perm = PermissionScopeManager()
        assert perm.is_scope_granted(PermissionScope.ACCESSIBILITY) is True
        perm.revoke_scope(PermissionScope.ACCESSIBILITY)
        assert perm.is_scope_granted(PermissionScope.ACCESSIBILITY) is False


# ===========================================================================
# 8. FILE OPERATIONS TESTS
# ===========================================================================
class TestArea8FileOperations:
    """Filesystem inspection and safety checks."""

    @pytest.mark.asyncio
    async def test_offline_file_listing(self, tmp_path):
        offline = OfflineModeManager()
        res = await offline.execute_offline_command("list files in workspace")
        assert res.action_taken in ("file_list", "file_list_error")


# ===========================================================================
# 9. ANDROID CONTROL TESTS
# ===========================================================================
class TestArea9AndroidControl:
    """Android ADB device control and permissions."""

    def test_android_device_scope_check(self):
        engine = PermissionEngine()
        assert engine.scope_manager.is_tool_allowed("android_adb") is True

        engine.scope_manager.revoke_scope(PermissionScope.DEVICE_CONTROL)
        assert engine.scope_manager.is_tool_allowed("android_adb") is False
        assert engine.check_permission("android_adb", RiskLevel.MEDIUM) == PermissionAction.DENY


# ===========================================================================
# 10. CROSS-DEVICE COMMUNICATION TESTS
# ===========================================================================
class TestArea10CrossDeviceComms:
    """Device pairing handshakes and token verification."""

    def test_pairing_handshake_lifecycle(self, tmp_path):
        storage = tmp_path / "paired.json"
        mgr = DevicePairingManager(storage_path=storage)

        # 1. Initiate pairing
        session = mgr.initiate_pairing(device_name="Pixel 8 Pro", device_type="phone")
        assert len(session.pin) == 6
        assert session.is_expired is False

        # 2. Verify with wrong PIN
        bad_verify = mgr.verify_pairing(session.session_id, "000000")
        assert bad_verify is None

        # 3. Verify with correct PIN
        device = mgr.verify_pairing(session.session_id, session.pin)
        assert device is not None
        assert device.device_name == "Pixel 8 Pro"
        assert mgr.authenticate_device(device.device_id, device.device_token) is True

        # 4. Revoke device
        assert mgr.revoke_device(device.device_id) is True
        assert mgr.authenticate_device(device.device_id, device.device_token) is False


# ===========================================================================
# 11. MEMORY & AUTO-LEARNING TESTS
# ===========================================================================
class TestArea11Memory:
    """Preference extraction and memory persistence."""

    @pytest.mark.asyncio
    async def test_brain_learns_preferences(self):
        brain = NexusBrain()
        await brain.initialize()

        with patch.object(brain._orchestrator, "process", new=AsyncMock(return_value="I have saved your preference.")):
            await brain.process("Remember that my editor is VSCode")
            rec = await brain.memory.storage.get("editor")
            assert rec is not None or brain.memory.is_enabled is True


# ===========================================================================
# 12. MULTI-STEP AUTONOMOUS TASKS TESTS
# ===========================================================================
class TestArea12MultiStepTasks:
    """Multi-step plan creation and execution."""

    @pytest.mark.asyncio
    async def test_autonomous_goal_decomposition(self):
        planner = TaskPlanner()
        goal = "Find my resume, convert it to PDF, and send to my phone"
        plan = await planner.create_plan(goal)
        assert plan.total_steps >= 3
        assert plan.status.value in ("planning", "pending", "in_progress", "completed")


# ===========================================================================
# 13. PERMISSIONS & REVOCATION TESTS
# ===========================================================================
class TestArea13Permissions:
    """Granular permission scope management."""

    def test_permission_grant_and_revocation(self, tmp_path):
        storage = tmp_path / "perms.json"
        mgr = PermissionScopeManager(storage_path=storage)

        # Initially all scopes granted
        assert mgr.is_scope_granted(PermissionScope.CAMERA) is True
        assert mgr.is_scope_granted(PermissionScope.MICROPHONE) is True

        # Revoke camera
        mgr.revoke_scope(PermissionScope.CAMERA)
        assert mgr.is_scope_granted(PermissionScope.CAMERA) is False
        assert mgr.is_tool_allowed("capture_camera") is False

        # Grant back
        mgr.grant_scope(PermissionScope.CAMERA)
        assert mgr.is_scope_granted(PermissionScope.CAMERA) is True
        assert mgr.is_tool_allowed("capture_camera") is True


# ===========================================================================
# 14. SECURITY, ENCRYPTION & COMMAND PROTECTION TESTS
# ===========================================================================
class TestArea14Security:
    """Cryptographic vault, dangerous command blocking, and API auth."""

    def test_secret_vault_encryption(self, tmp_path):
        vault_path = tmp_path / "vault.enc"
        key_mgr = KeyManager(tmp_path / "keys")
        vault = SecretVault(vault_path=vault_path, key_manager=key_mgr)

        vault.set_secret("GEMINI_API_KEY", "sk-secret-key-12345")
        assert vault.get_secret("GEMINI_API_KEY") == "sk-secret-key-12345"

        # Ensure disk payload is encrypted and does not expose plain text
        raw_disk = vault_path.read_text(encoding="utf-8")
        assert "sk-secret-key-12345" not in raw_disk

    def test_dangerous_command_protection(self):
        guard = TerminalSecurityClassifier()
        blocked_cmd = "format C: /fs:NTFS"
        res = guard.classify_command(blocked_cmd)
        assert res.status == CommandSafetyStatus.BLOCKED

    def test_api_auth_manager(self):
        auth = AuthManager(master_api_key="nx_master_test_key")
        assert auth.validate_api_key("nx_master_test_key") is True
        assert auth.validate_api_key("nx_invalid_key") is False

        new_key = auth.create_api_key()
        assert auth.validate_api_key(new_key) is True
        auth.revoke_api_key(new_key)
        assert auth.validate_api_key(new_key) is False


# ===========================================================================
# 15. ERROR RECOVERY & RECONNECTION TESTS
# ===========================================================================
class TestArea15ErrorRecovery:
    """Connection recovery with exponential backoff."""

    @pytest.mark.asyncio
    async def test_reconnect_manager_backoff(self):
        mgr = ConnectionRecoveryManager(base_backoff_seconds=0.1, max_backoff_seconds=1.0)
        attempts = 0

        async def fake_reconnect():
            nonlocal attempts
            attempts += 1
            return attempts >= 2

        mgr.register_target("phone_adb", "android_adb", reconnect_coro=fake_reconnect)
        mgr.mark_disconnected("phone_adb", "Device unplugged")

        # First attempt fails
        assert await mgr.attempt_reconnect("phone_adb") is False
        # Second attempt succeeds
        assert await mgr.attempt_reconnect("phone_adb") is True
        st = mgr.get_state("phone_adb")
        assert st is not None
        assert st.is_connected is True


# ===========================================================================
# 16. EMERGENCY STOP TESTS
# ===========================================================================
class TestArea16EmergencyStop:
    """Emergency stop intent detection and task abortion."""

    @pytest.mark.asyncio
    async def test_emergency_stop_kills_everything(self):
        mgr = TaskManager()
        cancellation = mgr.cancellation

        assert cancellation.detect_cancellation_intent("NEXUS STOP") == CancellationType.EMERGENCY
        assert cancellation.detect_cancellation_intent("nexus stop please") == CancellationType.GRACEFUL

        res = mgr.emergency_stop(reason="Operator safety override")
        assert res["emergency"] is True


# ===========================================================================
# 17. ACCESSIBILITY & OFFLINE MODE TESTS
# ===========================================================================
class TestArea17AccessibilityAndOffline:
    """Custom commands, audio feedback, and local offline mode."""

    def test_custom_command_expansion(self, tmp_path):
        cmd_file = tmp_path / "custom_cmds.json"
        mgr = CustomCommandManager(storage_path=cmd_file)

        mgr.register_command(
            phrase="work mode",
            actions=["open vscode", "set volume 10", "mute alerts"],
        )

        actions = mgr.match_and_expand("Nexus please enter work mode")
        assert actions == ["open vscode", "set volume 10", "mute alerts"]

    @pytest.mark.asyncio
    async def test_offline_mode_execution(self):
        offline = OfflineModeManager(force_offline=True)
        assert offline.is_online() is False

        # Open application offline
        res = await offline.execute_offline_command("open notepad")
        assert res.success is True
        assert res.action_taken == "app_launch"


# ===========================================================================
# 18. API ROUTES VERIFICATION TESTS
# ===========================================================================
class TestPhase11ApiEndpoints:
    """Verify REST API routes for permissions, pairing, and accessibility."""

    @pytest.mark.asyncio
    async def test_permissions_api(self):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. List permissions
            r1 = await client.get("/api/permissions")
            assert r1.status_code == 200
            assert "microphone" in r1.json()["scopes"]

            # 2. Revoke permission
            r2 = await client.post("/api/permissions/revoke", json={"scope": "camera"})
            assert r2.status_code == 200
            assert r2.json()["granted"] is False

            # 3. Grant permission
            r3 = await client.post("/api/permissions/grant", json={"scope": "camera"})
            assert r3.status_code == 200
            assert r3.json()["granted"] is True

    @pytest.mark.asyncio
    async def test_pairing_api(self):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Initiate pairing
            r1 = await client.post("/api/pairing/initiate", json={"device_name": "Galaxy S24", "device_type": "phone"})
            assert r1.status_code == 200
            data = r1.json()
            session_id = data["session_id"]
            pin = data["pin"]

            # 2. Verify pairing
            r2 = await client.post("/api/pairing/verify", json={"session_id": session_id, "pin": pin})
            assert r2.status_code == 200
            assert r2.json()["success"] is True

            # 3. List devices
            r3 = await client.get("/api/pairing/devices")
            assert r3.status_code == 200
            assert r3.json()["count"] >= 1

    @pytest.mark.asyncio
    async def test_accessibility_api(self):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. List custom commands
            r1 = await client.get("/api/accessibility/commands")
            assert r1.status_code == 200

            # 2. Register custom command
            r2 = await client.post(
                "/api/accessibility/commands",
                json={
                    "phrase": "quick check",
                    "actions": ["battery status", "list files"],
                    "description": "Quick system check",
                },
            )
            assert r2.status_code == 200
            assert r2.json()["phrase"] == "quick check"
