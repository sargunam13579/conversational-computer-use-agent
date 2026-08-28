"""
NEXUS API — Supabase Authentication Routes.

Provides endpoints for verifying user authentication status, fetching user
profile info from Supabase JWT tokens, and managing user auth state.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from nexus.core.config import NexusSettings, get_settings
from nexus.security.supabase_auth import SupabaseUser, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/me")
async def get_auth_me(
    user: SupabaseUser = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Return the current authenticated Supabase user profile.

    Decodes and verifies the JWT token from the Authorization header.
    """
    return {
        "authenticated": True,
        "user_id": user.user_id,
        "email": user.email,
        "role": user.role,
        "aud": user.aud,
        "user_metadata": user.user_metadata,
    }


@router.get("/status")
async def get_auth_status(request: Request) -> dict[str, Any]:
    """
    Return the Supabase Auth system status and configuration state.
    """
    settings: NexusSettings = getattr(request.app.state, "settings", get_settings())

    has_supabase_url = bool(settings.supabase_url or settings.security.supabase_url)
    has_jwt_secret = bool(
        settings.supabase_jwt_secret
        or settings.supabase_service_role_key
        or settings.security.supabase_jwt_secret
    )

    return {
        "provider": "supabase",
        "configured": has_supabase_url,
        "require_auth": settings.security.require_auth,
        "supabase_url": settings.supabase_url or settings.security.supabase_url,
        "jwt_verification_enabled": has_jwt_secret,
        "status": "ready" if has_supabase_url else "missing_configuration",
    }
