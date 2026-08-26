"""Tests for the NEXUS tool system — registry, executor, and starter tools."""

from __future__ import annotations

import pytest

from nexus.tools.base import RiskLevel, TargetDevice
from nexus.tools.executor import ToolExecutor
from nexus.tools.registry import ToolRegistry
from nexus.tools.system.basic import (
    GetCurrentTimeTool,
    GetSystemInfoTool,
    OpenApplicationTool,
    SearchWebTool,
    SetVolumeTool,
    get_starter_tools,
)

# ---------------------------------------------------------------------------
# Tool Registry Tests
# ---------------------------------------------------------------------------


class TestToolRegistry:
    """Tests for the ToolRegistry."""

    def test_register_tool(self, tool_registry: ToolRegistry):
        tool = GetCurrentTimeTool()
        tool_registry.register(tool)
        assert tool.name in tool_registry
        assert tool_registry.count == 1

    def test_register_duplicate_raises(self, tool_registry: ToolRegistry):
        tool = GetCurrentTimeTool()
        tool_registry.register(tool)
        with pytest.raises(ValueError, match="already registered"):
            tool_registry.register(tool)

    def test_register_many(self, tool_registry: ToolRegistry, starter_tools):
        tool_registry.register_many(starter_tools)
        assert tool_registry.count == len(starter_tools)

    def test_get_tool(self, tool_registry: ToolRegistry):
        tool = GetCurrentTimeTool()
        tool_registry.register(tool)
        found = tool_registry.get("get_current_time")
        assert found is tool

    def test_get_nonexistent(self, tool_registry: ToolRegistry):
        assert tool_registry.get("nonexistent") is None

    def test_get_or_raise(self, tool_registry: ToolRegistry):
        with pytest.raises(KeyError):
            tool_registry.get_or_raise("nonexistent")

    def test_list_tools_by_category(self, tool_registry: ToolRegistry, starter_tools):
        tool_registry.register_many(starter_tools)
        system_tools = tool_registry.list_tools(category="system")
        assert len(system_tools) >= 2  # get_current_time + get_system_info

    def test_get_schemas(self, tool_registry: ToolRegistry, starter_tools):
        tool_registry.register_many(starter_tools)
        schemas = tool_registry.get_schemas()
        assert len(schemas) == len(starter_tools)
        for schema in schemas:
            assert schema.name
            assert schema.description
            assert schema.parameters

    def test_tool_names(self, tool_registry: ToolRegistry, starter_tools):
        tool_registry.register_many(starter_tools)
        names = tool_registry.tool_names
        assert "get_current_time" in names
        assert "get_system_info" in names
        assert "open_application" in names


# ---------------------------------------------------------------------------
# Starter Tool Tests
# ---------------------------------------------------------------------------


class TestStarterTools:
    """Tests for individual starter tools."""

    @pytest.mark.asyncio
    async def test_get_current_time(self):
        tool = GetCurrentTimeTool()
        assert tool.name == "get_current_time"
        assert tool.category == "system"
        assert tool.risk_level == RiskLevel.LOW

        result = await tool.execute()
        assert result.success
        assert "Current time" in result.output

    @pytest.mark.asyncio
    async def test_get_system_info(self):
        tool = GetSystemInfoTool()
        assert tool.name == "get_system_info"

        result = await tool.execute()
        assert result.success
        assert "OS:" in result.output
        assert "CPU:" in result.output
        assert "RAM:" in result.output

    def test_open_application_properties(self):
        tool = OpenApplicationTool()
        assert tool.name == "open_application"
        assert tool.category == "application"
        assert tool.risk_level == RiskLevel.LOW
        assert tool.target_device == TargetDevice.LAPTOP

    def test_search_web_properties(self):
        tool = SearchWebTool()
        assert tool.name == "search_web"
        assert tool.category == "web"

    def test_set_volume_properties(self):
        tool = SetVolumeTool()
        assert tool.name == "set_volume"
        assert tool.target_device == TargetDevice.LAPTOP

    def test_tool_schemas_valid(self, starter_tools):
        """Every starter tool must produce a valid schema."""
        for tool in starter_tools:
            schema = tool.to_schema()
            assert "name" in schema
            assert "description" in schema
            assert "parameters" in schema
            assert schema["parameters"]["type"] == "object"

    def test_get_starter_tools_returns_all(self):
        tools = get_starter_tools()
        assert len(tools) == 6
        names = {t.name for t in tools}
        assert names == {
            "get_current_time",
            "get_system_info",
            "get_weather",
            "open_application",
            "set_volume",
            "search_web",
        }


# ---------------------------------------------------------------------------
# Tool Executor Tests
# ---------------------------------------------------------------------------


class TestToolExecutor:
    """Tests for the ToolExecutor."""

    @pytest.mark.asyncio
    async def test_execute_known_tool(self, tool_registry: ToolRegistry):
        tool_registry.register(GetCurrentTimeTool())
        executor = ToolExecutor(registry=tool_registry, max_retries=0)

        result = await executor.execute("get_current_time", {})
        assert result.success
        assert "Current time" in result.output

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, tool_registry: ToolRegistry):
        executor = ToolExecutor(registry=tool_registry, max_retries=0)

        result = await executor.execute("nonexistent_tool", {})
        assert not result.success
        assert "Unknown tool" in result.output

    @pytest.mark.asyncio
    async def test_execution_count(self, tool_registry: ToolRegistry):
        tool_registry.register(GetCurrentTimeTool())
        executor = ToolExecutor(registry=tool_registry, max_retries=0)

        assert executor.execution_count == 0
        await executor.execute("get_current_time", {})
        assert executor.execution_count == 1
        await executor.execute("get_current_time", {})
        assert executor.execution_count == 2


# ---------------------------------------------------------------------------
# Archive & Window State Tool Tests
# ---------------------------------------------------------------------------


class TestArchiveAndWindowTools:
    """Tests for archive compression, extraction, and window state control."""

    @pytest.mark.asyncio
    async def test_compress_and_extract_archive(self, tmp_path):
        from nexus.tools.system.files import CompressFilesTool, ExtractArchiveTool

        compress_tool = CompressFilesTool()
        extract_tool = ExtractArchiveTool()

        # Create sample files
        file1 = tmp_path / "file1.txt"
        file1.write_text("Hello from archive test")
        file2 = tmp_path / "file2.txt"
        file2.write_text("Second file content")

        archive_dest = tmp_path / "output.zip"

        # Compress
        res = await compress_tool.execute(
            sources=[str(file1), str(file2)],
            destination_archive=str(archive_dest),
        )
        assert res.success
        assert archive_dest.exists()

        # Extract
        extract_dest = tmp_path / "extracted"
        res_extract = await extract_tool.execute(
            archive_path=str(archive_dest),
            destination_dir=str(extract_dest),
        )
        assert res_extract.success
        assert (extract_dest / "file1.txt").exists()
        assert (extract_dest / "file2.txt").exists()
        assert (extract_dest / "file1.txt").read_text() == "Hello from archive test"

    @pytest.mark.asyncio
    async def test_window_state_tool(self):
        from nexus.tools.system.apps import WindowStateTool

        tool = WindowStateTool()
        assert tool.name == "window_state"
        assert tool.risk_level == RiskLevel.LOW

        # Execution with empty name
        res_empty = await tool.execute(app_name="")
        assert not res_empty.success

        # Execution with nonexistent window
        res_nonexistent = await tool.execute(app_name="nonexistent_fake_app_xyz_123", action="minimize")
        assert not res_nonexistent.success

