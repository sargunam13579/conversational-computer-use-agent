"""
NEXUS Planning — Safe Failure Recovery & Retry System.

Categorizes errors into safe/transient vs. unrecoverable fatal failures,
and handles exponential backoff and tool fallback strategies.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum

from nexus.planning.types import PlanStep
from nexus.utils.logging import get_logger

log = get_logger("planning.retry")


class ErrorCategory(StrEnum):
    """Classification of errors for recovery strategy."""

    TRANSIENT = "transient"  # Network glitch, busy lock, temporary timeout
    TOOL_FALLBACK = "tool_fallback"  # Tool failed, alternative tool available
    FATAL = "fatal"  # Permission denied, syntax error, missing mandatory secret
    NEEDS_CLARIFICATION = "needs_clarification"  # Missing parameter, ambiguous path


# Keywords indicating transient, safe-to-retry issues
_TRANSIENT_ERROR_KEYWORDS = [
    "timeout",
    "temporarily unavailable",
    "connection reset",
    "busy",
    "locked",
    "rate limit",
    "econnrefused",
    "try again",
    "device offline",
    "stream not open",
]

# Fallback mappings: tool -> alternative tool
_TOOL_FALLBACK_MAP: dict[str, list[str]] = {
    "convert_document": ["print_to_pdf", "shell_execute"],
    "read_webpage": ["browser_navigate", "search_web"],
    "launch_app": ["shell_execute"],
    "send_file": ["transfer_file_adb", "save_to_shared_folder"],
}


@dataclass
class RetryDecision:
    """Actionable recommendation on how to handle a step failure."""

    should_retry: bool
    category: ErrorCategory
    delay_seconds: float = 0.0
    fallback_tool: str | None = None
    reason: str = ""


class RetrySystem:
    """
    Evaluates execution failures and manages retry/recovery strategies.
    """

    def __init__(
        self,
        base_delay_seconds: float = 0.5,
        max_delay_seconds: float = 5.0,
        backoff_multiplier: float = 1.5,
    ) -> None:
        self.base_delay = base_delay_seconds
        self.max_delay = max_delay_seconds
        self.multiplier = backoff_multiplier

    def classify_error(self, error_message: str) -> ErrorCategory:
        """Classify an error message into an ErrorCategory."""
        msg = error_message.lower()

        if any(kw in msg for kw in _TRANSIENT_ERROR_KEYWORDS):
            return ErrorCategory.TRANSIENT

        if "ambiguous" in msg or "multiple files found" in msg or "not specified" in msg:
            return ErrorCategory.NEEDS_CLARIFICATION

        return ErrorCategory.FATAL

    def evaluate_retry(self, step: PlanStep, error_message: str) -> RetryDecision:
        """
        Determine whether a failed step should be retried and with what parameters.
        """
        if step.retry_count >= step.max_retries:
            # Check if an alternative fallback tool exists
            if step.tool_name and step.tool_name in _TOOL_FALLBACK_MAP:
                alternatives = _TOOL_FALLBACK_MAP[step.tool_name]
                for alt in alternatives:
                    if alt != step.tool_name:
                        return RetryDecision(
                            should_retry=True,
                            category=ErrorCategory.TOOL_FALLBACK,
                            fallback_tool=alt,
                            delay_seconds=self.base_delay,
                            reason=f"Primary tool '{step.tool_name}' exhausted retries. Switching to fallback tool '{alt}'",
                        )

            return RetryDecision(
                should_retry=False,
                category=ErrorCategory.FATAL,
                reason=f"Exhausted maximum retries ({step.max_retries}) for step {step.order}",
            )

        category = self.classify_error(error_message)

        if category == ErrorCategory.TRANSIENT:
            delay = min(
                self.max_delay,
                self.base_delay * (self.multiplier**step.retry_count),
            )
            return RetryDecision(
                should_retry=True,
                category=category,
                delay_seconds=delay,
                reason=f"Transient failure detected ({error_message}). Backing off for {delay:.2f}s (attempt {step.retry_count + 1}/{step.max_retries})",
            )

        # Check for tool fallback even on non-transient errors if applicable
        if step.tool_name and step.tool_name in _TOOL_FALLBACK_MAP:
            alt = _TOOL_FALLBACK_MAP[step.tool_name][0]
            return RetryDecision(
                should_retry=True,
                category=ErrorCategory.TOOL_FALLBACK,
                fallback_tool=alt,
                delay_seconds=self.base_delay,
                reason=f"Tool '{step.tool_name}' failed with error ({error_message}). Attempting fallback tool '{alt}'",
            )

        return RetryDecision(
            should_retry=False,
            category=category,
            reason=f"Non-recoverable failure on step {step.order}: {error_message}",
        )

    async def execute_backoff(self, decision: RetryDecision) -> None:
        """Asynchronously sleep for the recommended retry delay."""
        if decision.delay_seconds > 0:
            log.info("Applying retry backoff delay: %.2fs", decision.delay_seconds)
            await asyncio.sleep(decision.delay_seconds)
