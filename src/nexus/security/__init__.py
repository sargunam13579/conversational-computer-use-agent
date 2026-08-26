"""
NEXUS Security Package.

Provides authentication, cryptography & secret vault, device pairing,
granular permission scopes, terminal command safety, and audit logging.
"""

from nexus.security.audit import AuditLogger
from nexus.security.auth import AuthManager, RateLimitWindow
from nexus.security.crypto import KeyManager, SecretEntry, SecretVault
from nexus.security.pairing import DevicePairingManager, PairedDevice, PairingSession
from nexus.security.permissions import (
    PermissionAction,
    PermissionEngine,
    PermissionScope,
    PermissionScopeManager,
    ScopeStatus,
)
from nexus.security.terminal_security import (
    CommandAnalysisResult,
    CommandSafetyStatus,
    TerminalSecurityClassifier,
)

__all__ = [
    "AuditLogger",
    "AuthManager",
    "RateLimitWindow",
    "KeyManager",
    "SecretEntry",
    "SecretVault",
    "DevicePairingManager",
    "PairedDevice",
    "PairingSession",
    "PermissionAction",
    "PermissionEngine",
    "PermissionScope",
    "PermissionScopeManager",
    "ScopeStatus",
    "CommandAnalysisResult",
    "CommandSafetyStatus",
    "TerminalSecurityClassifier",
]
