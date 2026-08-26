"""
NEXUS LLM Provider — Base Interface.

All LLM providers must implement this abstract interface, ensuring the Brain
can swap providers without changing any calling code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ModelTier(StrEnum):
    """Model selection tiers based on task complexity."""

    FAST = "fast"  # Quick, cheap — classification, simple Q&A
    SMART = "smart"  # Complex reasoning, multi-step planning
    VISION = "vision"  # Image/screenshot understanding
    LOCAL = "local"  # Offline fallback


@dataclass
class LLMMessage:
    """A single message in a conversation."""

    role: str  # "system", "user", "assistant", "tool"
    content: str
    name: str | None = None  # Tool name (for tool role)
    tool_call_id: str | None = None  # ID linking tool result to its call
    images: list[str] | None = None  # Base64 or URL images (for vision)


@dataclass
class ToolCallRequest:
    """An LLM-generated request to call a tool."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """The response from an LLM provider."""

    content: str | None = None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str = "stop"  # stop, tool_calls, length, error
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)  # prompt_tokens, completion_tokens

    @property
    def has_tool_calls(self) -> bool:
        """Whether the response contains tool call requests."""
        return len(self.tool_calls) > 0


@dataclass
class ToolSchema:
    """
    Schema for a tool that the LLM can call.

    This is provider-agnostic; each provider converts it to its native format.
    """

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema object


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Each provider (Gemini, OpenAI, Anthropic, Ollama) implements this
    interface, allowing the model router to swap between them seamlessly.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""
        ...

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        model: str,
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            messages: Conversation history.
            model: The specific model name to use.
            tools: Optional list of tool schemas for function calling.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the response.

        Returns:
            An LLMResponse with content and/or tool calls.
        """
        ...

    @abstractmethod
    async def check_availability(self) -> bool:
        """Check if the provider is available and configured."""
        ...

    def format_tool_schemas(self, tools: list[ToolSchema]) -> list[dict[str, Any]]:
        """
        Convert generic tool schemas to provider-specific format.

        Default implementation returns the generic format.
        Override in subclasses for provider-specific formatting.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]
