"""
NEXUS Android Agent Security & Authentication Manager.

Handles pairing code generation, HMAC-SHA256 message signing, token validation,
and permission enforcement.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import string
import time
from typing import Any

from nexus.utils.logging import get_logger

log = get_logger("agents.android.security")


class AndroidSecurityManager:
    """Security, authentication, and pairing management for Android devices."""

    def __init__(self, secret_key: str | None = None) -> None:
        self._secret = secret_key or secrets.token_hex(32)
        # code -> {expires_at, ...}
        self._active_pairing_codes: dict[str, dict[str, Any]] = {}
        # device_id -> {token, name, paired_at}
        self._paired_devices: dict[str, dict[str, Any]] = {}

    @property
    def paired_devices(self) -> dict[str, dict[str, Any]]:
        return self._paired_devices

    def generate_pairing_code(self, expiry_seconds: int = 300) -> str:
        """Generate a secure 6-character alphanumeric pairing code."""
        chars = string.ascii_uppercase + string.digits
        # Avoid ambiguous characters (0, O, 1, I)
        safe_chars = "".join(c for c in chars if c not in "0O1I")
        code = "".join(secrets.choice(safe_chars) for _ in range(6))

        self._active_pairing_codes[code] = {
            "expires_at": time.time() + expiry_seconds,
            "created_at": time.time(),
        }
        log.info("Generated Android pairing code: %s (expires in %ds)", code, expiry_seconds)
        return code

    def verify_pairing_code(
        self,
        code: str,
        device_id: str,
        device_name: str,
    ) -> str | None:
        """
        Verify pairing code and issue persistent authentication token for device.
        """
        clean_code = code.strip().upper()
        entry = self._active_pairing_codes.get(clean_code)

        if not entry:
            log.warning("Invalid pairing code attempt: %s", clean_code)
            return None

        if time.time() > entry["expires_at"]:
            log.warning("Expired pairing code: %s", clean_code)
            del self._active_pairing_codes[clean_code]
            return None

        # Pairing successful — generate auth token
        del self._active_pairing_codes[clean_code]
        auth_token = secrets.token_urlsafe(32)

        self._paired_devices[device_id] = {
            "device_id": device_id,
            "device_name": device_name,
            "token": auth_token,
            "paired_at": time.time(),
        }
        log.info("Device '%s' (%s) successfully paired.", device_name, device_id)
        return auth_token

    def is_device_authorized(self, device_id: str, token: str) -> bool:
        """Check if device is paired and token matches."""
        device = self._paired_devices.get(device_id)
        if not device:
            return False
        return hmac.compare_digest(device["token"], token)

    def sign_payload(self, payload_bytes: bytes) -> str:
        """Generate HMAC-SHA256 signature for message payload."""
        return hmac.new(
            self._secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

    def verify_signature(self, payload_bytes: bytes, signature: str) -> bool:
        """Verify HMAC-SHA256 signature."""
        expected = self.sign_payload(payload_bytes)
        return hmac.compare_digest(expected, signature)

    def unpair_device(self, device_id: str) -> bool:
        """Remove paired device."""
        if device_id in self._paired_devices:
            del self._paired_devices[device_id]
            log.info("Unpaired Android device: %s", device_id)
            return True
        return False
