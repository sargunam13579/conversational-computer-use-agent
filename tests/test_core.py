"""Tests for the NEXUS context manager and core utilities."""

from __future__ import annotations

from nexus.core.context import ContextManager
from nexus.utils.text import format_file_size, normalize_text, sanitize_filename, truncate

# ---------------------------------------------------------------------------
# Context Manager Tests
# ---------------------------------------------------------------------------


class TestContextManager:
    """Tests for the ContextManager."""

    def test_empty_context(self):
        ctx = ContextManager(max_turns=10)
        assert ctx.turn_count == 0
        assert ctx.message_count == 0

    def test_add_messages(self):
        ctx = ContextManager(max_turns=10)
        ctx.add_user_message("Hello")
        ctx.add_assistant_message("Hi there!")
        assert ctx.turn_count == 1
        assert ctx.message_count == 2

    def test_system_prompt(self):
        ctx = ContextManager(max_turns=10)
        ctx.set_system_prompt("You are NEXUS")
        ctx.add_user_message("Hello")

        messages = ctx.get_messages()
        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[0].content == "You are NEXUS"
        assert messages[1].role == "user"

    def test_trim_old_messages(self):
        ctx = ContextManager(max_turns=3)
        for i in range(5):
            ctx.add_user_message(f"Message {i}")
            ctx.add_assistant_message(f"Response {i}")

        assert ctx.turn_count <= 3

    def test_get_last_user_message(self):
        ctx = ContextManager(max_turns=10)
        ctx.add_user_message("First")
        ctx.add_assistant_message("Response")
        ctx.add_user_message("Second")
        assert ctx.get_last_user_message() == "Second"

    def test_get_last_user_message_empty(self):
        ctx = ContextManager(max_turns=10)
        assert ctx.get_last_user_message() is None

    def test_clear(self):
        ctx = ContextManager(max_turns=10)
        ctx.set_system_prompt("System")
        ctx.add_user_message("Hello")
        ctx.add_assistant_message("Hi")
        ctx.clear()
        assert ctx.message_count == 0
        # System prompt should be preserved after clear
        messages = ctx.get_messages()
        assert len(messages) == 1  # Only system prompt
        assert messages[0].role == "system"

    def test_tool_result(self):
        ctx = ContextManager(max_turns=10)
        ctx.add_user_message("What time is it?")
        ctx.add_tool_result(
            tool_call_id="call_1",
            tool_name="get_current_time",
            result="Current time: 10:30 AM",
        )
        messages = ctx.get_messages()
        tool_msg = messages[-1]
        assert tool_msg.role == "tool"
        assert tool_msg.name == "get_current_time"
        assert tool_msg.tool_call_id == "call_1"


# ---------------------------------------------------------------------------
# Text Utility Tests
# ---------------------------------------------------------------------------


class TestTextUtils:
    """Tests for text processing utilities."""

    def test_normalize_text(self):
        assert normalize_text("  hello   world  ") == "hello world"
        assert normalize_text("") == ""

    def test_truncate(self):
        assert truncate("hello", 10) == "hello"
        assert truncate("hello world this is long", 10) == "hello w..."
        assert truncate("hello", 5) == "hello"

    def test_format_file_size(self):
        assert format_file_size(500) == "500.0 B"
        assert "KB" in format_file_size(1024)
        assert "MB" in format_file_size(1024 * 1024)
        assert "GB" in format_file_size(1024**3)

    def test_sanitize_filename(self):
        assert sanitize_filename("hello.txt") == "hello.txt"
        assert sanitize_filename("file:with<bad>chars") == "file_with_bad_chars"
        assert sanitize_filename("") == "unnamed"
        assert sanitize_filename("...") == "unnamed"
