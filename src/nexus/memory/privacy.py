"""
NEXUS Memory Privacy & Sensitive Data Filter.

Prevents unauthorized storage of passwords, API keys, bearer tokens,
credit cards, private keys, and sensitive PII.
"""

from __future__ import annotations

import re
from typing import Any

from nexus.utils.logging import get_logger

log = get_logger("memory.privacy")

# Regex patterns detecting sensitive credentials and secrets
_SENSITIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OPENAI_API_KEY", re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE)),
    ("GITHUB_TOKEN", re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}", re.IGNORECASE)),
    ("AWS_ACCESS_KEY", re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE)),
    ("BEARER_TOKEN", re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE)),
    ("PRIVATE_KEY", re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----", re.IGNORECASE)),
    (
        "PASSWORD_FIELD",
        re.compile(
            r"(?:password|passwd|pwd|secret|api_key|apikey)\s*[:=]\s*['\"]?([^\s'\"]{6,})['\"]?",
            re.IGNORECASE,
        ),
    ),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
]


class MemoryPrivacyFilter:
    """Detects and redacts sensitive data before memory persistence."""

    def __init__(self, redact_in_place: bool = True) -> None:
        self._redact = redact_in_place

    def contains_sensitive_data(self, text: str) -> bool:
        """Check if string contains potential sensitive credentials or PII."""
        if not text or not isinstance(text, str):
            return False
        return any(pattern.search(text) for _, pattern in _SENSITIVE_PATTERNS)

    def sanitize(self, text: str) -> str:
        """Scrub sensitive patterns from text, replacing with redaction markers."""
        if not text or not isinstance(text, str):
            return text

        sanitized = text
        for label, pattern in _SENSITIVE_PATTERNS:
            if label == "PASSWORD_FIELD":
                sanitized = pattern.sub(r"password: [REDACTED]", sanitized)
            else:
                sanitized = pattern.sub(f"[{label}_REDACTED]", sanitized)
        return sanitized

    def sanitize_value(self, value: Any) -> Any:
        """Recursively sanitize string, dict, or list values."""
        if isinstance(value, str):
            return self.sanitize(value)
        elif isinstance(value, dict):
            return {k: self.sanitize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.sanitize_value(item) for item in value]
        return value
