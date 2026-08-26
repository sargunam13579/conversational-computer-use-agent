"""
NEXUS Core — Confirmation Security System.

Provides two-step verification for sensitive operations (such as identity changes,
settings modifications, and high-risk actions). Manages pending confirmation states
with automatic timeout expiration and intent detection.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from nexus.utils.events import get_event_bus
from nexus.utils.logging import get_logger

log = get_logger("core.confirmation")

DEFAULT_CONFIRMATION_TIMEOUT_SECONDS = 60.0

AFFIRMATIVE_PHRASES = {
    "yes",
    "y",
    "yep",
    "yeah",
    "sure",
    "confirm",
    "proceed",
    "do it",
    "go ahead",
    "please do",
    "affirmative",
    "correct",
    "ok",
    "okay",
    "sounds good",
    "absolutely",
    "definitely",
    "i agree",
    "accept",
}

NEGATIVE_PHRASES = {
    "no",
    "n",
    "nope",
    "nah",
    "cancel",
    "stop",
    "never mind",
    "nevermind",
    "abort",
    "don't",
    "do not",
    "negative",
    "reject",
    "decline",
    "disagree",
}


class ConfirmationAction(StrEnum):
    """Types of actions that require confirmation."""

    CHANGE_NAME = "change_name"
    CHANGE_SETTINGS = "change_settings"
    DELETE_DATA = "delete_data"
    EXECUTE_TOOL = "execute_tool"
    CUSTOM = "custom"


class ConfirmationStatus(StrEnum):
    """Status of a confirmation request."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class PendingConfirmation:
    """A pending confirmation request."""

    id: str
    action: ConfirmationAction | str
    prompt_message: str
    payload: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = DEFAULT_CONFIRMATION_TIMEOUT_SECONDS
    created_at: float = field(default_factory=time.time)
    on_confirm: Callable[[dict[str, Any]], Coroutine[Any, Any, str] | str | None] | None = None
    on_reject: Callable[[dict[str, Any]], Coroutine[Any, Any, str] | str | None] | None = None

    @property
    def is_expired(self) -> bool:
        """Check if this confirmation has expired."""
        return (time.time() - self.created_at) > self.timeout_seconds


class ConfirmationManager:
    """
    Manages pending confirmation requests for security.

    Ensures critical actions are not executed unintentionally or without explicit
    verification by the user.
    """

    def __init__(self, default_timeout: float = DEFAULT_CONFIRMATION_TIMEOUT_SECONDS) -> None:
        self._default_timeout = default_timeout
        self._pending: PendingConfirmation | None = None
        self._event_bus = get_event_bus()

    @property
    def has_pending(self) -> bool:
        """Whether a valid (non-expired) confirmation is pending."""
        if self._pending is None:
            return False
        if self._pending.is_expired:
            self.expire()
            return False
        return True

    @property
    def pending_action(self) -> PendingConfirmation | None:
        """Get the current pending confirmation if not expired."""
        if self.has_pending:
            return self._pending
        return None

    def create_confirmation(
        self,
        action: ConfirmationAction | str,
        prompt_message: str,
        payload: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
        on_confirm: Callable[[dict[str, Any]], Any] | None = None,
        on_reject: Callable[[dict[str, Any]], Any] | None = None,
    ) -> PendingConfirmation:
        """
        Create a new pending confirmation request.

        Any existing pending confirmation is replaced.
        """
        import uuid

        conf_id = str(uuid.uuid4())
        conf = PendingConfirmation(
            id=conf_id,
            action=action,
            prompt_message=prompt_message,
            payload=payload or {},
            timeout_seconds=timeout_seconds or self._default_timeout,
            on_confirm=on_confirm,
            on_reject=on_reject,
        )
        self._pending = conf
        log.info("Created pending confirmation [%s]: %s", action, prompt_message)

        self._event_bus.emit_sync(
            "confirmation.created",
            {"id": conf_id, "action": str(action), "prompt": prompt_message},
            source="confirmation_manager",
        )
        return conf

    def is_affirmative(self, text: str) -> bool:
        """Check if user input text expresses confirmation/affirmation."""
        normalized = self._normalize(text)
        if normalized in AFFIRMATIVE_PHRASES:
            return True
        # Check starting word or contains clear affirmation
        words = normalized.split()
        return bool(words and words[0] in AFFIRMATIVE_PHRASES)

    def is_negative(self, text: str) -> bool:
        """Check if user input text expresses rejection/cancellation."""
        normalized = self._normalize(text)
        if normalized in NEGATIVE_PHRASES:
            return True
        words = normalized.split()
        return bool(words and words[0] in NEGATIVE_PHRASES)

    async def handle_response(self, user_input: str) -> tuple[ConfirmationStatus, str]:
        """
        Evaluate user input against the pending confirmation.

        Returns:
            (status, response_message)
        """
        if not self.has_pending or self._pending is None:
            return ConfirmationStatus.EXPIRED, "No confirmation is currently pending."

        conf = self._pending

        if self.is_affirmative(user_input):
            return await self.confirm()
        elif self.is_negative(user_input):
            return await self.reject()
        else:
            # Ambiguous input — re-prompt the user
            return ConfirmationStatus.PENDING, (
                f"Please reply 'Yes' or 'No'. {conf.prompt_message}"
            )

    async def confirm(self) -> tuple[ConfirmationStatus, str]:
        """Confirm the currently pending action."""
        if not self.has_pending or self._pending is None:
            return ConfirmationStatus.EXPIRED, "Confirmation has expired or does not exist."

        conf = self._pending
        self._pending = None
        log.info("Confirmation [%s] CONFIRMED", conf.action)

        response_msg = "Action confirmed."
        if conf.on_confirm is not None:
            import inspect

            if inspect.iscoroutinefunction(conf.on_confirm):
                result = await conf.on_confirm(conf.payload)
            else:
                result = conf.on_confirm(conf.payload)
            if isinstance(result, str) and result:
                response_msg = result

        await self._event_bus.emit(
            "confirmation.confirmed",
            {"id": conf.id, "action": str(conf.action), "payload": conf.payload},
            source="confirmation_manager",
        )
        return ConfirmationStatus.CONFIRMED, response_msg

    async def reject(self) -> tuple[ConfirmationStatus, str]:
        """Reject/cancel the currently pending action."""
        if self._pending is None:
            return ConfirmationStatus.REJECTED, "No confirmation was pending."

        conf = self._pending
        self._pending = None
        log.info("Confirmation [%s] REJECTED", conf.action)

        response_msg = "Action cancelled."
        if conf.on_reject is not None:
            import inspect

            if inspect.iscoroutinefunction(conf.on_reject):
                result = await conf.on_reject(conf.payload)
            else:
                result = conf.on_reject(conf.payload)
            if isinstance(result, str) and result:
                response_msg = result

        await self._event_bus.emit(
            "confirmation.rejected",
            {"id": conf.id, "action": str(conf.action)},
            source="confirmation_manager",
        )
        return ConfirmationStatus.REJECTED, response_msg

    def expire(self) -> None:
        """Mark current confirmation as expired and clear it."""
        if self._pending is not None:
            log.info("Confirmation [%s] EXPIRED", self._pending.action)
            conf = self._pending
            self._pending = None
            self._event_bus.emit_sync(
                "confirmation.expired",
                {"id": conf.id, "action": str(conf.action)},
                source="confirmation_manager",
            )

    def cancel(self) -> None:
        """Immediately clear pending confirmation without callback."""
        self._pending = None

    def _normalize(self, text: str) -> str:
        """Normalize text for intent matching."""
        cleaned = re.sub(r"[^\w\s]", "", text.strip().lower())
        return " ".join(cleaned.split())
