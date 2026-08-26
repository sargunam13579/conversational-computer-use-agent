"""
NEXUS API — Memory Endpoints.

Provides REST endpoints for:
- Creating, reading, querying, updating, and deleting memory records
- Memory search with keyword and category filtering
- Context reference resolution testing
- Memory statistics and privacy controls
"""

from __future__ import annotations

import contextlib
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from nexus.memory.manager import MemoryManager
from nexus.memory.types import MemoryCategory, PrivacyLevel

router = APIRouter(prefix="/memory", tags=["Memory & Context"])

_memory_manager = MemoryManager()


class CreateMemoryRequest(BaseModel):
    key: str
    value: Any
    category: str = "user_defined_info"
    tags: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    privacy_level: str = "private"


class UpdateMemoryRequest(BaseModel):
    value: Any | None = None
    tags: list[str] | None = None
    confidence: float | None = None
    privacy_level: str | None = None


class ContextResolveRequest(BaseModel):
    user_input: str
    recent_dialog_turns: list[str] = Field(default_factory=list)


class MemorySettingsRequest(BaseModel):
    enabled: bool


@router.get("/")
async def list_memories(
    category: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """List or search stored memory records."""
    cat_enum = None
    if category:
        try:
            cat_enum = MemoryCategory(category)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category '{category}'") from None

    records = await _memory_manager.search_memory(category=cat_enum, limit=limit)
    return {
        "count": len(records),
        "memories": [r.to_dict() for r in records],
    }


@router.post("/")
async def create_memory(req: CreateMemoryRequest) -> dict[str, Any]:
    """Create or update a memory record."""
    try:
        cat_enum = MemoryCategory(req.category)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid category '{req.category}'") from None

    try:
        priv_enum = PrivacyLevel(req.privacy_level)
    except ValueError:
        priv_enum = PrivacyLevel.PRIVATE

    record = await _memory_manager.store_memory(
        key=req.key,
        value=req.value,
        category=cat_enum,
        tags=req.tags,
        confidence=req.confidence,
        privacy_level=priv_enum,
    )

    if not record:
        raise HTTPException(status_code=400, detail="Memory storage is disabled")

    return {"success": True, "memory": record.to_dict()}


@router.get("/search")
async def search_memory(
    query: str = Query(default=""),
    category: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """Search memory records by keyword query."""
    cat_enum = None
    if category:
        with contextlib.suppress(ValueError):
            cat_enum = MemoryCategory(category)

    records = await _memory_manager.search_memory(query=query, category=cat_enum, limit=limit)
    return {
        "query": query,
        "count": len(records),
        "memories": [r.to_dict() for r in records],
    }


@router.get("/stats")
async def get_stats() -> dict[str, Any]:
    """Get memory system metrics and status."""
    return await _memory_manager.get_stats()


@router.post("/settings")
async def update_settings(req: MemorySettingsRequest) -> dict[str, Any]:
    """Enable or disable memory storage."""
    _memory_manager.set_enabled(req.enabled)
    return {"success": True, "enabled": req.enabled}


@router.post("/context/resolve")
async def resolve_context(req: ContextResolveRequest) -> dict[str, Any]:
    """Test contextual and anaphoric reference resolution."""
    resolved = await _memory_manager.resolver.resolve_reference(
        user_input=req.user_input,
        recent_dialog_turns=req.recent_dialog_turns,
    )
    return {"user_input": req.user_input, "resolved": resolved}


@router.get("/{record_id}")
async def get_memory(record_id: str) -> dict[str, Any]:
    """Retrieve single memory record by ID."""
    record = await _memory_manager.storage.get(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return {"memory": record.to_dict()}


@router.delete("/{record_id}")
async def delete_memory(record_id: str) -> dict[str, Any]:
    """Delete a memory record by ID."""
    deleted = await _memory_manager.delete_memory(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return {"success": True, "deleted_id": record_id}


@router.delete("/")
async def clear_memories(category: str | None = None) -> dict[str, Any]:
    """Clear all memories or memories in a specific category."""
    cat_enum = None
    if category:
        try:
            cat_enum = MemoryCategory(category)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category '{category}'") from None

    count = await _memory_manager.clear_memory(category=cat_enum)
    return {"success": True, "cleared_count": count, "category": category}
