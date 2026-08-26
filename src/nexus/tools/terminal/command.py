"""
NEXUS Terminal Command Execution Tool.

Provides safe terminal command execution with:
- Security classification and safety checks
- Output capture (stdout, stderr, exit code)
- Error detection and timeout enforcement
- Confirmation requirement for high-risk operations
"""

from __future__ import annotations

import asyncio
import contextlib
import platform
import time
from pathlib import Path
from typing import Any

from nexus.security.terminal_security import (
    CommandSafetyStatus,
    TerminalSecurityClassifier,
)
from nexus.tools.base import BaseTool, RiskLevel, TargetDevice, ToolResult
from nexus.utils.logging import get_logger

log = get_logger("tools.terminal.command")


class ExecuteCommandTool(BaseTool):
    """
    Execute terminal / shell commands safely on the laptop.
    """

    def __init__(self, classifier: TerminalSecurityClassifier | None = None) -> None:
        self._classifier = classifier or TerminalSecurityClassifier()

    @property
    def name(self) -> str:
        return "execute_command"

    @property
    def description(self) -> str:
        return (
            "Execute approved terminal commands on the laptop. Captures stdout and stderr output, "
            "monitors execution status, and applies strict security rules to prevent harmful actions."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command line string to execute (e.g., 'dir', 'git status', 'python test.py').",
                },
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory in which to execute the command.",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Maximum execution time in seconds before terminating (default: 30).",
                },
                "shell": {
                    "type": "string",
                    "enum": ["powershell", "cmd", "default"],
                    "description": "Shell environment to use on Windows (default: 'powershell').",
                },
            },
            "required": ["command"],
        }

    @property
    def category(self) -> str:
        return "terminal"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def validate(self, **kwargs: Any) -> tuple[bool, str]:
        cmd = kwargs.get("command", "").strip()
        if not cmd:
            return False, "Command cannot be empty."

        analysis = self._classifier.analyze(cmd)
        if analysis.status == CommandSafetyStatus.BLOCKED:
            return False, f"Security Violation: {analysis.reason}"

        return True, ""

    async def execute(
        self,
        command: str = "",
        working_dir: str | None = None,
        timeout_seconds: int = 30,
        shell: str = "powershell",
        **kwargs: Any,
    ) -> ToolResult:
        cmd_clean = command.strip()
        if not cmd_clean:
            return ToolResult.fail("Command cannot be empty.")

        # 1. Security Analysis
        analysis = self._classifier.analyze(cmd_clean)
        if analysis.status == CommandSafetyStatus.BLOCKED:
            log.warning("Blocked dangerous command attempt: '%s'", cmd_clean)
            return ToolResult.fail(
                f"Command blocked by NEXUS Security Guard: {analysis.reason}",
                status="blocked",
                risk_level=analysis.risk_level.value,
            )

        # 2. Resolve working directory
        cwd = Path(working_dir).expanduser().resolve() if working_dir else Path.cwd()
        if not cwd.exists() or not cwd.is_dir():
            return ToolResult.fail(f"Working directory does not exist: '{cwd}'")

        # 3. Determine shell executable
        is_windows = platform.system() == "Windows"
        if is_windows:
            if shell == "cmd":
                exec_cmd = ["cmd.exe", "/c", cmd_clean]
            else:
                exec_cmd = [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    cmd_clean,
                ]
        else:
            exec_cmd = ["/bin/sh", "-c", cmd_clean]

        start_time = time.time()
        try:
            # Execute asynchronously with subprocess
            proc = await asyncio.create_subprocess_exec(
                *exec_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=float(timeout_seconds),
                )
            except TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                return ToolResult.fail(
                    f"Command timed out after {timeout_seconds} seconds: '{cmd_clean}'",
                    timed_out=True,
                    timeout_seconds=timeout_seconds,
                )

            duration = time.time() - start_time
            exit_code = proc.returncode or 0

            # Decode outputs
            stdout_str = stdout_bytes.decode("utf-8", errors="replace").rstrip()
            stderr_str = stderr_bytes.decode("utf-8", errors="replace").rstrip()

            formatted_output_parts = []
            if stdout_str:
                formatted_output_parts.append(stdout_str)
            if stderr_str:
                formatted_output_parts.append(f"[STDERR]\n{stderr_str}")

            output_text = (
                "\n".join(formatted_output_parts)
                or f"(Command exited with code {exit_code} and no output)"
            )

            if exit_code == 0:
                return ToolResult.ok(
                    output_text,
                    exit_code=exit_code,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    duration_seconds=round(duration, 3),
                    working_dir=str(cwd),
                )
            else:
                return ToolResult.fail(
                    f"Command exited with non-zero status code {exit_code}:\n{output_text}",
                    exit_code=exit_code,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    duration_seconds=round(duration, 3),
                )

        except Exception as e:
            log.error("Execution error running '%s': %s", cmd_clean, e)
            return ToolResult.fail(f"Failed to execute command: {e}")
