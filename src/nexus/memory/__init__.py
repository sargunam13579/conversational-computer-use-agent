"""
NEXUS Memory Package.

Provides short-term conversation memory, task memory, long-term preferences,
device & application configs, privacy redaction, and contextual reference resolution.
"""

from nexus.memory.context_resolver import ContextResolver
from nexus.memory.manager import MemoryManager
from nexus.memory.privacy import MemoryPrivacyFilter
from nexus.memory.storage import MemoryStorage
from nexus.memory.types import (
    ContextState,
    MemoryCategory,
    MemoryRecord,
    PrivacyLevel,
)

__all__ = [
    "MemoryCategory",
    "PrivacyLevel",
    "MemoryRecord",
    "ContextState",
    "MemoryPrivacyFilter",
    "MemoryStorage",
    "ContextResolver",
    "MemoryManager",
]
