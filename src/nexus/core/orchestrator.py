"""
NEXUS Orchestrator.

Implements the agentic loop: the core cycle of
  User Input → LLM → Tool Calls → Results → LLM → Response
This is the engine that turns NEXUS from a chatbot into an agent.
"""

from __future__ import annotations

from typing import Any

from nexus.core.context import ContextManager
from nexus.llm.providers.base import ModelTier
from nexus.llm.router import ModelRouter
from nexus.tools.executor import ToolExecutor
from nexus.tools.registry import ToolRegistry
from nexus.utils.events import get_event_bus
from nexus.utils.logging import get_logger, print_thinking

log = get_logger("core.orchestrator")

# Maximum iterations of the agentic loop to prevent infinite tool-call chains
MAX_AGENT_ITERATIONS = 10

_TOOL_INTENT_KEYWORDS = {
    "open", "launch", "start", "run", "close", "kill", "stop", "terminate",
    "screenshot", "capture", "camera", "photo", "record",
    "volume", "mute", "unmute", "sound", "audio", "brightness", "display",
    "battery", "power", "shutdown", "restart", "sleep", "lock",
    "wifi", "bluetooth", "network", "ip", "ping", "system", "specs", "diagnostic",
    "file", "folder", "directory", "delete", "create", "search file", "list files",
    "browser", "search", "google", "url", "navigate", "website", "tab",
    "phone", "android", "device", "tap", "swipe", "sms", "notification"
}


def _requires_tools(user_input: str) -> bool:
    """Check if the user input requires system action tools (Tool Path) or is conversational (Fast Path)."""
    lowered = user_input.lower().strip()
    words = set(lowered.split())
    return any(kw in words or kw in lowered for kw in _TOOL_INTENT_KEYWORDS)


class Orchestrator:
    """
    Coordinates the agentic loop: LLM reasoning → tool execution → final response.

    Attributes:
        last_tool_calls: Tool calls executed during the last message turn.
    """

    def __init__(
        self,
        router: ModelRouter,
        registry: ToolRegistry,
        executor: ToolExecutor,
        context: ContextManager,
    ) -> None:
        self._router = router
        self._registry = registry
        self._executor = executor
        self._context = context
        self._event_bus = get_event_bus()
        self.last_tool_calls: list[dict[str, Any]] = []

    async def process(
        self,
        user_input: str,
        tier: ModelTier = ModelTier.FAST,
        show_thinking: bool = True,
    ) -> str:
        """
        Process a user input through the full agentic loop.

        Args:
            user_input: The user's message or command.
            tier: Which model tier to use for this request.
            show_thinking: Whether to print thinking steps in the terminal.

        Returns:
            The final text response from NEXUS.
        """
        # Clear tool calls history for this turn
        self.last_tool_calls = []

        # Add user message to context
        self._context.add_user_message(user_input)

        # Fast Path vs Tool Path determination
        needs_tools = _requires_tools(user_input)
        tool_schemas = self._registry.get_schemas() if needs_tools else None

        # Emit event
        await self._event_bus.emit(
            "user.message",
            {"content": user_input, "mode": "tool" if needs_tools else "fast"},
            source="orchestrator",
        )

        executed_tools: list[dict[str, Any]] = []

        # --- Agentic Loop ---
        for iteration in range(MAX_AGENT_ITERATIONS):
            log.debug("Agentic loop iteration %d (needs_tools=%s)", iteration + 1, needs_tools)

            if show_thinking and iteration > 0:
                print_thinking(f"Thinking... (step {iteration + 1})")

            # Send to LLM (offer tools only on first pass if tools are needed)
            active_tools = tool_schemas if (tool_schemas and iteration == 0) else None
            messages = self._context.get_messages()
            response = await self._router.generate(
                messages=messages,
                tier=tier,
                tools=active_tools,
            )

            # If the LLM returned a final text response (no tool calls), we're done
            if not response.has_tool_calls:
                final_response = response.content or "I completed the task."
                self._context.add_assistant_message(final_response)
                self.last_tool_calls = executed_tools

                await self._event_bus.emit(
                    "assistant.response",
                    {"content": final_response, "iterations": iteration + 1},
                    source="orchestrator",
                )
                return final_response

            # Add the assistant's tool-calling intent to context
            if response.content:
                self._context.add_assistant_message(response.content)

            # Execute each tool call and collect results
            for tc in response.tool_calls:
                log.info("LLM requested tool: %s(%s)", tc.name, tc.arguments)

                if show_thinking:
                    print_thinking(f"Calling {tc.name}...")

                result = await self._executor.execute(
                    tool_name=tc.name,
                    parameters=tc.arguments,
                )

                executed_tools.append({
                    "name": tc.name,
                    "arguments": tc.arguments if isinstance(tc.arguments, dict) else {},
                    "result": str(result.output) if result.output is not None else None,
                    "success": bool(result.success),
                })
                self.last_tool_calls = executed_tools

                # Add tool result to context for the next LLM iteration
                self._context.add_tool_result(
                    tool_call_id=tc.id,
                    tool_name=tc.name,
                    result=result.output,
                )

        # If we exhausted all iterations, return what we have
        log.warning("Agentic loop reached max iterations (%d)", MAX_AGENT_ITERATIONS)
        self.last_tool_calls = executed_tools
        final = "I've been working on this task but reached my step limit. Here's what I've done so far."
        self._context.add_assistant_message(final)
        return final

    def reset(self) -> None:
        """Reset the conversation context."""
        self._context.clear()
        log.info("Conversation context reset")
