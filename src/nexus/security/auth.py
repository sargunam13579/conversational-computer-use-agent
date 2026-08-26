"""
NEXUS API Authentication & Rate Limiting Subsystem.

Provides API key validation, session token authentication,
and per-client rate limiting security guards.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from nexus.security.crypto import KeyManager
from nexus.utils.logging import get_logger

log = get_logger("security.auth")


@dataclass
class RateLimitWindow:
    """Sliding rate limit window tracking request counts."""

    max_requests: int = 120
    window_seconds: float = 60.0
    timestamps: list[float] = field(default_factory=list)

    def is_allowed(self) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        self.timestamps = [t for t in self.timestamps if t > cutoff]
        if len(self.timestamps) >= self.max_requests:
            return False
        self.timestamps.append(now)
        return True


class AuthManager:
    """
    Manages API keys, session tokens, and security rate limits.
    """

    def __init__(self, master_api_key: str | None = None) -> None:
        self._master_api_key = master_api_key
        self._valid_api_keys: set[str] = set()
        if master_api_key:
            self._valid_api_keys.add(master_api_key)
        self._active_sessions: dict[str, float] = {}  # token -> expires_at
        self._rate_limiters: dict[str, RateLimitWindow] = {}

    def create_api_key(self, prefix: str = "nx") -> str:
        """Generate a new secure API key."""
        token = KeyManager.generate_token(32)
        key = f"{prefix}_{token}"
        self._valid_api_keys.add(key)
        return key

    def revoke_api_key(self, api_key: str) -> bool:
        """Revoke an existing API key."""
        if api_key in self._valid_api_keys:
            self._valid_api_keys.remove(api_key)
            return True
        return False

    def validate_api_key(self, api_key: str | None) -> bool:
        """Check if an API key is valid."""
        if not api_key:
            return False
        return api_key in self._valid_api_keys

    def create_session_token(self, ttl_seconds: float = 3600.0) -> str:
        """Generate a time-limited session token."""
        token = KeyManager.generate_token(24)
        self._active_sessions[token] = time.time() + ttl_seconds
        return token

    def validate_session_token(self, token: str | None) -> bool:
        """Check if a session token is valid and not expired."""
        if not token or token not in self._active_sessions:
            return False
        expires_at = self._active_sessions[token]
        if time.time() > expires_at:
            del self._active_sessions[token]
            return False
        return True

    def check_rate_limit(self, client_id: str, max_requests: int = 120, window_seconds: float = 60.0) -> bool:
        """Check if a client has exceeded their rate limit window."""
        if client_id not in self._rate_limiters:
            self._rate_limiters[client_id] = RateLimitWindow(
                max_requests=max_requests, window_seconds=window_seconds
            )
        return self._rate_limiters[client_id].is_allowed()
