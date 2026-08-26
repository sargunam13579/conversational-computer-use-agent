"""
NEXUS Tool Registry.

Discovers, registers, and manages all available tools. Provides tool lookup
by name and generates schemas for the LLM's function calling interface.
"""

from __future__ import annotations

from nexus.llm.providers.base import ToolSchema
from nexus.tools.base import BaseTool, TargetDevice
from nexus.utils.logging import get_logger

log = get_logger("tools.registry")


class ToolRegistry:
    """
    Central registry for all NEXUS tools.

    Tools are registered at startup and looked up by name when the LLM
    requests a function call.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """
        Register a tool in the registry.

        Raises ValueError if a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool
        log.debug("Registered tool: %s (%s)", tool.name, tool.category)

    def register_many(self, tools: list[BaseTool]) -> None:
        """Register multiple tools at once."""
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> BaseTool | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def get_or_raise(self, name: str) -> BaseTool:
        """Look up a tool by name, raising KeyError if not found."""
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not found in registry")
        return tool

    def list_tools(
        self,
        category: str | None = None,
        target_device: TargetDevice | None = None,
    ) -> list[BaseTool]:
        """
        List all registered tools, optionally filtered.

        Args:
            category: Filter by tool category (e.g., 'system', 'files').
            target_device: Filter by target device.
        """
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        if target_device:
            tools = [
                t
                for t in tools
                if t.target_device == target_device or t.target_device == TargetDevice.ANY
            ]
        return tools

    def get_schemas(
        self,
        category: str | None = None,
        target_device: TargetDevice | None = None,
    ) -> list[ToolSchema]:
        """
        Generate LLM-compatible tool schemas for function calling.

        Args:
            category: Filter by category.
            target_device: Filter by target device.

        Returns:
            List of ToolSchema objects ready for the LLM.
        """
        tools = self.list_tools(category=category, target_device=target_device)
        return [
            ToolSchema(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters,
            )
            for tool in tools
        ]

    @property
    def tool_names(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    @property
    def count(self) -> int:
        """Number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __repr__(self) -> str:
        return f"<ToolRegistry(tools={self.count})>"
