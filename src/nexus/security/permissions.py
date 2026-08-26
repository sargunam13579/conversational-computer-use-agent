"""
NEXUS Permission Engine & Permission Scope Subsystem.

Checks whether tool actions and hardware capabilities are allowed based on
risk level and user-configured permission scopes.
Enables users to view, grant, and revoke permissions at any time.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path

from nexus.core.config import NexusSettings, get_settings
from nexus.tools.base import RiskLevel
from nexus.utils.logging import get_logger

log = get_logger("security.permissions")


class PermissionScope(StrEnum):
    """Explicit capability scopes that can be granted or revoked."""

    MICROPHONE = "microphone"
    CAMERA = "camera"
    SCREEN_CAPTURE = "screen_capture"
    FILE_ACCESS = "file_access"
    NOTIFICATIONS = "notifications"
    ACCESSIBILITY = "accessibility"
    DEVICE_CONTROL = "device_control"


class PermissionAction:
    """Possible permission actions."""

    AUTO = "auto"  # Execute without asking
    CONFIRM = "confirm"  # Ask user for confirmation
    DENY = "deny"  # Block the action


@dataclass
class ScopeStatus:
    """Status metadata for an individual permission scope."""

    scope: str
    granted: bool
    description: str
    granted_at: float | None = None
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, str] = field(default_factory=dict)


# Default descriptions for each capability scope
_DEFAULT_SCOPE_DESCRIPTIONS: dict[PermissionScope, str] = {
    PermissionScope.MICROPHONE: "Access microphone for voice recording and continuous speech recognition.",
    PermissionScope.CAMERA: "Access webcam and camera devices for visual processing and OCR.",
    PermissionScope.SCREEN_CAPTURE: "Capture desktop and application screen for multimodal vision analysis.",
    PermissionScope.FILE_ACCESS: "Read, write, convert, and manage local filesystem files and directories.",
    PermissionScope.NOTIFICATIONS: "Display system notifications and alert banners to the user.",
    PermissionScope.ACCESSIBILITY: "Automate keyboard/mouse inputs, inspect UI trees, and manage hands-free mode.",
    PermissionScope.DEVICE_CONTROL: "Control connected Android phones, launch applications, and send cross-device files.",
}

# Tool to Scope mapping
_TOOL_SCOPE_MAP: dict[str, PermissionScope] = {
    "voice_record": PermissionScope.MICROPHONE,
    "speech_to_text": PermissionScope.MICROPHONE,
    "capture_camera": PermissionScope.CAMERA,
    "take_photo": PermissionScope.CAMERA,
    "screen_capture": PermissionScope.SCREEN_CAPTURE,
    "screen_ocr": PermissionScope.SCREEN_CAPTURE,
    "find_files": PermissionScope.FILE_ACCESS,
    "read_file": PermissionScope.FILE_ACCESS,
    "write_file": PermissionScope.FILE_ACCESS,
    "convert_document": PermissionScope.FILE_ACCESS,
    "rename_file": PermissionScope.FILE_ACCESS,
    "send_notification": PermissionScope.NOTIFICATIONS,
    "click_element": PermissionScope.ACCESSIBILITY,
    "type_text": PermissionScope.ACCESSIBILITY,
    "press_hotkey": PermissionScope.ACCESSIBILITY,
    "android_adb": PermissionScope.DEVICE_CONTROL,
    "transfer_file": PermissionScope.DEVICE_CONTROL,
    "launch_app": PermissionScope.DEVICE_CONTROL,
}


class PermissionScopeManager:
    """
    Manages and persists granular permission scopes for NEXUS.
    Enables checking, granting, and revoking permissions dynamically.
    """

    def __init__(self, storage_path: str | Path | None = None) -> None:
        if storage_path is None:
            home = Path.home()
            self.storage_path = home / ".nexus" / "permissions.json"
        else:
            self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._scopes: dict[str, ScopeStatus] = {}
        self._initialize_scopes()
        self._load()

    def _initialize_scopes(self) -> None:
        """Initialize all default scopes with granted status by default."""
        for scope in PermissionScope:
            self._scopes[scope.value] = ScopeStatus(
                scope=scope.value,
                granted=True,  # Default to granted on install
                description=_DEFAULT_SCOPE_DESCRIPTIONS[scope],
                granted_at=time.time(),
            )

    def _load(self) -> None:
        if not self.storage_path.exists():
            self._save()
            return
        try:
            raw = self.storage_path.read_text(encoding="utf-8")
            if not raw.strip():
                return
            data = json.loads(raw)
            for item in data.get("scopes", []):
                s = ScopeStatus(**item)
                self._scopes[s.scope] = s
        except Exception as e:
            log.warning("Could not load permissions from disk: %s", e)

    def _save(self) -> None:
        try:
            payload = {
                "version": "1.0",
                "updated_at": time.time(),
                "scopes": [asdict(s) for s in self._scopes.values()],
            }
            self.storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            if os.name != "nt":
                os.chmod(self.storage_path, 0o600)
        except Exception as e:
            log.error("Failed to save permissions: %s", e)

    def is_scope_granted(self, scope: PermissionScope | str) -> bool:
        """Check if a capability scope is currently granted."""
        scope_str = scope.value if isinstance(scope, PermissionScope) else str(scope)
        status = self._scopes.get(scope_str)
        if status is None:
            # Unknown scope default to False for safety
            return False
        return status.granted

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool's required capability scope is granted."""
        scope = _TOOL_SCOPE_MAP.get(tool_name)
        if scope is None:
            # Tool has no explicit capability constraint
            return True
        return self.is_scope_granted(scope)

    def grant_scope(self, scope: PermissionScope | str) -> None:
        """Grant a capability scope."""
        scope_str = scope.value if isinstance(scope, PermissionScope) else str(scope)
        if scope_str in self._scopes:
            self._scopes[scope_str].granted = True
            self._scopes[scope_str].granted_at = time.time()
            self._scopes[scope_str].updated_at = time.time()
        else:
            self._scopes[scope_str] = ScopeStatus(
                scope=scope_str,
                granted=True,
                description=f"Custom permission scope: {scope_str}",
                granted_at=time.time(),
            )
        self._save()
        log.info("Granted permission scope: %s", scope_str)

    def revoke_scope(self, scope: PermissionScope | str) -> None:
        """Revoke a capability scope."""
        scope_str = scope.value if isinstance(scope, PermissionScope) else str(scope)
        if scope_str in self._scopes:
            self._scopes[scope_str].granted = False
            self._scopes[scope_str].updated_at = time.time()
        else:
            self._scopes[scope_str] = ScopeStatus(
                scope=scope_str,
                granted=False,
                description=f"Custom permission scope: {scope_str}",
                granted_at=None,
            )
        self._save()
        log.warning("Revoked permission scope: %s", scope_str)

    def list_scopes(self) -> dict[str, ScopeStatus]:
        """List all permission scopes and their current status."""
        return dict(self._scopes)

    def reset_defaults(self) -> None:
        """Reset all capability scopes to default granted state."""
        self._initialize_scopes()
        self._save()


class PermissionEngine:
    """
    Checks whether a tool action is allowed.

    Uses the risk-based permission model from the configuration, with
    optional per-tool overrides from the database, combined with scope validation.
    """

    def __init__(
        self,
        settings: NexusSettings | None = None,
        scope_manager: PermissionScopeManager | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._scope_manager = scope_manager or PermissionScopeManager()

    @property
    def scope_manager(self) -> PermissionScopeManager:
        return self._scope_manager

    def check_permission(
        self,
        tool_name: str,
        risk_level: RiskLevel,
        custom_rules: dict[str, str] | None = None,
    ) -> str:
        """
        Check the permission for a tool action.
        """
        # 1. Check if the capability scope for this tool is revoked
        if not self._scope_manager.is_tool_allowed(tool_name):
            log.warning("Tool %s blocked due to revoked capability scope", tool_name)
            return PermissionAction.DENY

        # 2. Check custom rules first (per-tool overrides)
        if custom_rules and tool_name in custom_rules:
            action = custom_rules[tool_name]
            log.debug("Custom rule for %s: %s", tool_name, action)
            return action

        # 3. Fall back to risk-level-based defaults
        perm_cfg = self._settings.security.permissions
        risk_map = {
            RiskLevel.LOW: perm_cfg.low_risk,
            RiskLevel.MEDIUM: perm_cfg.medium_risk,
            RiskLevel.HIGH: perm_cfg.high_risk,
            RiskLevel.CRITICAL: perm_cfg.critical_risk,
        }

        action = risk_map.get(risk_level, PermissionAction.CONFIRM)
        log.debug(
            "Permission check: tool=%s, risk=%s → %s",
            tool_name,
            risk_level.value,
            action,
        )
        return action

    def is_allowed(self, tool_name: str, risk_level: RiskLevel) -> bool:
        """Quick check: is this tool auto-approved?"""
        return self.check_permission(tool_name, risk_level) != PermissionAction.DENY

    def requires_confirmation(self, tool_name: str, risk_level: RiskLevel) -> bool:
        """Check if this tool needs user confirmation."""
        return self.check_permission(tool_name, risk_level) == PermissionAction.CONFIRM
