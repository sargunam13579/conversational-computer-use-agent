"""
NEXUS Automation Package.

Provides active application tracking, native UI interaction, error recovery,
and multi-step workflow execution.
"""

from nexus.automation.app_controller import ActiveAppInfo, DesktopAppController
from nexus.automation.error_recovery import ErrorRecoveryManager, with_retry
from nexus.automation.ui_interaction import DesktopUIInteraction
from nexus.automation.workflow import (
    MultiStepWorkflowEngine,
    WorkflowResult,
    WorkflowStep,
)

__all__ = [
    "DesktopAppController",
    "ActiveAppInfo",
    "DesktopUIInteraction",
    "ErrorRecoveryManager",
    "with_retry",
    "MultiStepWorkflowEngine",
    "WorkflowStep",
    "WorkflowResult",
]
