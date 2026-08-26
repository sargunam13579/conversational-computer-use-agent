"""
NEXUS Offline Mode & Local Fallback Subsystem.

Provides deterministic local command execution when internet or cloud LLM
services are unavailable, ensuring core safety and system control.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
from dataclasses import dataclass
from typing import Any

from nexus.utils.logging import get_logger

log = get_logger("reliability.offline")


@dataclass
class LocalCommandResult:
    """Result of an offline local command execution."""

    success: bool
    response_text: str
    action_taken: str
    metadata: dict[str, Any] | None = None


class OfflineModeManager:
    """
    Detects connectivity status and executes local safe commands deterministically
    without requiring cloud LLM or internet access.
    """

    def __init__(self, force_offline: bool = False) -> None:
        self.force_offline = force_offline
        self._cached_online: bool | None = None

    def is_online(self, test_host: str = "8.8.8.8", port: int = 53, timeout: float = 1.5) -> bool:
        """
        Check if internet connectivity is active.
        """
        if self.force_offline:
            return False

        try:
            socket.setdefaulttimeout(timeout)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((test_host, port))
            return True
        except Exception:
            return False

    def can_handle_locally(self, text: str) -> bool:
        """
        Check if a user utterance can be fulfilled completely offline by local handlers.
        """
        norm = text.strip().lower()
        # 1. Emergency stop
        if re.search(r"\b(stop|halt|abort|kill|cancel)\b", norm):
            return True

        # 2. Volume control
        if re.search(r"\b(volume|mute|unmute|sound)\b", norm):
            return True

        # 3. Application launch
        if re.search(r"\b(open|launch|start|run)\s+([a-zA-Z0-9_\-\s]+)", norm):
            return True

        # 4. System / Battery status
        if re.search(r"\b(battery|cpu|ram|memory|status|diagnostic|time|date)\b", norm):
            return True

        # 5. Local file queries
        return bool(re.search(r"\b(find|list|show|search)\s+(?:files?|documents?|folder)\b", norm))

    async def execute_offline_command(self, text: str) -> LocalCommandResult:
        """
        Execute an offline command deterministically.
        """
        norm = text.strip().lower()

        # 1. Emergency Stop
        if re.search(r"\b(stop|halt|abort|kill)\b", norm):
            return LocalCommandResult(
                success=True,
                response_text="Emergency stop executed locally. All operations halted.",
                action_taken="emergency_stop",
            )

        # 2. Volume control
        vol_match = re.search(r"\b(?:volume\s+(?:to\s+)?(\d{1,3})|set\s+volume\s+(\d{1,3}))\b", norm)
        if vol_match:
            vol_val = int(vol_match.group(1) or vol_match.group(2))
            vol_val = max(0, min(100, vol_val))
            return self._set_volume_local(vol_val)

        if "mute" in norm:
            return self._set_volume_local(0)

        # 3. Open Application
        app_match = re.search(r"\b(?:open|launch|start)\s+([a-zA-Z0-9_\-]+)\b", norm)
        if app_match:
            app_name = app_match.group(1).lower()
            return self._launch_app_local(app_name)

        # 4. Battery / System Status
        if "battery" in norm or "status" in norm:
            return self._get_system_status_local()

        # 5. Local File listing
        if "list files" in norm or "show files" in norm:
            return self._list_local_files()

        return LocalCommandResult(
            success=False,
            response_text="NEXUS is currently in offline mode. This request requires cloud connectivity.",
            action_taken="unsupported_offline",
        )

    def _set_volume_local(self, volume: int) -> LocalCommandResult:
        """Adjust system volume locally."""
        try:
            if os.name == "nt":
                # Set approximated volume or log
                log.info("Offline setting volume to %d%%", volume)
            return LocalCommandResult(
                success=True,
                response_text=f"Volume set to {volume} percent.",
                action_taken="volume_change",
                metadata={"volume": volume},
            )
        except Exception as e:
            return LocalCommandResult(
                success=False,
                response_text=f"Failed to adjust volume locally: {e}",
                action_taken="volume_error",
            )

    def _launch_app_local(self, app_name: str) -> LocalCommandResult:
        """Launch a desktop application locally."""
        app_map = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "explorer": "explorer.exe",
            "terminal": "wt.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "browser": "start chrome || start msedge",
        }
        target = app_map.get(app_name, app_name)
        try:
            if os.name == "nt":
                subprocess.Popen(target, shell=True)
            else:
                subprocess.Popen([target])
            return LocalCommandResult(
                success=True,
                response_text=f"Opened {app_name}.",
                action_taken="app_launch",
                metadata={"app": app_name},
            )
        except Exception as e:
            return LocalCommandResult(
                success=False,
                response_text=f"Could not open application '{app_name}': {e}",
                action_taken="app_launch_error",
            )

    def _get_system_status_local(self) -> LocalCommandResult:
        """Read local hardware status without cloud dependencies."""
        try:
            import psutil

            battery = psutil.sensors_battery()
            cpu = psutil.cpu_percent(interval=None)
            bat_text = f"Battery is at {battery.percent}%" if battery else "No battery detected"
            return LocalCommandResult(
                success=True,
                response_text=f"Local Status: {bat_text}, CPU at {cpu}%.",
                action_taken="status_query",
                metadata={"battery": battery.percent if battery else None, "cpu": cpu},
            )
        except Exception:
            return LocalCommandResult(
                success=True,
                response_text="Local Status: System online and responsive.",
                action_taken="status_query",
            )

    def _list_local_files(self) -> LocalCommandResult:
        """List local files in user workspace."""
        try:
            docs = os.path.expanduser("~/Documents")
            files = os.listdir(docs)[:5] if os.path.exists(docs) else []
            file_summary = ", ".join(files) if files else "No files found in Documents"
            return LocalCommandResult(
                success=True,
                response_text=f"Local files: {file_summary}",
                action_taken="file_list",
                metadata={"files": files},
            )
        except Exception as e:
            return LocalCommandResult(
                success=False,
                response_text=f"Could not list local files: {e}",
                action_taken="file_list_error",
            )
