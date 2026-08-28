"""
NEXUS Security — Supabase Authentication & JWT Verification Subsystem.

Provides JWT token decoding, signature validation against Supabase JWT secret,
and FastAPI dependencies for protecting REST API endpoints.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from nexus.core.config import NexusSettings, get_settings
from nexus.utils.logging import get_logger

log = get_logger("security.supabase_auth")

security_bearer = HTTPBearer(auto_error=False)


class SupabaseUser:
    """Represents an authenticated Supabase user context."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.user_id: str = payload.get("sub", "")
        self.email: str = payload.get("email", "")
        self.role: str = payload.get("role", "authenticated")
        self.aud: str = payload.get("aud", "")
        self.app_metadata: dict[str, Any] = payload.get("app_metadata", {})
        self.user_metadata: dict[str, Any] = payload.get("user_metadata", {})
        self.exp: int = payload.get("exp", 0)

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.exp

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "role": self.role,
            "aud": self.aud,
            "user_metadata": self.user_metadata,
        }


def decode_supabase_jwt(
    token: str,
    secret: str = "",
    verify_signature: bool = True,
) -> Optional[dict[str, Any]]:
    """
    Decode and verify a Supabase JWT token.

    Args:
        token: The raw JWT string from Authorization Bearer header.
        secret: The SUPABASE_JWT_SECRET or SUPABASE_SERVICE_ROLE_KEY.
        verify_signature: If True and secret is provided, validates signature.

    Returns:
        Decoded payload dictionary or None if invalid.
    """
    try:
        if secret and verify_signature:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_aud": True},
            )
        else:
            # Decode without signature check if secret is not configured yet in local dev
            payload = jwt.decode(
                token,
                options={"verify_signature": False},
            )
        return payload
    except jwt.ExpiredSignatureError:
        log.warning("Supabase JWT token has expired")
        return None
    except jwt.InvalidTokenError as e:
        log.warning("Invalid Supabase JWT token: %s", e)
        return None
    except Exception as e:
        log.error("Unexpected error parsing Supabase JWT: %s", e)
        return None


def verify_supabase_token(token: str, settings: Optional[NexusSettings] = None) -> Optional[SupabaseUser]:
    """
    Verify token and return a SupabaseUser object.
    """
    if not settings:
        settings = get_settings()

    jwt_secret = settings.supabase_jwt_secret or settings.supabase_service_role_key
    payload = decode_supabase_jwt(
        token,
        secret=jwt_secret,
        verify_signature=bool(jwt_secret),
    )

    if not payload:
        return None

    user = SupabaseUser(payload)
    if user.is_expired:
        return None

    return user


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> SupabaseUser:
    """
    FastAPI dependency to extract and verify the current authenticated Supabase user.

    Raises:
        HTTPException 401 if authentication fails and require_auth is enabled.
    """
    settings: NexusSettings = getattr(request.app.state, "settings", get_settings())

    if not credentials or not credentials.credentials:
        if settings.security.require_auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authorization bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Development fallback mock user when require_auth is False
        return SupabaseUser({
            "sub": "local-dev-user-0000",
            "email": "dev@nexus.local",
            "role": "authenticated",
            "aud": "authenticated",
        })

    token = credentials.credentials
    user = verify_supabase_token(token, settings=settings)

    if not user:
        if settings.security.require_auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return SupabaseUser({
            "sub": "local-dev-user-0000",
            "email": "dev@nexus.local",
            "role": "authenticated",
            "aud": "authenticated",
        })

    return user
