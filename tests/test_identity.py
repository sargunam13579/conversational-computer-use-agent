"""
Unit and Integration Tests for Phase 3 — Assistant Identity, Wake Word & Confirmation.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nexus.api.app import create_app
from nexus.core.brain import NexusBrain
from nexus.core.config import NexusSettings
from nexus.core.confirmation import (
    ConfirmationAction,
    ConfirmationManager,
    ConfirmationStatus,
)
from nexus.core.identity import (
    DEFAULT_ASSISTANT_NAME,
    DEFAULT_WAKE_WORD,
    IdentityManager,
)
from nexus.llm.prompts.system import build_system_prompt
from nexus.voice.wake_word import WakeWordDetector

# ===========================================================================
# 1. Identity Manager Tests
# ===========================================================================


class TestIdentityManager:
    """Tests for IdentityManager configuration and persistence."""

    def test_default_identity(self, tmp_path: Path):
        id_file = tmp_path / "identity.json"
        mgr = IdentityManager(storage_path=id_file)

        assert mgr.name == DEFAULT_ASSISTANT_NAME
        assert mgr.wake_word == DEFAULT_WAKE_WORD
        assert mgr.aliases == []
        assert mgr.user_name == "User"
        assert DEFAULT_ASSISTANT_NAME in mgr.all_wake_words

    def test_set_name_syncs_wake_word(self, tmp_path: Path):
        id_file = tmp_path / "identity.json"
        mgr = IdentityManager(storage_path=id_file)

        mgr.set_name("Aria", sync_wake_word=True)
        assert mgr.name == "Aria"
        assert mgr.wake_word == "Aria"
        assert "Aria" in mgr.all_wake_words

    def test_set_name_without_wake_word_sync(self, tmp_path: Path):
        id_file = tmp_path / "identity.json"
        mgr = IdentityManager(storage_path=id_file)

        mgr.set_name("Aria", sync_wake_word=False)
        assert mgr.name == "Aria"
        assert mgr.wake_word == DEFAULT_WAKE_WORD

    def test_empty_name_raises(self, tmp_path: Path):
        mgr = IdentityManager(storage_path=tmp_path / "identity.json")
        with pytest.raises(ValueError, match="cannot be empty"):
            mgr.set_name("   ")

    def test_empty_wake_word_raises(self, tmp_path: Path):
        mgr = IdentityManager(storage_path=tmp_path / "identity.json")
        with pytest.raises(ValueError, match="cannot be empty"):
            mgr.set_wake_word("")

    def test_alias_management(self, tmp_path: Path):
        mgr = IdentityManager(storage_path=tmp_path / "identity.json")

        assert mgr.add_alias("Ari") is True
        assert "Ari" in mgr.aliases
        # Duplicate should return False
        assert mgr.add_alias("ari") is False
        assert len(mgr.aliases) == 1

        assert mgr.add_alias("Assistant") is True
        assert len(mgr.aliases) == 2
        assert "Ari" in mgr.all_wake_words
        assert "Assistant" in mgr.all_wake_words

        # Remove alias
        assert mgr.remove_alias("Ari") is True
        assert "Ari" not in mgr.aliases
        assert mgr.remove_alias("NonExistent") is False

    def test_persistence_save_and_reload(self, tmp_path: Path):
        id_file = tmp_path / "identity.json"
        mgr1 = IdentityManager(storage_path=id_file)
        mgr1.set_name("Jarvis")
        mgr1.add_alias("J")
        mgr1.set_user_name("Alice")
        mgr1.set_require_wake_word(True)

        assert id_file.exists()
        saved_data = json.loads(id_file.read_text(encoding="utf-8"))
        assert saved_data["assistant_name"] == "Jarvis"
        assert saved_data["wake_word"] == "Jarvis"
        assert saved_data["aliases"] == ["J"]
        assert saved_data["user_name"] == "Alice"
        assert saved_data["require_wake_word"] is True

        # Reload in a new manager
        mgr2 = IdentityManager(storage_path=id_file)
        assert mgr2.name == "Jarvis"
        assert mgr2.wake_word == "Jarvis"
        assert mgr2.aliases == ["J"]
        assert mgr2.user_name == "Alice"
        assert mgr2.config.require_wake_word is True

    def test_update_bulk(self, tmp_path: Path):
        mgr = IdentityManager(storage_path=tmp_path / "identity.json")
        mgr.update(
            assistant_name="Aria",
            wake_word="Hey Aria",
            aliases=["Ari", "Computer"],
            user_name="Bob",
            require_wake_word=True,
        )
        assert mgr.name == "Aria"
        assert mgr.wake_word == "Hey Aria"
        assert mgr.aliases == ["Ari", "Computer"]
        assert mgr.user_name == "Bob"
        assert mgr.config.require_wake_word is True


# ===========================================================================
# 2. Confirmation Security Engine Tests
# ===========================================================================


class TestConfirmationManager:
    """Tests for two-step verification and confirmation lifecycle."""

    def test_initial_state_no_pending(self):
        cm = ConfirmationManager()
        assert not cm.has_pending
        assert cm.pending_action is None

    def test_create_pending_confirmation(self):
        cm = ConfirmationManager(default_timeout=30.0)
        conf = cm.create_confirmation(
            action=ConfirmationAction.CHANGE_NAME,
            prompt_message="Do you want to change name?",
            payload={"new_name": "Aria"},
        )
        assert cm.has_pending
        assert cm.pending_action is not None
        assert cm.pending_action.id == conf.id
        assert cm.pending_action.action == ConfirmationAction.CHANGE_NAME
        assert cm.pending_action.payload == {"new_name": "Aria"}

    def test_affirmative_intent_matching(self):
        cm = ConfirmationManager()
        assert cm.is_affirmative("yes")
        assert cm.is_affirmative("Yes, please")
        assert cm.is_affirmative("yep")
        assert cm.is_affirmative("Sure!")
        assert cm.is_affirmative("confirm")
        assert cm.is_affirmative("proceed")
        assert cm.is_affirmative("absolutely")

    def test_negative_intent_matching(self):
        cm = ConfirmationManager()
        assert cm.is_negative("no")
        assert cm.is_negative("No thanks")
        assert cm.is_negative("cancel")
        assert cm.is_negative("stop")
        assert cm.is_negative("never mind")
        assert cm.is_negative("abort")

    @pytest.mark.asyncio
    async def test_confirm_flow(self):
        cm = ConfirmationManager()
        callback_called = False

        def on_confirm(payload):
            nonlocal callback_called
            callback_called = True
            return f"Changed name to {payload['target']}!"

        cm.create_confirmation(
            action=ConfirmationAction.CHANGE_NAME,
            prompt_message="Change name?",
            payload={"target": "Aria"},
            on_confirm=on_confirm,
        )

        status, msg = await cm.handle_response("yes")
        assert status == ConfirmationStatus.CONFIRMED
        assert callback_called is True
        assert msg == "Changed name to Aria!"
        assert not cm.has_pending

    @pytest.mark.asyncio
    async def test_reject_flow(self):
        cm = ConfirmationManager()
        callback_called = False

        def on_reject(payload):
            nonlocal callback_called
            callback_called = True
            return "Name change aborted."

        cm.create_confirmation(
            action=ConfirmationAction.CHANGE_NAME,
            prompt_message="Change name?",
            on_reject=on_reject,
        )

        status, msg = await cm.handle_response("no")
        assert status == ConfirmationStatus.REJECTED
        assert callback_called is True
        assert msg == "Name change aborted."
        assert not cm.has_pending

    @pytest.mark.asyncio
    async def test_ambiguous_response_prompts_again(self):
        cm = ConfirmationManager()
        cm.create_confirmation(
            action=ConfirmationAction.CHANGE_NAME,
            prompt_message="Do you want to change name?",
        )

        status, msg = await cm.handle_response("What is the weather today?")
        assert status == ConfirmationStatus.PENDING
        assert "Please reply 'Yes' or 'No'" in msg
        assert cm.has_pending

    @pytest.mark.asyncio
    async def test_expired_confirmation(self):
        cm = ConfirmationManager(default_timeout=0.01)
        cm.create_confirmation(
            action=ConfirmationAction.CHANGE_NAME,
            prompt_message="Change name?",
            timeout_seconds=0.01,
        )
        await asyncio.sleep(0.02)

        assert not cm.has_pending
        status, msg = await cm.confirm()
        assert status == ConfirmationStatus.EXPIRED


# ===========================================================================
# 3. Dynamic Wake-Word Detection Tests
# ===========================================================================


class TestWakeWordDetector:
    """Tests for WakeWordDetector matching prefixes, aliases, and commands."""

    def test_direct_wake_word(self):
        detector = WakeWordDetector(wake_words=["NEXUS"])
        match = detector.detect("Nexus, open Chrome")
        assert match.matched is True
        assert match.wake_word == "NEXUS"
        assert match.command == "open Chrome"

    def test_prefix_wake_word(self):
        detector = WakeWordDetector(wake_words=["NEXUS"])
        match1 = detector.detect("Hey Nexus, what time is it?")
        assert match1.matched is True
        assert match1.prefix == "hey"
        assert match1.wake_word == "NEXUS"
        assert match1.command == "what time is it"

        match2 = detector.detect("OK Nexus, turn up the volume")
        assert match2.matched is True
        assert match2.prefix == "ok"
        assert match2.command == "turn up the volume"

        match3 = detector.detect("Hi Nexus, check battery")
        assert match3.matched is True
        assert match3.prefix == "hi"
        assert match3.command == "check battery"

    def test_standalone_wake_word_no_command(self):
        detector = WakeWordDetector(wake_words=["NEXUS"])
        match1 = detector.detect("Nexus")
        assert match1.matched is True
        assert match1.command == ""
        assert not match1.has_command

        match2 = detector.detect("Hey Nexus")
        assert match2.matched is True
        assert match2.prefix == "hey"
        assert match2.command == ""

    def test_trailing_wake_word(self):
        detector = WakeWordDetector(wake_words=["NEXUS"])
        match = detector.detect("Open Chrome, Nexus")
        assert match.matched is True
        assert match.command == "Open Chrome"

    def test_alias_detection(self):
        detector = WakeWordDetector(wake_words=["NEXUS", "Aria", "Ari"])
        match_aria = detector.detect("Hey Aria, play some music")
        assert match_aria.matched is True
        assert match_aria.wake_word == "Aria"
        assert match_aria.command == "play some music"

        match_ari = detector.detect("Ari, what is 2+2?")
        assert match_ari.matched is True
        assert match_ari.wake_word == "Ari"
        assert match_ari.command == "what is 2+2"

    def test_name_change_stops_old_name_unless_in_aliases(self):
        detector = WakeWordDetector(wake_words=["NEXUS"])
        # Initially NEXUS matches
        assert detector.detect("Nexus, open Chrome").matched is True
        assert detector.detect("Aria, open Chrome").matched is False

        # Change wake words to Aria (without NEXUS alias)
        detector.update_wake_words(primary="Aria", aliases=[])
        assert detector.detect("Nexus, open Chrome").matched is False
        assert detector.detect("Aria, open Chrome").matched is True

        # Change wake words to Aria WITH NEXUS as alias
        detector.update_wake_words(primary="Aria", aliases=["NEXUS"])
        assert detector.detect("Nexus, open Chrome").matched is True
        assert detector.detect("Aria, open Chrome").matched is True


# ===========================================================================
# 4. System Prompt & Brain Identity Integration Tests
# ===========================================================================


class TestSystemPromptDynamicIdentity:
    """Tests for dynamic prompt injection with custom assistant identity."""

    def test_default_prompt_name(self):
        prompt = build_system_prompt(assistant_name="NEXUS")
        assert "You are NEXUS" in prompt
        assert "Assistant Name: NEXUS" in prompt

    def test_custom_prompt_name(self):
        prompt = build_system_prompt(assistant_name="Aria", user_name="Alice")
        assert "You are Aria" in prompt
        assert "Assistant Name: Aria" in prompt
        assert "User: Alice" in prompt


class TestNexusBrainIdentityFlow:
    """Tests for complete name change and confirmation workflow through NexusBrain."""

    @pytest.mark.asyncio
    async def test_name_change_confirmation_flow(self, tmp_path: Path):
        settings = NexusSettings()
        id_mgr = IdentityManager(storage_path=tmp_path / "identity.json")
        brain = NexusBrain(settings=settings, identity=id_mgr)
        await brain.initialize()

        assert brain.name == "NEXUS"

        # 1. User asks to change name
        resp1 = await brain.process("Nexus, from now on your name is Aria")
        assert "Do you want me to change my name from NEXUS to Aria?" in resp1
        assert brain.confirmation.has_pending

        # 2. User confirms
        resp2 = await brain.process("Yes")
        assert "My name has been changed to Aria" in resp2
        assert brain.name == "Aria"
        assert brain.identity.wake_word == "Aria"
        assert not brain.confirmation.has_pending

        # 3. Context system prompt has been updated
        sys_prompt = brain._context.get_system_prompt()
        assert "You are Aria" in sys_prompt

    @pytest.mark.asyncio
    async def test_name_change_rejected_flow(self, tmp_path: Path):
        settings = NexusSettings()
        id_mgr = IdentityManager(storage_path=tmp_path / "identity.json")
        brain = NexusBrain(settings=settings, identity=id_mgr)
        await brain.initialize()

        # 1. User asks to change name
        await brain.process("Change your name to Jarvis")
        assert brain.confirmation.has_pending

        # 2. User rejects
        resp2 = await brain.process("No")
        assert "cancelled" in resp2.lower()
        assert brain.name == "NEXUS"  # Name should remain unchanged
        assert not brain.confirmation.has_pending


# ===========================================================================
# 5. Identity REST API Routes Tests
# ===========================================================================


class TestIdentityAPIRoutes:
    """Tests for `/api/identity` and `/api/wake-word` endpoints."""

    def test_get_identity_endpoint(self, tmp_path: Path):
        settings = NexusSettings()
        app = create_app(settings)
        id_mgr = IdentityManager(storage_path=tmp_path / "identity.json")
        mock_brain = NexusBrain(settings=settings, identity=id_mgr)

        with TestClient(app) as client:
            app.state.brain = mock_brain
            resp = client.get("/api/identity")
            assert resp.status_code == 200
            data = resp.json()
            assert data["assistant_name"] == "NEXUS"
            assert data["wake_word"] == "NEXUS"
            assert data["require_wake_word"] is False

    def test_change_name_and_confirm_endpoint(self, tmp_path: Path):
        settings = NexusSettings()
        app = create_app(settings)
        id_mgr = IdentityManager(storage_path=tmp_path / "identity.json")
        mock_brain = NexusBrain(settings=settings, identity=id_mgr)

        with TestClient(app) as client:
            app.state.brain = mock_brain

            # Step 1: Initiate name change
            init_resp = client.post("/api/identity/change-name", json={"name": "Aria"})
            assert init_resp.status_code == 200
            init_data = init_resp.json()
            assert init_data["target_name"] == "Aria"
            prompt_str = "Do you want me to change my name from NEXUS to Aria?"
            assert prompt_str in init_data["confirmation_prompt"]

            # Step 2: Confirm action
            conf_resp = client.post("/api/identity/confirm", json={"confirmed": True})
            assert conf_resp.status_code == 200
            assert conf_resp.json()["confirmed"] is True
            assert mock_brain.name == "Aria"

            # Step 3: Check identity
            get_resp = client.get("/api/identity")
            assert get_resp.json()["assistant_name"] == "Aria"
            assert get_resp.json()["wake_word"] == "Aria"

    def test_alias_api_endpoints(self, tmp_path: Path):
        settings = NexusSettings()
        app = create_app(settings)
        id_mgr = IdentityManager(storage_path=tmp_path / "identity.json")
        mock_brain = NexusBrain(settings=settings, identity=id_mgr)

        with TestClient(app) as client:
            app.state.brain = mock_brain

            # Add alias
            add_resp = client.post("/api/identity/aliases?alias=Ari")
            assert add_resp.status_code == 200
            assert "Ari" in add_resp.json()["aliases"]

            # Duplicate alias returns 409
            dup_resp = client.post("/api/identity/aliases?alias=Ari")
            assert dup_resp.status_code == 409

            # Delete alias
            del_resp = client.delete("/api/identity/aliases/Ari")
            assert del_resp.status_code == 200
            assert "Ari" not in del_resp.json()["aliases"]

    def test_wake_word_detect_endpoint(self, tmp_path: Path):
        settings = NexusSettings()
        app = create_app(settings)
        id_mgr = IdentityManager(storage_path=tmp_path / "identity.json")
        mock_brain = NexusBrain(settings=settings, identity=id_mgr)

        with TestClient(app) as client:
            app.state.brain = mock_brain
            resp = client.post("/api/wake-word/detect", json={"text": "Hey Nexus, open Chrome"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["matched"] is True
            assert data["wake_word"] == "NEXUS"
            assert data["prefix"] == "hey"
            assert data["command"] == "open Chrome"


# ===========================================================================
# 6. Identity CLI Helper Tests
# ===========================================================================


class TestIdentityCLI:
    """Tests for CLI identity commands."""

    def test_print_identity_no_crash(self, tmp_path: Path):
        from nexus.cli import _print_identity

        settings = NexusSettings()
        id_mgr = IdentityManager(storage_path=tmp_path / "identity.json")
        brain = NexusBrain(settings=settings, identity=id_mgr)
        # Should execute cleanly without raising exceptions
        _print_identity(brain)
