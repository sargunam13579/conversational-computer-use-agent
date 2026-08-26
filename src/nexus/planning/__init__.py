"""
NEXUS Planning & Multi-Step Autonomous Agent Package.

Provides goal decomposition, dynamic tool selection, plan execution, progress tracking,
resilient retries, confirmation management, result verification, and emergency stops.
"""

from nexus.planning.cancellation import (
    CancellationManager,
    CancellationToken,
    CancellationType,
    EmergencyStopError,
    EmergencyStopException,
    TaskCancelledError,
    TaskCancelledException,
)
from nexus.planning.executor import PlanExecutionEngine
from nexus.planning.manager import TaskManager
from nexus.planning.planner import TaskPlanner
from nexus.planning.progress import ProgressTracker
from nexus.planning.retry import ErrorCategory, RetryDecision, RetrySystem
from nexus.planning.tool_selector import ToolSelector
from nexus.planning.types import (
    ExecutionResult,
    Plan,
    PlanStatus,
    PlanStep,
    RiskLevel,
    StepStatus,
    TaskGoal,
    TaskProgress,
    VerificationResult,
)
from nexus.planning.verifier import ResultVerifier

__all__ = [
    "CancellationManager",
    "CancellationToken",
    "CancellationType",
    "EmergencyStopError",
    "EmergencyStopException",
    "TaskCancelledError",
    "TaskCancelledException",
    "PlanExecutionEngine",
    "TaskManager",
    "TaskPlanner",
    "ProgressTracker",
    "ErrorCategory",
    "RetryDecision",
    "RetrySystem",
    "ToolSelector",
    "ExecutionResult",
    "Plan",
    "PlanStatus",
    "PlanStep",
    "RiskLevel",
    "StepStatus",
    "TaskGoal",
    "TaskProgress",
    "VerificationResult",
    "ResultVerifier",
]
