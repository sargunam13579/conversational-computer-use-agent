"""
Comprehensive Test Suite for Phase 7 — NEXUS Reliable Memory & Context System.

Tests:
1. MemoryRecord & MemoryCategory models
2. MemoryPrivacyFilter (sensitive credential redaction)
3. MemoryStorage (CRUD, persistence, search, tag filters, category isolation)
4. ContextResolver (anaphora/deixis resolution for 'this', 'it', 'my Java project')
5. MemoryManager & Auto-Learning (preference extraction from natural conversation)
6. LLM Memory Tools Suite (store, recall, search, delete, clear, settings)
7. FastAPI Memory Endpoints (/api/memory/*)
8. NexusBrain integration
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from nexus.api.app import create_app
from nexus.core.brain import NexusBrain
from nexus.memory.context_resolver import ContextResolver
from nexus.memory.manager import MemoryManager
from nexus.memory.privacy import MemoryPrivacyFilter
from nexus.memory.storage import MemoryStorage
from nexus.memory.types import MemoryCategory, MemoryRecord, PrivacyLevel
from nexus.tools.memory.memory_tools import (
    ClearMemoryTool,
    DeleteMemoryTool,
    ManageMemorySettingsTool,
    RecallMemoryTool,
    SearchMemoryTool,
    StoreMemoryTool,
    get_memory_tools,
)

# ===========================================================================
# 1. MEMORY DATA TYPES TESTS
# ===========================================================================


class TestMemoryTypes:
    """Tests for record schemas and category enums."""

    def test_memory_record_serialization(self):
        rec = MemoryRecord(
            key="ide_theme",
            value="catppuccin_mocha",
            category=MemoryCategory.USER_PREFERENCE,
            tags=["editor", "theme"],
            privacy_level=PrivacyLevel.PRIVATE,
        )

        d = rec.to_dict()
        assert d["key"] == "ide_theme"
        assert d["value"] == "catppuccin_mocha"
        assert d["category"] == "user_preference"
        assert d["tags"] == ["editor", "theme"]

        reconstructed = MemoryRecord.from_dict(d)
        assert reconstructed.id == rec.id
        assert reconstructed.category == MemoryCategory.USER_PREFERENCE
        assert reconstructed.key == rec.key
        assert reconstructed.value == rec.value


# ===========================================================================
# 2. PRIVACY & SENSITIVE DATA REDACTION TESTS
# ===========================================================================


class TestMemoryPrivacyFilter:
    """Tests for redacting passwords, API keys, and sensitive tokens."""

    def test_sensitive_data_detection(self):
        filter_ = MemoryPrivacyFilter()

        assert filter_.contains_sensitive_data("Normal user preference note") is False
        assert (
            filter_.contains_sensitive_data("My key is sk-abcdef1234567890abcdef1234567890") is True
        )
        assert filter_.contains_sensitive_data("ghp_1234567890abcdefghijklmnopqrstuvwxyz12") is True
        assert filter_.contains_sensitive_data("password = SuperSecret123") is True

    def test_sensitive_data_sanitization(self):
        filter_ = MemoryPrivacyFilter()

        text = "API Key: sk-1234567890abcdef1234567890, password: SecretPassword99"
        clean = filter_.sanitize(text)

        assert "sk-1234567890" not in clean
        assert "SecretPassword99" not in clean
        assert "[OPENAI_API_KEY_REDACTED]" in clean or "[REDACTED]" in clean

    def test_nested_value_sanitization(self):
        filter_ = MemoryPrivacyFilter()
        payload = {
            "token": "ghp_1234567890abcdefghijklmnopqrstuvwxyz12",
            "notes": ["password = mypassword123", "normal note"],
        }
        sanitized = filter_.sanitize_value(payload)

        assert isinstance(sanitized, dict)
        assert "ghp_" not in sanitized["token"]
        assert "mypassword123" not in sanitized["notes"][0]
        assert sanitized["notes"][1] == "normal note"


# ===========================================================================
# 3. MEMORY STORAGE ENGINE TESTS
# ===========================================================================


class TestMemoryStorage:
    """Tests for persistent storage, CRUD, search, and category listing."""

    @pytest.mark.asyncio
    async def test_crud_and_persistence(self, tmp_path: Path):
        file_path = tmp_path / "test_memory.json"
        storage = MemoryStorage(storage_path=file_path)

        # 1. Store
        rec = await storage.store(
            key="java_projects_dir",
            value="D:/Projects",
            category=MemoryCategory.USER_PREFERENCE,
            tags=["java", "code"],
        )
        assert rec is not None
        assert rec.key == "java_projects_dir"
        assert rec.value == "D:/Projects"
        assert file_path.exists()

        # 2. Get by ID & find by key
        found = await storage.get(rec.id)
        assert found is not None
        assert found.value == "D:/Projects"

        by_key = await storage.find_by_key("java_projects_dir")
        assert by_key is not None
        assert by_key.id == rec.id

        # 3. Update
        updated = await storage.store(
            key="java_projects_dir",
            value="E:/JavaWorkspace",
            category=MemoryCategory.USER_PREFERENCE,
        )
        assert updated is not None
        assert updated.id == rec.id
        assert updated.value == "E:/JavaWorkspace"

        # 4. Search
        search_res = await storage.search(query="workspace")
        assert len(search_res) == 1
        assert search_res[0].key == "java_projects_dir"

        # 5. Delete
        deleted = await storage.delete("java_projects_dir")
        assert deleted is True
        assert await storage.find_by_key("java_projects_dir") is None

    @pytest.mark.asyncio
    async def test_category_isolation_and_clearing(self, tmp_path: Path):
        storage = MemoryStorage(storage_path=tmp_path / "mem.json")

        await storage.store("pref1", "val1", category=MemoryCategory.USER_PREFERENCE)
        await storage.store("app1", "val2", category=MemoryCategory.APP_PREFERENCE)
        await storage.store("info1", "val3", category=MemoryCategory.USER_DEFINED_INFO)

        prefs = await storage.list_by_category(MemoryCategory.USER_PREFERENCE)
        assert len(prefs) == 1
        assert prefs[0].key == "pref1"

        # Clear only user preferences
        cleared_count = await storage.clear(category=MemoryCategory.USER_PREFERENCE)
        assert cleared_count == 1
        assert len(await storage.list_by_category(MemoryCategory.USER_PREFERENCE)) == 0
        assert len(await storage.list_by_category(MemoryCategory.APP_PREFERENCE)) == 1

        # Clear all
        total_cleared = await storage.clear()
        assert total_cleared == 2
        stats = await storage.get_stats()
        assert stats["total_records"] == 0


# ===========================================================================
# 4. CONTEXT & REFERENCE RESOLUTION ENGINE TESTS
# ===========================================================================


class TestContextResolver:
    """Tests for resolving anaphora and domain aliases."""

    @pytest.mark.asyncio
    async def test_project_alias_resolution(self, tmp_path: Path):
        storage = MemoryStorage(storage_path=tmp_path / "mem.json")
        await storage.store(
            key="java_projects_dir",
            value="D:/Projects",
            category=MemoryCategory.USER_PREFERENCE,
        )

        resolver = ContextResolver(storage=storage)

        # "Open my Java project" -> resolves to D:/Projects
        res = await resolver.resolve_reference("Open my Java project")
        assert res.get("target_path") == "D:/Projects"
        assert res.get("reference_type") == "project_directory"

    @pytest.mark.asyncio
    async def test_pronoun_resolution(self, tmp_path: Path):
        storage = MemoryStorage(storage_path=tmp_path / "mem.json")
        resolver = ContextResolver(storage=storage)

        # Set active context
        resolver.update_state(
            last_downloaded_file="C:/Users/user/Downloads/interview_questions.pdf",
            last_copied_text="Python AsyncIO Architecture",
            last_mentioned_url="https://github.com/nexus/nexus-ai",
        )

        # 1. "Open the file" / "Move that file"
        res_file = await resolver.resolve_reference("Move the file to Documents")
        assert res_file.get("target_file") == "C:/Users/user/Downloads/interview_questions.pdf"

        # 2. "Search this"
        res_search = await resolver.resolve_reference("Search this on Google")
        assert res_search.get("search_query") == "Python AsyncIO Architecture"

        # 3. "Open that link"
        res_link = await resolver.resolve_reference("Open that link")
        assert res_link.get("target_url") == "https://github.com/nexus/nexus-ai"

    @pytest.mark.asyncio
    async def test_context_prompt_building(self, tmp_path: Path):
        storage = MemoryStorage(storage_path=tmp_path / "mem.json")
        await storage.store("editor", "VS Code", category=MemoryCategory.USER_PREFERENCE)
        await storage.store("project_name", "NEXUS AI", category=MemoryCategory.USER_DEFINED_INFO)

        resolver = ContextResolver(storage=storage)
        resolver.update_state(active_task_description="Build Phase 7 Memory System")

        prompt_str = await resolver.build_context_prompt()
        assert "VS Code" in prompt_str
        assert "NEXUS AI" in prompt_str
        assert "Build Phase 7 Memory System" in prompt_str


# ===========================================================================
# 5. MEMORY MANAGER & AUTO-LEARNING TESTS
# ===========================================================================


class TestMemoryManager:
    """Tests for learning preferences from natural conversational patterns."""

    @pytest.mark.asyncio
    async def test_auto_learning_from_conversation(self, tmp_path: Path):
        storage = MemoryStorage(storage_path=tmp_path / "mem.json")
        manager = MemoryManager(storage=storage)

        # Example 1: Project path declaration
        msg1 = "My Java projects are normally inside D:/Projects"
        rec1 = await manager.auto_learn_from_message(msg1)
        assert rec1 is not None
        assert rec1.key == "java_projects_dir"
        assert rec1.value == "D:/Projects"
        assert rec1.category == MemoryCategory.USER_PREFERENCE

        # Example 2: Explicit remember note
        msg2 = "Remember that my favorite model is Claude 3.7 Sonnet"
        rec2 = await manager.auto_learn_from_message(msg2)
        assert rec2 is not None
        assert rec2.key == "favorite_model"
        assert "Claude 3.7" in rec2.value

        # Example 3: Default application
        msg3 = "Set my default browser to Brave"
        rec3 = await manager.auto_learn_from_message(msg3)
        assert rec3 is not None
        assert rec3.key == "default_browser"
        assert rec3.value == "Brave"
        assert rec3.category == MemoryCategory.APP_PREFERENCE


# ===========================================================================
# 6. LLM MEMORY TOOLS SUITE TESTS
# ===========================================================================


class TestMemoryToolsSuite:
    """Tests for all LLM memory tools."""

    @pytest.mark.asyncio
    async def test_store_recall_and_search_tools(self, tmp_path: Path):
        storage = MemoryStorage(storage_path=tmp_path / "mem.json")
        manager = MemoryManager(storage=storage)

        store_tool = StoreMemoryTool(manager=manager)
        assert store_tool.name == "store_memory"

        # 1. Store
        res_store = await store_tool.execute(
            key="python_version",
            value="3.12",
            category="user_preference",
            tags=["python", "runtime"],
        )
        assert res_store.success is True
        assert "3.12" in res_store.output

        # 2. Recall
        recall_tool = RecallMemoryTool(manager=manager)
        res_recall = await recall_tool.execute(key="python_version")
        assert res_recall.success is True
        assert "3.12" in res_recall.output

        # 3. Search
        search_tool = SearchMemoryTool(manager=manager)
        res_search = await search_tool.execute(query="python")
        assert res_search.success is True
        assert res_search.data["count"] == 1

        # 4. Settings
        settings_tool = ManageMemorySettingsTool(manager=manager)
        res_status = await settings_tool.execute(action="status")
        assert res_status.success is True
        assert "Total Records" in res_status.output

        # 5. Delete
        del_tool = DeleteMemoryTool(manager=manager)
        res_del = await del_tool.execute(target="python_version")
        assert res_del.success is True

        # 6. Clear
        clear_tool = ClearMemoryTool(manager=manager)
        res_clear = await clear_tool.execute()
        assert res_clear.success is True

    def test_factory(self):
        tools = get_memory_tools()
        assert len(tools) == 6


# ===========================================================================
# 7. FASTAPI MEMORY ENDPOINTS TESTS
# ===========================================================================


class TestFastAPIMemoryRoutes:
    """Tests for /api/memory/* endpoints."""

    @pytest.mark.asyncio
    async def test_rest_endpoints(self):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Create memory
            res_create = await ac.post(
                "/api/memory/",
                json={
                    "key": "test_endpoint_key",
                    "value": "endpoint_val",
                    "category": "user_defined_info",
                    "tags": ["test"],
                },
            )
            assert res_create.status_code == 200
            mem_id = res_create.json()["memory"]["id"]

            # 2. Get by ID
            res_get = await ac.get(f"/api/memory/{mem_id}")
            assert res_get.status_code == 200
            assert res_get.json()["memory"]["key"] == "test_endpoint_key"

            # 3. Search
            res_search = await ac.get("/api/memory/search?query=endpoint")
            assert res_search.status_code == 200
            assert res_search.json()["count"] >= 1

            # 4. Context resolve
            res_resolve = await ac.post(
                "/api/memory/context/resolve",
                json={"user_input": "Open my Java project"},
            )
            assert res_resolve.status_code == 200

            # 5. Delete
            res_del = await ac.delete(f"/api/memory/{mem_id}")
            assert res_del.status_code == 200
            assert res_del.json()["success"] is True


# ===========================================================================
# 8. NEXUS BRAIN MEMORY INTEGRATION TESTS
# ===========================================================================


class TestNexusBrainMemoryIntegration:
    """Tests for Brain auto-learning during dialogue processing."""

    @pytest.mark.asyncio
    async def test_brain_auto_learn_on_process(self):
        brain = NexusBrain()
        assert brain.memory_manager is not None

        # Patch orchestrator so no live LLM call is attempted
        from unittest.mock import AsyncMock, patch

        with patch.object(
            brain._orchestrator,
            "process",
            new_callable=AsyncMock,
            return_value="Remembered your preference.",
        ):
            # Process a message containing a preference declaration
            pref_input = "My Java projects are normally inside D:/Projects"
            res = await brain.process(pref_input)
            assert res == "Remembered your preference."

            # Verify preference was captured in memory
            recalled = await brain.memory_manager.recall_memory("java_projects_dir")
            assert recalled is not None
            assert recalled.value == "D:/Projects"
