"""
NEXUS LLM Provider — Anthropic (Claude).

Implements the BaseLLMProvider interface using the Anthropic Python SDK.
"""

from __future__ import annotations

from typing import Any

from nexus.llm.providers.base import (
    BaseLLMProvider,
    LLMMessage,
    LLMResponse,
    ToolCallRequest,
    ToolSchema,
)
from nexus.utils.logging import get_logger

log = get_logger("llm.anthropic")


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude LLM provider."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: Any = None

    @property
    def provider_name(self) -> str:
        return "Anthropic"

    def _ensure_client(self) -> Any:
        """Lazily initialize the Anthropic client."""
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str,
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate a response using Anthropic Claude."""
        client = self._ensure_client()

        # Extract system message
        system_content = ""
        conversation = []
        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
            else:
                conversation.append(self._convert_message(msg))

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": conversation,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if system_content:
            kwargs["system"] = system_content

        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        try:
            response = await client.messages.create(**kwargs)
            return self._parse_response(response, model)

        except Exception as e:
            log.error("Anthropic API error: %s", e)
            return LLMResponse(
                content=f"Error communicating with Anthropic: {e}",
                finish_reason="error",
                model=model,
            )

    def _convert_message(self, msg: LLMMessage) -> dict[str, Any]:
        """Convert a single LLMMessage to Anthropic format."""
        if msg.role == "tool":
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id or "",
                        "content": msg.content,
                    }
                ],
            }

        content: list[dict[str, Any]] = []
        if msg.content:
            content.append({"type": "text", "text": msg.content})

        if msg.images:
            for img in msg.images:
                if img.startswith("data:"):
                    media_type, data = img.split(";base64,", 1)
                    media_type = media_type.replace("data:", "")
                    content.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": data,
                            },
                        }
                    )

        role = "assistant" if msg.role == "assistant" else "user"
        return {"role": role, "content": content}

    def _convert_tools(self, tools: list[ToolSchema]) -> list[dict[str, Any]]:
        """Convert ToolSchemas to Anthropic tool format."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in tools
        ]

    def _parse_response(self, response: Any, model: str) -> LLMResponse:
        """Parse an Anthropic response into our LLMResponse format."""
        tool_calls = []
        content_parts = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCallRequest(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    )
                )

        content = "\n".join(content_parts) if content_parts else None
        finish_reason = "tool_calls" if tool_calls else "stop"

        usage = {
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
        }

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            model=model,
            usage=usage,
        )

    async def check_availability(self) -> bool:
        """Check if Anthropic is available."""
        if not self._api_key:
            return False
        try:
            self._ensure_client()
            return True
        except Exception as e:
            log.warning("Anthropic not available: %s", e)
            return False
