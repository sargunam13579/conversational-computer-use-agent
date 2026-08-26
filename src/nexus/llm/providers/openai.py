"""
NEXUS LLM Provider — OpenAI.

Implements the BaseLLMProvider interface using the OpenAI Python SDK.
"""

from __future__ import annotations

import json
from typing import Any

from nexus.llm.providers.base import (
    BaseLLMProvider,
    LLMMessage,
    LLMResponse,
    ToolCallRequest,
    ToolSchema,
)
from nexus.utils.logging import get_logger

log = get_logger("llm.openai")


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM provider (GPT-4o, GPT-4o-mini, etc.)."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: Any = None

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    def _ensure_client(self) -> Any:
        """Lazily initialize the OpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str,
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate a response using OpenAI."""
        client = self._ensure_client()

        # Convert messages
        oai_messages = self._convert_messages(messages)

        # Build kwargs
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": oai_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            kwargs["tools"] = self.format_tool_schemas(tools)
            kwargs["tool_choice"] = "auto"

        try:
            response = await client.chat.completions.create(**kwargs)
            return self._parse_response(response, model)

        except Exception as e:
            log.error("OpenAI API error: %s", e)
            return LLMResponse(
                content=f"Error communicating with OpenAI: {e}",
                finish_reason="error",
                model=model,
            )

    def _convert_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Convert LLMMessages to OpenAI format."""
        oai_messages = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role}

            if msg.role == "tool":
                entry["content"] = msg.content
                entry["tool_call_id"] = msg.tool_call_id or ""
            elif msg.images:
                # Vision: multi-part content
                content_parts: list[dict[str, Any]] = []
                if msg.content:
                    content_parts.append({"type": "text", "text": msg.content})
                for img in msg.images:
                    content_parts.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": img},
                        }
                    )
                entry["content"] = content_parts
            else:
                entry["content"] = msg.content

            oai_messages.append(entry)
        return oai_messages

    def _parse_response(self, response: Any, model: str) -> LLMResponse:
        """Parse an OpenAI response into our LLMResponse format."""
        choice = response.choices[0]
        message = choice.message
        tool_calls = []

        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    ToolCallRequest(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments),
                    )
                )

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else choice.finish_reason or "stop",
            model=model,
            usage=usage,
        )

    async def check_availability(self) -> bool:
        """Check if OpenAI is available."""
        if not self._api_key:
            return False
        try:
            self._ensure_client()
            return True
        except Exception as e:
            log.warning("OpenAI not available: %s", e)
            return False
