"""
NEXUS Memory System — Data Types and Enumerations.

Defines the 6 core memory categories, record schemas, and context state structures.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class MemoryCategory(StrEnum):
    """The 6 core memory categories in NEXUS."""

    CONVERSATION = "conversation"  # Short-term dialog history and turn state
    CURRENT_TASK = "current_task"  # Active task, goals, step progress, target files
    USER_PREFERENCE = "user_preference"  # Long-term user preferences (paths, styles)
    DEVICE_MEMORY = "device_memory"  # Host specs, screen geometry, OS details
    APP_PREFERENCE = "app_preference"  # Default applications, browser configs
    USER_DEFINED_INFO = "user_defined_info"  # Explicit facts, aliases, custom notes


class PrivacyLevel(StrEnum):
    """Privacy classification for stored memory items."""

    PUBLIC = "public"  # Safe general info
    PRIVATE = "private"  # User-specific preferences
    SENSITIVE = "sensitive"  # Requires explicit permission and masking


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class MemoryRecord:
    """A discrete item stored in the NEXUS Memory System."""

    key: str
    value: Any
    category: MemoryCategory = MemoryCategory.USER_DEFINED_INFO
    id: str = field(default_factory=_new_id)
    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0  # 0.0 to 1.0
    created_at: str = field(default_factory=_utcnow_iso)
    updated_at: str = field(default_factory=_utcnow_iso)
    last_accessed: str = field(default_factory=_utcnow_iso)
    access_count: int = 0
    privacy_level: PrivacyLevel = PrivacyLevel.PRIVATE
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert memory record to dictionary."""
        data = asdict(self)
        data["category"] = str(self.category)
        data["privacy_level"] = str(self.privacy_level)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryRecord:
        """Create memory record from dictionary."""
        cat = MemoryCategory(data.get("category", MemoryCategory.USER_DEFINED_INFO))
        priv = PrivacyLevel(data.get("privacy_level", PrivacyLevel.PRIVATE))
        return cls(
            id=data.get("id", _new_id()),
            category=cat,
            key=data.get("key", ""),
            value=data.get("value"),
            tags=data.get("tags", []),
            confidence=float(data.get("confidence", 1.0)),
            created_at=data.get("created_at", _utcnow_iso()),
            updated_at=data.get("updated_at", _utcnow_iso()),
            last_accessed=data.get("last_accessed", _utcnow_iso()),
            access_count=int(data.get("access_count", 0)),
            privacy_level=priv,
            metadata=data.get("metadata", {}),
        )

    def record_access(self) -> None:
        """Increment access counter and update timestamp."""
        self.access_count += 1
        self.last_accessed = _utcnow_iso()


@dataclass
class ContextState:
    """Current dynamic context state for reference resolution."""

    active_app: str | None = None
    active_window_title: str | None = None
    last_mentioned_path: str | None = None
    last_mentioned_url: str | None = None
    last_search_query: str | None = None
    last_downloaded_file: str | None = None
    last_copied_text: str | None = None
    active_task_description: str | None = None
    active_task_steps: list[str] = field(default_factory=list)
    recent_entities: dict[str, str] = field(default_factory=dict)
