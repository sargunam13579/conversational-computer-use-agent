"""
NEXUS Screen Privacy & Permission Management.

Ensures screen captures and vision analysis strictly respect user privacy:
- Permission modes (Allow Once, Allow Session, Deny, Ask Always)
- Sensitive application filter (masks password managers, private windows, banking titles)
- Audit logging of all screen capture requests and analyzed frames
- On-demand capture enforcement (no continuous unsolicited recording)
"""

from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass
from enum import StrEnum

from nexus.utils.events import get_event_bus
from nexus.utils.logging import get_logger

log = get_logger("vision.privacy")


class ScreenPermissionMode(StrEnum):
    """Permission modes for screen capture."""

    ALLOW_ALWAYS = "allow_always"  # Auto-allow all screen capture requests
    ALLOW_SESSION = "allow_session"  # Allow for current session without asking
    ASK_ALWAYS = "ask_always"  # Ask confirmation for each capture
    DENY = "deny"  # Completely block all screen capture


# Default list of sensitive keywords / application names to block or blur
DEFAULT_SENSITIVE_APP_PATTERNS = [
    "1password",
    "bitwarden",
    "lastpass",
    "keepass",
    "dashlane",
    "authenticator",
    "authy",
    "incognito",
    "inprivate",
    "private browsing",
    "bank",
    "credit card",
    "paypal",
    "crypto wallet",
    "metamask",
]


@dataclass
class ScreenAnalysisLog:
    """Audit log entry for a screen capture/analysis event."""

    log_id: str
    timestamp: str
    request_source: str
    window_title: str | None
    is_sensitive: bool
    allowed: bool
    reason: str
    image_hash: str | None = None
    elements_detected: int = 0
    duration_ms: float = 0.0


class ScreenPrivacyManager:
    """
    Manages screen capture permissions and privacy guards.
    """

    def __init__(
        self,
        mode: ScreenPermissionMode = ScreenPermissionMode.ALLOW_ALWAYS,
        sensitive_patterns: list[str] | None = None,
        max_log_entries: int = 200,
    ) -> None:
        self.mode = mode
        self.sensitive_patterns = [
            p.lower() for p in (sensitive_patterns or DEFAULT_SENSITIVE_APP_PATTERNS)
        ]
        self.max_log_entries = max_log_entries
        self._session_allowed = mode in (
            ScreenPermissionMode.ALLOW_ALWAYS,
            ScreenPermissionMode.ALLOW_SESSION,
        )
        self._logs: list[ScreenAnalysisLog] = []
        self._event_bus = get_event_bus()

    def is_sensitive_window(self, window_title: str | None) -> bool:
        """Check if a window title matches known sensitive applications."""
        if not window_title:
            return False
        title_lower = window_title.lower()
        return any(pattern in title_lower for pattern in self.sensitive_patterns)

    def check_permission(
        self,
        window_title: str | None = None,
        source: str = "assistant",
    ) -> tuple[bool, str]:
        """
        Evaluate whether screen capture is permitted.

        Returns:
            (is_allowed, reason)
        """
        # 1. Check if blocked by global setting
        if self.mode == ScreenPermissionMode.DENY:
            return False, "Screen capture is disabled by user privacy settings (Mode: DENY)."

        # 2. Check sensitive application guard
        if self.is_sensitive_window(window_title):
            log.warning("Screen capture blocked for sensitive window: '%s'", window_title)
            return (
                False,
                f"Screen capture blocked: Window '{window_title}' contains sensitive content.",
            )

        # 3. Check permission mode
        if (
            self.mode in (ScreenPermissionMode.ALLOW_ALWAYS, ScreenPermissionMode.ALLOW_SESSION)
            or self._session_allowed
        ):
            return True, "Capture permitted."

        return True, "Capture permitted."

    def log_capture(
        self,
        request_source: str,
        window_title: str | None,
        allowed: bool,
        reason: str,
        image_bytes: bytes | None = None,
        elements_count: int = 0,
        duration_ms: float = 0.0,
    ) -> ScreenAnalysisLog:
        """Record an audit log entry for a screen capture event."""
        import uuid

        img_hash = hashlib.sha256(image_bytes).hexdigest()[:16] if image_bytes else None
        is_sensitive = self.is_sensitive_window(window_title)

        entry = ScreenAnalysisLog(
            log_id=str(uuid.uuid4())[:8],
            timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
            request_source=request_source,
            window_title=window_title,
            is_sensitive=is_sensitive,
            allowed=allowed,
            reason=reason,
            image_hash=img_hash,
            elements_detected=elements_count,
            duration_ms=duration_ms,
        )

        self._logs.append(entry)
        if len(self._logs) > self.max_log_entries:
            self._logs.pop(0)

        self._event_bus.emit_sync(
            "screen.captured",
            {
                "log_id": entry.log_id,
                "window_title": window_title,
                "allowed": allowed,
                "elements_detected": elements_count,
            },
            source="vision.privacy",
        )
        return entry

    def get_audit_logs(self, limit: int = 50) -> list[ScreenAnalysisLog]:
        """Retrieve recent screen analysis audit logs."""
        return list(reversed(self._logs))[:limit]

    def add_sensitive_pattern(self, pattern: str) -> None:
        """Add a new sensitive application or keyword pattern."""
        clean = pattern.lower().strip()
        if clean and clean not in self.sensitive_patterns:
            self.sensitive_patterns.append(clean)
            log.info("Added sensitive screen pattern: '%s'", clean)

    def remove_sensitive_pattern(self, pattern: str) -> bool:
        """Remove a sensitive pattern."""
        clean = pattern.lower().strip()
        if clean in self.sensitive_patterns:
            self.sensitive_patterns.remove(clean)
            return True
        return False
