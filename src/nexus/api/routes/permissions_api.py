"""
NEXUS Permissions REST API Router.

Provides endpoints for inspecting, granting, and revoking capability permission scopes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from nexus.security.permissions import PermissionScopeManager

router = APIRouter(prefix="/permissions", tags=["permissions"])

_scope_manager = PermissionScopeManager()


class GrantScopeRequest(BaseModel):
    scope: str = Field(..., description="The permission scope to grant")


class RevokeScopeRequest(BaseModel):
    scope: str = Field(..., description="The permission scope to revoke")


@router.get("", summary="List all permission scopes")
async def list_permissions() -> dict[str, Any]:
    """Get the current grant status of all capability permission scopes."""
    scopes = _scope_manager.list_scopes()
    return {
        "scopes": {k: {"scope": v.scope, "granted": v.granted, "description": v.description} for k, v in scopes.items()}
    }


@router.post("/grant", summary="Grant a permission scope")
async def grant_permission(req: GrantScopeRequest) -> dict[str, Any]:
    """Explicitly grant a capability permission scope."""
    _scope_manager.grant_scope(req.scope)
    return {
        "success": True,
        "scope": req.scope,
        "granted": True,
        "message": f"Permission scope '{req.scope}' granted successfully.",
    }


@router.post("/revoke", summary="Revoke a permission scope")
async def revoke_permission(req: RevokeScopeRequest) -> dict[str, Any]:
    """Explicitly revoke a capability permission scope."""
    _scope_manager.revoke_scope(req.scope)
    return {
        "success": True,
        "scope": req.scope,
        "granted": False,
        "message": f"Permission scope '{req.scope}' revoked.",
    }


@router.post("/reset", summary="Reset permissions to defaults")
async def reset_permissions() -> dict[str, Any]:
    """Reset all capability scopes to default granted state."""
    _scope_manager.reset_defaults()
    return {"success": True, "message": "All permission scopes reset to defaults."}
