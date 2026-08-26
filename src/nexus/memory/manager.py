"""
NEXUS Unified Memory Manager.

Orchestrates all 6 memory categories, integrates privacy controls, automated preference learning,
and prompt context enrichment.
"""

from __future__ import annotations

import re
from typing import Any

from nexus.memory.context_resolver import ContextResolver
from nexus.memory.privacy import MemoryPrivacyFilter
from nexus.memory.storage import MemoryStorage
from nexus.memory.types import MemoryCategory, MemoryRecord, PrivacyLevel
from nexus.utils.logging import get_logger

log = get_logger("memory.manager")

# Patterns to detect explicit preference statements from user input
_PREFERENCE_LEARNING_PATTERNS = [
    # "My Java projects are normally inside D:/Projects"
    re.compile(
        r"my\s+(?P<topic>[a-zA-Z0-9_+]+)\s+(?:projects|files|docs|code)\s+(?:are|is)\s+(?:normally|usually|located|stored)?\s+(?:in|inside|at)\s+(?P<val>[a-zA-Z]:[\\/][^\s]+|/[^\s]+)",
        re.IGNORECASE,
    ),
    # "Remember that my email is user@example.com"
    re.compile(
        r"(?:remember|save|store)\s+(?:that\s+)?(?:my\s+)?(?P<key>[a-zA-Z0-9_\-\s]{2,30})\s+(?:is|=|as)\s+(?P<val>.+)",
        re.IGNORECASE,
    ),
    # "Set my default browser to Chrome"
    re.compile(
        r"(?:set|change)\s+(?:my\s+)?default\s+(?P<app>[a-zA-Z0-9_]+)\s+to\s+(?P<val>[a-zA-Z0-9_\s]+)",
        re.IGNORECASE,
    ),
]


class MemoryManager:
    """Central manager for all persistent memory operations and contextual learning."""

    def __init__(
        self,
        storage: MemoryStorage | None = None,
        privacy_filter: MemoryPrivacyFilter | None = None,
        context_resolver: ContextResolver | None = None,
    ) -> None:
        self._privacy = privacy_filter or MemoryPrivacyFilter()
        self._storage = storage or MemoryStorage(privacy_filter=self._privacy)
        self._resolver = context_resolver or ContextResolver(storage=self._storage)

    @property
    def storage(self) -> MemoryStorage:
        return self._storage

    @property
    def privacy(self) -> MemoryPrivacyFilter:
        return self._privacy

    @property
    def resolver(self) -> ContextResolver:
        return self._resolver

    @property
    def is_enabled(self) -> bool:
        return self._storage.is_enabled

    def set_enabled(self, enabled: bool) -> None:
        self._storage.set_enabled(enabled)

    async def auto_learn_from_message(self, user_message: str) -> MemoryRecord | None:
        """Inspect user message for explicit preference statements and store them."""
        if not self.is_enabled:
            return None

        clean_text = user_message.strip()

        # 1. Project Directory Pattern
        match_proj = _PREFERENCE_LEARNING_PATTERNS[0].search(clean_text)
        if match_proj:
            topic = match_proj.group("topic").lower().strip()
            path_val = match_proj.group("val").strip()
            key = f"{topic}_projects_dir"
            return await self._storage.store(
                key=key,
                value=path_val,
                category=MemoryCategory.USER_PREFERENCE,
                tags=[topic, "projects", "path", "directory"],
                confidence=0.95,
            )

        # 2. Explicit "Remember that X is Y" Pattern
        match_rem = _PREFERENCE_LEARNING_PATTERNS[1].search(clean_text)
        if match_rem:
            key_raw = match_rem.group("key").strip()
            val_raw = match_rem.group("val").strip().rstrip(".!?")
            key_clean = re.sub(r"\s+", "_", key_raw).lower()
            return await self._storage.store(
                key=key_clean,
                value=val_raw,
                category=MemoryCategory.USER_DEFINED_INFO,
                tags=["user_note", key_clean],
                confidence=1.0,
            )

        # 3. Default App Pattern
        match_app = _PREFERENCE_LEARNING_PATTERNS[2].search(clean_text)
        if match_app:
            app_type = match_app.group("app").strip().lower()
            app_val = match_app.group("val").strip().rstrip(".!?")
            key = f"default_{app_type}"
            return await self._storage.store(
                key=key,
                value=app_val,
                category=MemoryCategory.APP_PREFERENCE,
                tags=["default_app", app_type],
                confidence=0.95,
            )

        return None

    async def store_memory(
        self,
        key: str,
        value: Any,
        category: MemoryCategory = MemoryCategory.USER_DEFINED_INFO,
        tags: list[str] | None = None,
        confidence: float = 1.0,
        privacy_level: PrivacyLevel = PrivacyLevel.PRIVATE,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord | None:
        """Store or update a memory item."""
        return await self._storage.store(
            key=key,
            value=value,
            category=category,
            tags=tags,
            confidence=confidence,
            privacy_level=privacy_level,
            metadata=metadata,
        )

    async def recall_memory(
        self,
        key: str,
        category: MemoryCategory | None = None,
    ) -> MemoryRecord | None:
        """Retrieve memory by exact key."""
        return await self._storage.find_by_key(key=key, category=category)

    async def search_memory(
        self,
        query: str = "",
        category: MemoryCategory | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
    ) -> list[MemoryRecord]:
        """Search memory by query keywords, category, or tags."""
        return await self._storage.search(query=query, category=category, tags=tags, limit=limit)

    async def delete_memory(self, record_id_or_key: str) -> bool:
        """Delete specific memory by ID or key."""
        return await self._storage.delete(record_id_or_key)

    async def clear_memory(self, category: MemoryCategory | None = None) -> int:
        """Clear all memories or memories in a specific category."""
        return await self._storage.clear(category)

    async def get_stats(self) -> dict[str, Any]:
        """Get summary stats."""
        return await self._storage.get_stats()
