"""
NEXUS Memory Tools for LLM & Agents.

Exposes memory recall, persistence, search, deletion, clearing, and privacy toggles.
"""

from __future__ import annotations

import contextlib
from typing import Any

from nexus.memory.manager import MemoryManager
from nexus.memory.types import MemoryCategory
from nexus.tools.base import BaseTool, RiskLevel, TargetDevice, ToolResult
from nexus.utils.logging import get_logger

log = get_logger("tools.memory")

# Shared default manager
_default_memory_manager = MemoryManager()


# ---------------------------------------------------------------------------
# Store Memory Tool
# ---------------------------------------------------------------------------


class StoreMemoryTool(BaseTool):
    """Store or update user preference, fact, project path, or note in memory."""

    def __init__(self, manager: MemoryManager | None = None) -> None:
        self._manager = manager or _default_memory_manager

    @property
    def name(self) -> str:
        return "store_memory"

    @property
    def description(self) -> str:
        return (
            "Store or update a memory item (e.g. user project path, coding style preference, "
            "important note, default app) for long-term retention."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": (
                        "Identifier key for the memory "
                        "(e.g. 'java_projects_dir', 'email', 'theme')."
                    ),
                },
                "value": {
                    "type": "string",
                    "description": (
                        "Value or information to store (e.g. 'D:/Projects', 'dark_mode')."
                    ),
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "user_preference",
                        "user_defined_info",
                        "app_preference",
                        "device_memory",
                        "current_task",
                        "conversation",
                    ],
                    "description": "Memory category (default: 'user_defined_info').",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of searchable tags.",
                },
            },
            "required": ["key", "value"],
        }

    @property
    def category(self) -> str:
        return "memory"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LOCAL

    async def execute(
        self,
        key: str = "",
        value: Any = None,
        category: str = "user_defined_info",
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        if not key or value is None:
            return ToolResult.fail("Both 'key' and 'value' parameters are required.")

        try:
            cat_enum = MemoryCategory(category)
        except ValueError:
            cat_enum = MemoryCategory.USER_DEFINED_INFO

        record = await self._manager.store_memory(
            key=key,
            value=value,
            category=cat_enum,
            tags=tags,
        )

        if not record:
            return ToolResult.fail("Memory storage is currently disabled.")

        return ToolResult.ok(
            f"Stored memory [{record.category.value}] '{record.key}': {record.value}",
            id=record.id,
            key=record.key,
            value=record.value,
            category=record.category.value,
        )


# ---------------------------------------------------------------------------
# Recall Memory Tool
# ---------------------------------------------------------------------------


class RecallMemoryTool(BaseTool):
    """Retrieve a stored memory item by key."""

    def __init__(self, manager: MemoryManager | None = None) -> None:
        self._manager = manager or _default_memory_manager

    @property
    def name(self) -> str:
        return "recall_memory"

    @property
    def description(self) -> str:
        return (
            "Recall a previously stored memory item "
            "(user preference, project directory, note) by key."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Key or topic to look up (e.g. 'java_projects_dir', 'email').",
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "user_preference",
                        "user_defined_info",
                        "app_preference",
                        "device_memory",
                        "current_task",
                        "conversation",
                    ],
                    "description": "Optional category filter.",
                },
            },
            "required": ["key"],
        }

    @property
    def category(self) -> str:
        return "memory"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LOCAL

    async def execute(
        self,
        key: str = "",
        category: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        if not key:
            return ToolResult.fail("Parameter 'key' is required.")

        cat_enum = None
        if category:
            with contextlib.suppress(ValueError):
                cat_enum = MemoryCategory(category)

        record = await self._manager.recall_memory(key=key, category=cat_enum)
        if record:
            return ToolResult.ok(
                f"Found memory [{record.category.value}] '{record.key}': {record.value}",
                id=record.id,
                key=record.key,
                value=record.value,
                category=record.category.value,
            )

        # Fallback to search
        search_results = await self._manager.search_memory(query=key, limit=3)
        if search_results:
            top = search_results[0]
            return ToolResult.ok(
                f"Found matching memory [{top.category.value}] '{top.key}': {top.value}",
                id=top.id,
                key=top.key,
                value=top.value,
                category=top.category.value,
            )

        return ToolResult.fail(f"No stored memory found for key '{key}'.")


# ---------------------------------------------------------------------------
# Search Memory Tool
# ---------------------------------------------------------------------------


class SearchMemoryTool(BaseTool):
    """Search across all stored memories by keyword, tags, or category."""

    def __init__(self, manager: MemoryManager | None = None) -> None:
        self._manager = manager or _default_memory_manager

    @property
    def name(self) -> str:
        return "search_memory"

    @property
    def description(self) -> str:
        return "Search across all stored memories using keyword query, category, or tags."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keywords to search for in memory keys, values, and tags.",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 10).",
                },
            },
            "required": [],
        }

    @property
    def category(self) -> str:
        return "memory"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LOCAL

    async def execute(
        self,
        query: str = "",
        category: str | None = None,
        limit: int = 10,
        **kwargs: Any,
    ) -> ToolResult:
        cat_enum = None
        if category:
            with contextlib.suppress(ValueError):
                cat_enum = MemoryCategory(category)

        results = await self._manager.search_memory(
            query=query,
            category=cat_enum,
            limit=limit,
        )

        if not results:
            return ToolResult.ok("No matching memories found.", count=0, memories=[])

        lines = [f"Found {len(results)} memory record(s):"]
        for r in results:
            lines.append(f"- [{r.category.value}] {r.key} = {r.value}")

        return ToolResult.ok(
            "\n".join(lines),
            count=len(results),
            memories=[r.to_dict() for r in results],
        )


# ---------------------------------------------------------------------------
# Delete Memory Tool
# ---------------------------------------------------------------------------


class DeleteMemoryTool(BaseTool):
    """Delete a specific memory item by key or ID."""

    def __init__(self, manager: MemoryManager | None = None) -> None:
        self._manager = manager or _default_memory_manager

    @property
    def name(self) -> str:
        return "delete_memory"

    @property
    def description(self) -> str:
        return "Delete a specific memory record by its key or unique ID."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "The memory key or ID to delete.",
                },
            },
            "required": ["target"],
        }

    @property
    def category(self) -> str:
        return "memory"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LOCAL

    async def execute(self, target: str = "", **kwargs: Any) -> ToolResult:
        if not target:
            return ToolResult.fail("Parameter 'target' is required.")

        deleted = await self._manager.delete_memory(target)
        if deleted:
            return ToolResult.ok(f"Successfully deleted memory '{target}'.")
        return ToolResult.fail(f"Could not find memory '{target}' to delete.")


# ---------------------------------------------------------------------------
# Clear Memory Tool
# ---------------------------------------------------------------------------


class ClearMemoryTool(BaseTool):
    """Clear memories with confirmation."""

    def __init__(self, manager: MemoryManager | None = None) -> None:
        self._manager = manager or _default_memory_manager

    @property
    def name(self) -> str:
        return "clear_memory"

    @property
    def description(self) -> str:
        return "Clear all stored memory records or records belonging to a specific category."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category to clear. If omitted, all memory is cleared.",
                },
            },
            "required": [],
        }

    @property
    def category(self) -> str:
        return "memory"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LOCAL

    async def execute(self, category: str | None = None, **kwargs: Any) -> ToolResult:
        cat_enum = None
        if category:
            with contextlib.suppress(ValueError):
                cat_enum = MemoryCategory(category)

        count = await self._manager.clear_memory(category=cat_enum)
        return ToolResult.ok(
            f"Cleared {count} memory record(s){f' in category {category}' if category else ''}.",
            cleared_count=count,
        )


# ---------------------------------------------------------------------------
# Manage Memory Settings Tool
# ---------------------------------------------------------------------------


class ManageMemorySettingsTool(BaseTool):
    """View or update memory privacy and operational settings."""

    def __init__(self, manager: MemoryManager | None = None) -> None:
        self._manager = manager or _default_memory_manager

    @property
    def name(self) -> str:
        return "manage_memory_settings"

    @property
    def description(self) -> str:
        return "View memory system statistics or enable/disable long-term memory."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "enable", "disable"],
                    "description": "Action to perform on memory settings.",
                },
            },
            "required": ["action"],
        }

    @property
    def category(self) -> str:
        return "memory"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LOCAL

    async def execute(self, action: str = "status", **kwargs: Any) -> ToolResult:
        act = action.lower().strip()
        if act == "enable":
            self._manager.set_enabled(True)
            return ToolResult.ok("Memory retention enabled.")
        elif act == "disable":
            self._manager.set_enabled(False)
            return ToolResult.ok("Memory retention disabled.")

        stats = await self._manager.get_stats()
        return ToolResult.ok(
            f"Memory System Status: {'Enabled' if stats['enabled'] else 'Disabled'}\n"
            f"Total Records: {stats['total_records']}\n"
            f"Categories: {stats['categories']}",
            stats=stats,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_memory_tools(manager: MemoryManager | None = None) -> list[BaseTool]:
    """Return all memory automation tools."""
    mgr = manager or _default_memory_manager
    return [
        StoreMemoryTool(manager=mgr),
        RecallMemoryTool(manager=mgr),
        SearchMemoryTool(manager=mgr),
        DeleteMemoryTool(manager=mgr),
        ClearMemoryTool(manager=mgr),
        ManageMemorySettingsTool(manager=mgr),
    ]
