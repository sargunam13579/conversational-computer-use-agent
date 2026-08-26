"""
NEXUS Async Event Bus.

A lightweight, in-process publish/subscribe system that lets components
communicate without direct coupling. Events are dispatched asynchronously.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from nexus.utils.logging import get_logger

log = get_logger("events")

# Type alias for event handlers
EventHandler = Callable[["Event"], Coroutine[Any, Any, None]]


@dataclass
class Event:
    """An event that can be published on the event bus."""

    name: str
    data: dict[str, Any] = field(default_factory=dict)
    source: str = "system"
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __str__(self) -> str:
        return f"Event({self.name}, source={self.source})"


class EventBus:
    """
    Async event bus for decoupled inter-component communication.

    Usage:
        bus = EventBus()

        async def on_tool_executed(event: Event):
            print(f"Tool {event.data['tool_name']} finished")

        bus.on("tool.executed", on_tool_executed)
        await bus.emit("tool.executed", {"tool_name": "open_app", "result": "ok"})
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_handlers: list[EventHandler] = []

    def on(self, event_name: str, handler: EventHandler) -> None:
        """
        Subscribe to a specific event.

        Args:
            event_name: The event name to listen for. Use '*' for all events.
            handler: An async callable that receives an Event.
        """
        if event_name == "*":
            self._wildcard_handlers.append(handler)
        else:
            self._handlers[event_name].append(handler)
        log.debug("Registered handler for event '%s'", event_name)

    def off(self, event_name: str, handler: EventHandler) -> None:
        """Unsubscribe a handler from an event."""
        if event_name == "*":
            self._wildcard_handlers.remove(handler)
        elif event_name in self._handlers:
            self._handlers[event_name].remove(handler)

    async def emit(
        self,
        event_name: str,
        data: dict[str, Any] | None = None,
        source: str = "system",
    ) -> None:
        """
        Emit an event, notifying all subscribed handlers.

        Args:
            event_name: The event name to emit.
            data: Optional data payload.
            source: The component that emitted the event.
        """
        event = Event(name=event_name, data=data or {}, source=source)
        log.debug("Emitting %s", event)

        handlers = list(self._handlers.get(event_name, []))
        handlers.extend(self._wildcard_handlers)

        if not handlers:
            return

        # Fire all handlers concurrently
        results = await asyncio.gather(
            *(h(event) for h in handlers),
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, Exception):
                log.error("Event handler error for '%s': %s", event_name, result)

    def emit_sync(
        self,
        event_name: str,
        data: dict[str, Any] | None = None,
        source: str = "system",
    ) -> None:
        """
        Emit an event synchronously.

        If an event loop is running, schedules the async emit as a background task.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.emit(event_name, data, source))
        except RuntimeError:
            # No running event loop in current thread
            pass

    def clear(self) -> None:
        """Remove all event handlers."""
        self._handlers.clear()
        self._wildcard_handlers.clear()


# ---------------------------------------------------------------------------
# Global event bus instance
# ---------------------------------------------------------------------------

_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Return the global event bus singleton."""
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
