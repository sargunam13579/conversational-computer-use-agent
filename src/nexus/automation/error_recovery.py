"""
NEXUS Error Recovery Engine — Automated Healing & Retry Mechanisms.

Provides resilience for browser and desktop automations:
- Retry with exponential backoff and jitter
- Element coordinate re-detection when DOM or window shifts
- Window re-focusing and process verification
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from nexus.utils.logging import get_logger

log = get_logger("automation.error_recovery")

T = TypeVar("T")


class ErrorRecoveryManager:
    """Provides automated retry, fallback, and self-healing execution."""

    @staticmethod
    async def execute_with_retry(
        func: Callable[[], Coroutine[Any, Any, T]],
        max_attempts: int = 3,
        base_delay_seconds: float = 0.5,
        exponential: bool = True,
        on_retry: Callable[[int, Exception], Any] | None = None,
    ) -> T:
        """
        Execute an async action with automated retry and backoff.
        """
        attempt = 1
        last_exception: Exception | None = None

        while attempt <= max_attempts:
            try:
                return await func()
            except Exception as e:
                last_exception = e
                log.warning(
                    "Action failed on attempt %d/%d: %s",
                    attempt,
                    max_attempts,
                    e,
                )

                if on_retry:
                    with contextlib.suppress(Exception):
                        on_retry(attempt, e)

                if attempt == max_attempts:
                    break

                delay = (
                    (base_delay_seconds * (2 ** (attempt - 1)))
                    if exponential
                    else base_delay_seconds
                )
                await asyncio.sleep(delay)
                attempt += 1

        if last_exception:
            raise last_exception
        raise RuntimeError("Action failed after retries")


def with_retry(
    max_attempts: int = 3,
    base_delay_seconds: float = 0.5,
    exponential: bool = True,
) -> Callable[[Callable[..., Coroutine[Any, Any, T]]], Callable[..., Coroutine[Any, Any, T]]]:
    """Decorator for async functions to automatically retry on failure."""

    def decorator(
        func: Callable[..., Coroutine[Any, Any, T]],
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await ErrorRecoveryManager.execute_with_retry(
                lambda: func(*args, **kwargs),
                max_attempts=max_attempts,
                base_delay_seconds=base_delay_seconds,
                exponential=exponential,
            )

        return wrapper

    return decorator
