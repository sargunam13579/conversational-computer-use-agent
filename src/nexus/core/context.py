"""
NEXUS Context Manager.

Manages the conversation context (working memory), building the message
history that gets sent to the LLM on each turn.
"""

from __future__ import annotations

from collections import deque

from nexus.llm.providers.base import LLMMessage
from nexus.utils.logging import get_logger

log = get_logger("core.context")


class ContextManager:
    """
    Manages the conversation context window.

    Maintains a sliding window of messages and injects system context
    (tools, memory, device state) into the prompt.
    """

    def __init__(self, max_turns: int = 20) -> None:
        """
        Args:
            max_turns: Maximum number of user+assistant turn pairs to keep.
        """
        self._max_turns = max_turns
        self._messages: deque[LLMMessage] = deque()
        self._system_prompt: str = ""

    def set_system_prompt(self, prompt: str) -> None:
        """Set or update the system prompt."""
        self._system_prompt = prompt

    @property
    def system_prompt(self) -> str:
        """Get the current system prompt."""
        return self._system_prompt

    def get_system_prompt(self) -> str:
        """Get the current system prompt."""
        return self._system_prompt

    def add_user_message(self, content: str) -> None:
        """Add a user message to the context."""
        self._messages.append(LLMMessage(role="user", content=content))
        self._trim()

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant response to the context."""
        self._messages.append(LLMMessage(role="assistant", content=content))
        self._trim()

    def add_tool_call_message(self, content: str) -> None:
        """Add an assistant message representing a tool call."""
        self._messages.append(LLMMessage(role="assistant", content=content))

    def add_tool_result(self, tool_call_id: str, tool_name: str, result: str) -> None:
        """Add a tool result message to the context."""
        self._messages.append(
            LLMMessage(
                role="tool",
                content=result,
                name=tool_name,
                tool_call_id=tool_call_id,
            )
        )

    def get_messages(self) -> list[LLMMessage]:
        """
        Build the full message list for the LLM, including system prompt.

        Returns:
            List starting with the system prompt, followed by conversation history.
        """
        messages = []
        if self._system_prompt:
            messages.append(LLMMessage(role="system", content=self._system_prompt))
        messages.extend(self._messages)
        return messages

    def clear(self) -> None:
        """Clear all conversation history (keeps system prompt)."""
        self._messages.clear()

    def _trim(self) -> None:
        """Trim the context to stay within the max turns limit."""
        # Count user messages as "turns"
        user_count = sum(1 for m in self._messages if m.role == "user")
        while user_count > self._max_turns and self._messages:
            removed = self._messages.popleft()
            if removed.role == "user":
                user_count -= 1

    @property
    def turn_count(self) -> int:
        """Number of user turns in the current context."""
        return sum(1 for m in self._messages if m.role == "user")

    @property
    def message_count(self) -> int:
        """Total number of messages in the context."""
        return len(self._messages)

    def get_recent_turns(self, count: int = 5) -> list[str]:
        """Return list of recent user message contents."""
        turns = [m.content for m in self._messages if m.role == "user"]
        return turns[-count:]

    def get_last_user_message(self) -> str | None:
        """Return the content of the last user message."""
        for msg in reversed(self._messages):
            if msg.role == "user":
                return msg.content
        return None
