"""
NEXUS LLM Provider — Google Gemini.

Implements the BaseLLMProvider interface using the Google GenAI SDK.
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

log = get_logger("llm.gemini")


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: Any = None

    @property
    def provider_name(self) -> str:
        return "Google Gemini"

    def _ensure_client(self) -> Any:
        """Lazily initialize the Gemini client."""
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str,
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate a response using Google Gemini."""
        client = self._ensure_client()
        from google.genai import types

        # Convert messages to Gemini format
        system_instruction, contents = self._convert_messages(messages)

        # Build generation config
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
        )

        # Add tools if provided
        if tools:
            gemini_tools = self._convert_tools(tools)
            config.tools = gemini_tools

        # Active Gemini models with fallback priority (Flash-Lite models have high quota limits)
        valid_models = [
            "gemini-flash-lite-latest",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemma-4-26b-a4b-it",
            "gemma-4-31b-it",
        ]

        models_to_try: list[str] = []
        if model:
            models_to_try.append(model)

        for fallback in valid_models:
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        last_error: Exception | None = None
        rate_limited_count = 0

        for current_model in models_to_try:
            try:
                log.info("[GEMINI REQUEST START] model='%s'", current_model)
                response = await client.aio.models.generate_content(
                    model=current_model,
                    contents=contents,
                    config=config,
                )
                log.info("[GEMINI RESPONSE RECEIVED] model='%s'", current_model)
                return self._parse_response(response, current_model)
            except Exception as e:
                last_error = e
                err_str = str(e)

                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                    rate_limited_count += 1
                    log.warning("[GEMINI RATE LIMIT] 429 RESOURCE_EXHAUSTED on model '%s', trying fallback...", current_model)
                    continue

                log.warning("Gemini model '%s' failed (%s), attempting fallback...", current_model, e)

        log.error("All Gemini models failed: %s", last_error)
        if rate_limited_count == len(models_to_try):
            return LLMResponse(
                content="⚠️ Gemini rate limit / quota exceeded on all models. Please wait a moment before sending another message.",
                finish_reason="rate_limit",
                model=models_to_try[0] if models_to_try else "gemini-flash-lite-latest",
            )

        return LLMResponse(
            content="I am having trouble connecting to the AI neural engine right now. Please check your internet connection or try again in a moment.",
            finish_reason="error",
            model=models_to_try[0] if models_to_try else "gemini-flash-lite-latest",
        )

    def _convert_messages(self, messages: list[LLMMessage]) -> tuple[str | None, list[Any]]:
        """Convert LLMMessages to Gemini system instruction and content list."""
        from google.genai import types

        system_instruction: str | None = None
        raw_contents: list[tuple[str, list[Any]]] = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = (
                    f"{system_instruction}\n\n{msg.content}"
                    if system_instruction
                    else msg.content
                )
                continue

            # In Gemini: 'model' is assistant, 'user' is user & tool results
            role = "model" if msg.role == "assistant" else "user"

            parts: list[Any] = []
            if msg.role == "tool":
                try:
                    parts.append(
                        types.Part.from_function_response(
                            name=msg.name or "tool",
                            response={"output": msg.content},
                        )
                    )
                except Exception:
                    tool_text = f"[Tool Output ({msg.name or 'result'})]:\n{msg.content}"
                    parts.append(types.Part.from_text(text=tool_text))
            elif msg.content:
                parts.append(types.Part.from_text(text=msg.content))

            # Add images for vision
            if msg.images:
                import base64
                import os
                for img in msg.images:
                    try:
                        if img.startswith("data:"):
                            b64_data = img.split(",", 1)[1]
                            raw_img_bytes = base64.b64decode(b64_data)
                        elif os.path.exists(img):
                            with open(img, "rb") as img_file:
                                raw_img_bytes = img_file.read()
                        else:
                            # Assume raw base64 string
                            raw_img_bytes = base64.b64decode(img)

                        parts.append(
                            types.Part.from_bytes(
                                data=raw_img_bytes,
                                mime_type="image/png",
                            )
                        )
                    except Exception as img_err:
                        log.warning("Could not convert image for Gemini: %s", img_err)

            if parts:
                raw_contents.append((role, parts))

        # Merge consecutive turns with the same role (Gemini requires alternating user/model)
        contents: list[Any] = []
        for role, parts in raw_contents:
            if contents and contents[-1].role == role:
                contents[-1].parts.extend(parts)
            else:
                contents.append(types.Content(role=role, parts=parts))

        # Gemini requires that the request does NOT end with a model turn
        if contents and contents[-1].role == "model":
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text="Please proceed with your response.")],
                )
            )

        return system_instruction, contents

    def _convert_tools(self, tools: list[ToolSchema]) -> list[Any]:
        """Convert ToolSchema list to Gemini tool format."""
        from google.genai import types

        function_declarations = []
        for tool in tools:
            schema = (
                types.Schema.model_validate(tool.parameters)
                if isinstance(tool.parameters, dict)
                else None
            )
            func_decl = types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=schema,
            )
            function_declarations.append(func_decl)

        return [types.Tool(function_declarations=function_declarations)]

    def _parse_response(self, response: Any, model: str) -> LLMResponse:
        """Parse a Gemini response into our LLMResponse format."""
        tool_calls: list[ToolCallRequest] = []
        content = None

        if response.candidates:
            candidate = response.candidates[0]
            parts = candidate.content.parts if candidate.content else []

            for part in parts:
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    tool_calls.append(
                        ToolCallRequest(
                            id=f"call_{fc.name}_{len(tool_calls)}",
                            name=fc.name,
                            arguments=dict(fc.args) if fc.args else {},
                        )
                    )
                elif hasattr(part, "text") and part.text:
                    content = (content or "") + part.text

        # Determine finish reason
        finish_reason = "tool_calls" if tool_calls else "stop"

        # Extract usage
        usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage = {
                "prompt_tokens": getattr(um, "prompt_token_count", 0),
                "completion_tokens": getattr(um, "candidates_token_count", 0),
            }

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            model=model,
            usage=usage,
        )

    async def check_availability(self) -> bool:
        """Check if Gemini is available."""
        if not self._api_key:
            return False
        try:
            self._ensure_client()
            return True
        except Exception as e:
            log.warning("Gemini not available: %s", e)
            return False
