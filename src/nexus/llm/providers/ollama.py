"""
NEXUS LLM Provider — Ollama (Local).

Implements the BaseLLMProvider interface for local models via Ollama.
This is the offline/privacy fallback provider.
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

log = get_logger("llm.ollama")


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider (Llama 3, Phi-3, Mistral, etc.)."""

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self._base_url = base_url
        self._client: Any = None

    @property
    def provider_name(self) -> str:
        return "Ollama (Local)"

    def _ensure_client(self) -> Any:
        """Lazily initialize the Ollama client."""
        if self._client is None:
            from ollama import AsyncClient

            self._client = AsyncClient(host=self._base_url)
        return self._client

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str,
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate a response using a local Ollama model."""
        client = self._ensure_client()

        # Convert messages to Ollama format
        ollama_messages = [{"role": msg.role, "content": msg.content} for msg in messages]

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": ollama_messages,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        # Ollama supports tools for some models
        if tools:
            kwargs["tools"] = self.format_tool_schemas(tools)

        try:
            response = await client.chat(**kwargs)
            return self._parse_response(response, model)

        except Exception as e:
            log.error("Ollama error: %s", e)
            return LLMResponse(
                content=f"Error communicating with Ollama: {e}",
                finish_reason="error",
                model=model,
            )

    def _parse_response(self, response: Any, model: str) -> LLMResponse:
        """Parse an Ollama response into our LLMResponse format."""
        message = response.get("message", {})
        content = message.get("content", "")
        tool_calls = []

        # Parse tool calls if present
        if "tool_calls" in message:
            for i, tc in enumerate(message["tool_calls"]):
                func = tc.get("function", {})
                tool_calls.append(
                    ToolCallRequest(
                        id=f"ollama_call_{i}",
                        name=func.get("name", ""),
                        arguments=func.get("arguments", {}),
                    )
                )

        usage = {}
        if "eval_count" in response:
            usage = {
                "prompt_tokens": response.get("prompt_eval_count", 0),
                "completion_tokens": response.get("eval_count", 0),
            }

        return LLMResponse(
            content=content if content else None,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
            model=model,
            usage=usage,
        )

    async def check_availability(self) -> bool:
        """Check if Ollama is running and reachable."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self._base_url}/api/tags", timeout=0.5)
                return resp.status_code == 200
        except Exception:
            return False
