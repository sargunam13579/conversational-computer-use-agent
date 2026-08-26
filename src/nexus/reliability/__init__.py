"""
NEXUS Reliability Package.

Provides offline fallback mode, deterministic local command processing,
and automatic connection recovery with exponential backoff.
"""

from nexus.reliability.connection_recovery import ConnectionRecoveryManager, ConnectionState
from nexus.reliability.offline import LocalCommandResult, OfflineModeManager

__all__ = [
    "OfflineModeManager",
    "LocalCommandResult",
    "ConnectionRecoveryManager",
    "ConnectionState",
]
