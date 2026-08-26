"""
NEXUS Memory Storage Engine.

Provides persistent, thread-safe memory storage with category indexing,
keyword search, tag filtering, and JSON/SQLite persistence.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from nexus.core.config import get_settings
from nexus.memory.privacy import MemoryPrivacyFilter
from nexus.memory.types import MemoryCategory, MemoryRecord, PrivacyLevel
from nexus.utils.logging import get_logger

log = get_logger("memory.storage")


class MemoryStorage:
    """Persistent storage engine for NEXUS memory records."""

    def __init__(
        self,
        storage_path: Path | str | None = None,
        privacy_filter: MemoryPrivacyFilter | None = None,
    ) -> None:
        if storage_path:
            self._path = Path(storage_path).expanduser().resolve()
        else:
            settings = get_settings()
            self._path = settings.resolved_data_dir / "nexus_memory.json"

        self._privacy_filter = privacy_filter or MemoryPrivacyFilter()
        self._records: dict[str, MemoryRecord] = {}  # id -> record
        self._lock = asyncio.Lock()
        self._loaded = False
        self._enabled = True

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def _ensure_dir(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> None:
        """Load records synchronously from disk."""
        if not self._path.exists():
            self._records = {}
            self._loaded = True
            return

        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            self._records = {
                item["id"]: MemoryRecord.from_dict(item)
                for item in data.get("records", [])
                if "id" in item
            }
            self._loaded = True
            log.info("Loaded %d memory records from %s", len(self._records), self._path)
        except Exception as e:
            log.warning("Could not load memory file '%s': %s", self._path, e)
            self._records = {}
            self._loaded = True

    async def ensure_loaded(self) -> None:
        """Ensure memory records are loaded into cache."""
        if not self._loaded:
            self.load()

    def save(self) -> None:
        """Save records to disk."""
        try:
            self._ensure_dir()
            payload = {
                "version": "1.0",
                "total": len(self._records),
                "records": [r.to_dict() for r in self._records.values()],
            }
            temp_path = self._path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temp_path.replace(self._path)
        except Exception as e:
            log.error("Failed to save memory records to %s: %s", self._path, e)

    async def store(
        self,
        key: str,
        value: Any,
        category: MemoryCategory = MemoryCategory.USER_DEFINED_INFO,
        tags: list[str] | None = None,
        confidence: float = 1.0,
        privacy_level: PrivacyLevel = PrivacyLevel.PRIVATE,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord | None:
        """Store or update a memory record."""
        if not self._enabled:
            log.debug("Memory storage is disabled; skipping store.")
            return None

        await self.ensure_loaded()

        # Sanitize sensitive data
        clean_key = self._privacy_filter.sanitize(key.strip())
        clean_value = self._privacy_filter.sanitize_value(value)

        async with self._lock:
            # Check if record with matching key & category already exists
            existing_id = None
            for rec in self._records.values():
                if rec.category == category and rec.key.lower() == clean_key.lower():
                    existing_id = rec.id
                    break

            if existing_id:
                record = self._records[existing_id]
                record.value = clean_value
                if tags:
                    record.tags = list(set(record.tags + tags))
                record.confidence = confidence
                record.privacy_level = privacy_level
                if metadata:
                    record.metadata.update(metadata)
                record.updated_at = record.created_at  # Will be refreshed below
                record.record_access()
            else:
                record = MemoryRecord(
                    key=clean_key,
                    value=clean_value,
                    category=category,
                    tags=tags or [],
                    confidence=confidence,
                    privacy_level=privacy_level,
                    metadata=metadata or {},
                )
                self._records[record.id] = record

            self.save()
            log.info("Stored memory [%s] '%s'", category.value, clean_key)
            return record

    async def get(self, record_id: str) -> MemoryRecord | None:
        """Retrieve a record by ID."""
        await self.ensure_loaded()
        async with self._lock:
            rec = self._records.get(record_id)
            if rec:
                rec.record_access()
                self.save()
            return rec

    async def find_by_key(
        self,
        key: str,
        category: MemoryCategory | None = None,
    ) -> MemoryRecord | None:
        """Find a single record matching key and optional category."""
        await self.ensure_loaded()
        clean_key = key.lower().strip()

        async with self._lock:
            for rec in self._records.values():
                if category and rec.category != category:
                    continue
                if rec.key.lower() == clean_key:
                    rec.record_access()
                    self.save()
                    return rec
            return None

    async def search(
        self,
        query: str = "",
        category: MemoryCategory | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
    ) -> list[MemoryRecord]:
        """Search memory records by query keywords, category, or tags."""
        await self.ensure_loaded()
        q_clean = query.lower().strip()
        tag_set = {t.lower().strip() for t in (tags or [])}

        results: list[MemoryRecord] = []
        async with self._lock:
            for rec in self._records.values():
                if category and rec.category != category:
                    continue

                if tag_set and not any(t.lower() in tag_set for t in rec.tags):
                    continue

                if q_clean:
                    val_str = str(rec.value).lower()
                    key_str = rec.key.lower()
                    tag_str = " ".join(rec.tags).lower()

                    if q_clean in key_str or q_clean in val_str or q_clean in tag_str:
                        results.append(rec)
                else:
                    results.append(rec)

                if len(results) >= limit:
                    break

        return results

    async def list_by_category(self, category: MemoryCategory) -> list[MemoryRecord]:
        """List all memories in a category."""
        return await self.search(category=category, limit=100)

    async def delete(self, record_id_or_key: str) -> bool:
        """Delete a record by ID or exact key."""
        await self.ensure_loaded()
        async with self._lock:
            # Try by ID first
            if record_id_or_key in self._records:
                del self._records[record_id_or_key]
                self.save()
                return True

            # Try by key
            clean_key = record_id_or_key.lower().strip()
            to_delete = [r.id for r in self._records.values() if r.key.lower() == clean_key]
            if to_delete:
                for rid in to_delete:
                    del self._records[rid]
                self.save()
                return True

            return False

    async def clear(self, category: MemoryCategory | None = None) -> int:
        """Clear memories, optionally restricted to a specific category."""
        await self.ensure_loaded()
        async with self._lock:
            if category:
                to_remove = [r.id for r in self._records.values() if r.category == category]
                for rid in to_remove:
                    del self._records[rid]
                count = len(to_remove)
            else:
                count = len(self._records)
                self._records.clear()

            self.save()
            log.info("Cleared %d memory records (category=%s)", count, category)
            return count

    async def get_stats(self) -> dict[str, Any]:
        """Get summary statistics of stored memories."""
        await self.ensure_loaded()
        counts: dict[str, int] = {}
        for cat in MemoryCategory:
            counts[cat.value] = sum(1 for r in self._records.values() if r.category == cat)

        return {
            "total_records": len(self._records),
            "enabled": self._enabled,
            "categories": counts,
        }
