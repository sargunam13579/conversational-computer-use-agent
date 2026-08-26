"""NEXUS core module — AI Brain, orchestrator, planner, intent, context, identity, confirmation."""

from nexus.core.brain import NexusBrain
from nexus.core.config import NexusSettings, get_settings, load_settings
from nexus.core.confirmation import (
    ConfirmationAction,
    ConfirmationManager,
    ConfirmationStatus,
    PendingConfirmation,
)
from nexus.core.context import ContextManager
from nexus.core.identity import IdentityConfig, IdentityManager
from nexus.core.orchestrator import Orchestrator

__all__ = [
    "ConfirmationAction",
    "ConfirmationManager",
    "ConfirmationStatus",
    "ContextManager",
    "IdentityConfig",
    "IdentityManager",
    "NexusBrain",
    "NexusSettings",
    "Orchestrator",
    "PendingConfirmation",
    "get_settings",
    "load_settings",
]
