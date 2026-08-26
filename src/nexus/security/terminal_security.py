"""
NEXUS Terminal Security Classifier & Safety Guard.

Provides security classification and validation for terminal commands to prevent
arbitrary destructive command execution on the user's system.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from nexus.tools.base import RiskLevel
from nexus.utils.logging import get_logger

log = get_logger("security.terminal")


class CommandSafetyStatus(StrEnum):
    """Command safety classification status."""

    ALLOWED = "allowed"  # Safe to execute automatically
    CONFIRM_REQUIRED = "confirm"  # Modifying or dangerous, requires confirmation
    BLOCKED = "blocked"  # Explicitly forbidden destructive command


@dataclass
class CommandAnalysisResult:
    """Result of command security analysis."""

    status: CommandSafetyStatus
    risk_level: RiskLevel
    reason: str
    command: str
    detected_patterns: list[str]
    suggested_action: str = ""


# Explicitly forbidden commands that pose catastrophic or irreversible risk
_BLOCKED_COMMAND_PATTERNS = [
    # Destructive disk formatting or partitioning
    (r"\bformat\s+[a-zA-Z]:", "Disk formatting is prohibited"),
    (r"\bdiskpart\b", "Disk partitioning tool is prohibited"),
    (r"\bbcdedit\b", "Boot configuration modification is prohibited"),
    # Fork bombs / resource exhaustion
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "Fork bomb detected"),
    (r"%0\|%0", "Batch fork bomb detected"),
    # Catastrophic whole-disk/system deletion
    (
        r"(?:rmdir|rd)\s+(?:/s\s+/q|/q\s+/s)\s+(?:[c-zC-Z]:\\?|/|\\|\%systemroot\%)",
        "Root or system drive deletion is prohibited",
    ),
    (
        r"del\s+(?:/f\s+/s\s+/q|/s\s+/q\s+/f|/q\s+/s\s+/f)\s+(?:[c-zC-Z]:\\?|/|\\|\%systemroot\%)",
        "Root or system deletion is prohibited",
    ),
    (r"rm\s+-rf\s+(?:/|/\*|~|%systemroot%|c:\\)", "Root or home recursive deletion is prohibited"),
    (
        r"Remove-Item\s+.*-Recurse\s+.*(?:[c-zC-Z]:\\|/|\\|\$env:SystemRoot)",
        "PowerShell system-wide recursive deletion is prohibited",
    ),
    # Direct master boot record or raw device writing
    (r"dd\s+if=.*of=(?:/dev/|\\\\.\\PhysicalDrive)", "Raw disk overwrite is prohibited"),
    # Disabling security tools
    (
        r"Set-MpPreference\s+-DisableRealtimeMonitoring\s+\$true",
        "Disabling Windows Defender is prohibited",
    ),
    (
        r"netsh\s+advfirewall\s+set\s+allprofiles\s+state\s+off",
        "Disabling Windows Firewall is prohibited",
    ),
]

# High-risk commands that modify system state, delete files, or access network executables
_HIGH_RISK_COMMAND_PATTERNS = [
    # Deletion operations
    (r"\b(?:del|erase)\b", "File deletion command"),
    (r"\b(?:rmdir|rd)\b", "Directory removal command"),
    (r"\bRemove-Item\b", "PowerShell item deletion"),
    (r"\brm\s+", "File/directory deletion"),
    # Process killing
    (r"\btaskkill\s+(?:/f|/F)", "Force process termination"),
    (r"\bStop-Process\s+.*-Force", "Force process termination"),
    (r"\bkill\s+-9", "Force process kill"),
    # Registry modifications
    (r"\breg\s+(?:add|delete|import)\b", "Registry modification"),
    (r"\bSet-ItemProperty\s+.*HKLM:", "System registry modification"),
    (r"\bRemove-ItemProperty\b", "Registry property removal"),
    # Service and user account management
    (r"\bnet\s+(?:user|localgroup|stop|start)\b", "Account or service management"),
    (r"\bStop-Service\b", "Service termination"),
    (r"\bRestart-Computer\b|\bStop-Computer\b|\bshutdown\b", "System shutdown/restart"),
    # Execution policy & arbitrary script invocation
    (r"Set-ExecutionPolicy", "Execution policy change"),
    (r"powershell\s+.*-(?:EncodedCommand|enc)\b", "Encoded PowerShell execution"),
    (
        r"(?:curl|iwr|Invoke-WebRequest|wget).*\|\s*(?:iex|Invoke-Expression|bash|sh|cmd)",
        "Remote script execution pipeline",
    ),
    (r"Invoke-Expression|iex\s*\(", "Dynamic script evaluation"),
]

# Known safe read-only / diagnostic commands
_SAFE_COMMAND_PREFIXES = {
    "dir",
    "ls",
    "pwd",
    "cd",
    "echo",
    "type",
    "cat",
    "more",
    "head",
    "tail",
    "git status",
    "git log",
    "git diff",
    "git branch",
    "git show",
    "git --version",
    "python --version",
    "python -V",
    "python -c",
    "py --version",
    "node --version",
    "node -v",
    "npm --version",
    "npm list",
    "pip list",
    "pip show",
    "pip --version",
    "whoami",
    "hostname",
    "ipconfig",
    "ifconfig",
    "ping",
    "tracert",
    "traceroute",
    "nslookup",
    "systeminfo",
    "ver",
    "date /t",
    "time /t",
    "where",
    "which",
    "findstr",
    "grep",
    "tree",
    "tasklist",
    "Get-Process",
    "Get-Service",
    "Get-Date",
    "Get-ChildItem",
    "Get-Location",
    "Get-Command",
    "Get-Help",
    "Get-Host",
}


class TerminalSecurityClassifier:
    """
    Evaluates terminal command strings against security rules.
    """

    def __init__(self, allowed_directories: list[str] | None = None) -> None:
        self.allowed_directories = [
            Path(d).expanduser().resolve() for d in (allowed_directories or ["~", "."])
        ]

    def analyze(self, command: str) -> CommandAnalysisResult:
        """
        Analyze a shell command for safety.
        """
        return self._do_analyze(command)

    def classify_command(self, command: str) -> CommandAnalysisResult:
        """Alias for analyze()."""
        return self._do_analyze(command)

    def _do_analyze(self, command: str) -> CommandAnalysisResult:
        cmd_clean = command.strip()
        if not cmd_clean:
            return CommandAnalysisResult(
                status=CommandSafetyStatus.ALLOWED,
                risk_level=RiskLevel.LOW,
                reason="Empty command",
                command=cmd_clean,
                detected_patterns=[],
            )

        # Check 1: Blocked commands (Catastrophic)
        for pattern, reason in _BLOCKED_COMMAND_PATTERNS:
            if re.search(pattern, cmd_clean, re.IGNORECASE):
                log.warning("Blocked dangerous command: %s (Reason: %s)", cmd_clean, reason)
                return CommandAnalysisResult(
                    status=CommandSafetyStatus.BLOCKED,
                    risk_level=RiskLevel.CRITICAL,
                    reason=f"Dangerous command strictly prohibited: {reason}",
                    command=cmd_clean,
                    detected_patterns=[pattern],
                    suggested_action="Refuse execution for safety.",
                )

        # Check 2: High-risk commands (Requires confirmation)
        for pattern, reason in _HIGH_RISK_COMMAND_PATTERNS:
            if re.search(pattern, cmd_clean, re.IGNORECASE):
                log.info("Command requires confirmation: %s (Reason: %s)", cmd_clean, reason)
                return CommandAnalysisResult(
                    status=CommandSafetyStatus.CONFIRM_REQUIRED,
                    risk_level=RiskLevel.HIGH,
                    reason=f"Potentially destructive action ({reason})",
                    command=cmd_clean,
                    detected_patterns=[pattern],
                    suggested_action="Prompt the user for explicit confirmation before executing.",
                )

        # Check 3: Known safe commands
        cmd_lower = cmd_clean.lower()
        for safe_prefix in _SAFE_COMMAND_PREFIXES:
            if cmd_lower == safe_prefix.lower() or cmd_lower.startswith(safe_prefix.lower() + " "):
                return CommandAnalysisResult(
                    status=CommandSafetyStatus.ALLOWED,
                    risk_level=RiskLevel.LOW,
                    reason=f"Safe diagnostic/query command matching '{safe_prefix}'",
                    command=cmd_clean,
                    detected_patterns=[],
                )

        # Check 4: General command default (Medium risk)
        return CommandAnalysisResult(
            status=CommandSafetyStatus.ALLOWED,
            risk_level=RiskLevel.MEDIUM,
            reason="Standard command execution",
            command=cmd_clean,
            detected_patterns=[],
        )

    def is_path_allowed(self, path: str | Path) -> bool:
        """
        Check if a given filesystem path is within the allowed directories.
        """
        target = Path(path).expanduser().resolve()
        for allowed in self.allowed_directories:
            try:
                target.relative_to(allowed)
                return True
            except ValueError:
                continue
        return False
