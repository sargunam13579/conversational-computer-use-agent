"""
NEXUS Tool — Base Interface.

Every tool (action) in NEXUS must extend this base class. Tools are the
atomic units of device control — the LLM calls them via function calling.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RiskLevel(StrEnum):
    """Risk classification for tool actions."""

    LOW = "low"  # Read-only, non-destructive (e.g., get_time)
    MEDIUM = "medium"  # Modifying but recoverable (e.g., move_file)
    HIGH = "high"  # Destructive or external (e.g., delete_file, send_email)
    CRITICAL = "critical"  # Irreversible or dangerous (e.g., shutdown, format_drive)


class TargetDevice(StrEnum):
    """Which device a tool targets."""

    LAPTOP = "laptop"
    ANDROID = "android"
    LOCAL = "local"
    ANY = "any"  # Device-agnostic (e.g., get_time, remember)


@dataclass
class ToolResult:
    """The result of a tool execution."""

    success: bool
    output: str  # Human-readable result for the LLM
    data: dict[str, Any] = field(default_factory=dict)  # Structured data
    error: str | None = None  # Error message if failed

    @classmethod
    def ok(cls, output: str, **data: Any) -> ToolResult:
        """Create a successful result."""
        return cls(success=True, output=output, data=data)

    @classmethod
    def fail(cls, error: str, **data: Any) -> ToolResult:
        """Create a failed result."""
        return cls(success=False, output=f"Error: {error}", error=error, data=data)


class BaseTool(ABC):
    """
    Abstract base class for all NEXUS tools.

    Subclasses must implement:
      - name, description, parameters (class-level or properties)
      - execute() — the actual tool logic

    Optionally override:
      - validate() — pre-execution validation
      - rollback() — undo the action
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier (e.g., 'open_app', 'delete_file')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for the LLM to understand what this tool does."""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema describing the tool's input parameters."""
        ...

    @property
    def category(self) -> str:
        """Tool category for grouping (e.g., 'system', 'files', 'web')."""
        return "general"

    @property
    def risk_level(self) -> RiskLevel:
        """Risk classification for permission checks."""
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        """Which device this tool operates on."""
        return TargetDevice.ANY

    @property
    def requires_confirmation(self) -> bool:
        """Whether this tool requires explicit user confirmation."""
        return self.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    @abstractmethod
    async def execute(self, *args: Any, **kwargs: Any) -> ToolResult:
        """
        Execute the tool with the given parameters.

        Args:
            *args: Positional parameters.
            **kwargs: Tool-specific keyword parameters matching the JSON schema.

        Returns:
            A ToolResult indicating success/failure and output.
        """
        ...

    async def validate(self, *args: Any, **kwargs: Any) -> tuple[bool, str]:
        """
        Validate parameters before execution.

        Returns:
            A tuple of (is_valid, error_message).
        """
        return True, ""

    async def rollback(self, *args: Any, **kwargs: Any) -> ToolResult:
        """
        Attempt to undo the action. Override in tools that support undo.

        Returns:
            A ToolResult indicating success/failure of the rollback.
        """
        return ToolResult.fail("Rollback not supported for this tool")

    def to_schema(self) -> dict[str, Any]:
        """Convert this tool to a schema dict for the LLM."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def __repr__(self) -> str:
        return f"<Tool:{self.name} ({self.category}, risk={self.risk_level.value})>"
