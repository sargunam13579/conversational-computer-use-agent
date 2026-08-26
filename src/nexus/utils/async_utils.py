"""
NEXUS Async Utilities.

Common async patterns used across the codebase: retry, timeout, throttle, etc.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any, TypeVar

from nexus.utils.logging import get_logger

log = get_logger("async_utils")

T = TypeVar("T")


async def retry_async(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs: Any,
) -> Any:
    """
    Retry an async function with exponential backoff.

    Args:
        func: The async function to call.
        max_retries: Maximum number of retry attempts.
        delay: Initial delay between retries (seconds).
        backoff: Multiplier applied to delay after each retry.
        exceptions: Tuple of exception types to catch and retry on.
    """
    last_exception: Exception | None = None
    current_delay = delay

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                log.warning(
                    "Attempt %d/%d failed for %s: %s. Retrying in %.1fs...",
                    attempt + 1,
                    max_retries + 1,
                    func.__name__,
                    e,
                    current_delay,
                )
                await asyncio.sleep(current_delay)
                current_delay *= backoff
            else:
                log.error(
                    "All %d attempts failed for %s: %s",
                    max_retries + 1,
                    func.__name__,
                    e,
                )

    raise last_exception  # type: ignore[misc]


async def timeout_async(
    func: Callable[..., Any],
    *args: Any,
    timeout_seconds: float = 30.0,
    **kwargs: Any,
) -> Any:
    """
    Run an async function with a timeout.

    Raises asyncio.TimeoutError if the function doesn't complete in time.
    """
    return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)


class RateLimiter:
    """
    Simple token-bucket rate limiter for async operations.

    Usage:
        limiter = RateLimiter(max_calls=5, period=60.0)  # 5 calls per minute
        await limiter.acquire()  # blocks if rate limit exceeded
    """

    def __init__(self, max_calls: int, period: float) -> None:
        self.max_calls = max_calls
        self.period = period
        self._calls: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a call is allowed under the rate limit."""
        async with self._lock:
            now = time.monotonic()
            # Remove expired timestamps
            self._calls = [t for t in self._calls if now - t < self.period]

            if len(self._calls) >= self.max_calls:
                # Wait until the oldest call expires
                wait_time = self.period - (now - self._calls[0])
                if wait_time > 0:
                    log.debug("Rate limit hit. Waiting %.1fs", wait_time)
                    await asyncio.sleep(wait_time)

            self._calls.append(time.monotonic())

    @property
    def remaining(self) -> int:
        """Number of calls remaining in the current window."""
        now = time.monotonic()
        active = [t for t in self._calls if now - t < self.period]
        return max(0, self.max_calls - len(active))
