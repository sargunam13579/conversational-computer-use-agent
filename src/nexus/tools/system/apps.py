"""
NEXUS Application Control Tools for Windows.

Provides safe capabilities to:
- Open / Launch applications with arguments
- Close applications gracefully or force kill
- Switch active application / bring window to front
- Search installed applications across Start Menu, PATH, and registry
- List running applications / GUI windows
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

import psutil

from nexus.tools.base import BaseTool, RiskLevel, TargetDevice, ToolResult
from nexus.utils.logging import get_logger

log = get_logger("tools.system.apps")

# Common application name to executable mappings
COMMON_APP_MAP: dict[str, str] = {
    "notepad": "notepad.exe",
    "notepad++": "notepad++.exe",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "mspaint": "mspaint.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    "powershell": "powershell.exe",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "settings": "ms-settings:",
    "control panel": "control.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "brave": "brave.exe",
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "slack": "slack.exe",
    "code": "code.cmd",
    "vscode": "code.cmd",
    "visual studio code": "code.cmd",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "outlook": "outlook.exe",
    "vlc": "vlc.exe",
    "steam": "steam.exe",
    "obs": "obs64.exe",
}


def _find_windows_app_path(app_name: str) -> str | None:
    """Find executable or shortcut path for a given application name."""
    clean_name = app_name.lower().strip()

    # 1. Exact match in common map
    if clean_name in COMMON_APP_MAP:
        mapped = COMMON_APP_MAP[clean_name]
        if mapped.startswith("ms-") or shutil.which(mapped):
            return mapped

    # 2. Check if on system PATH
    found = shutil.which(app_name)
    if found:
        return found

    # 3. Check Start Menu shortcuts on Windows
    if platform.system() == "Windows":
        start_menu_dirs = [
            Path(os.environ.get("APPDATA", ""))
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs",
            Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData"))
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs",
        ]
        for base_dir in start_menu_dirs:
            if base_dir.exists():
                for lnk in base_dir.rglob("*.lnk"):
                    if clean_name in lnk.stem.lower():
                        return str(lnk)

    return None


# ---------------------------------------------------------------------------
# Open / Launch Application
# ---------------------------------------------------------------------------


class OpenApplicationTool(BaseTool):
    """Open or launch an application on the laptop."""

    @property
    def name(self) -> str:
        return "open_application"

    @property
    def description(self) -> str:
        return (
            "Open or launch an application on the laptop. Specify the application name "
            "(e.g., 'notepad', 'code', 'chrome', 'calc') and optional launch arguments or working directory."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Name or executable of the application (e.g. 'notepad', 'chrome', 'code', 'calculator').",
                },
                "arguments": {
                    "type": "string",
                    "description": "Optional command-line arguments to pass to the application.",
                },
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory in which to start the application.",
                },
            },
            "required": ["app_name"],
        }

    @property
    def category(self) -> str:
        return "application"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self,
        app_name: str = "",
        arguments: str | None = None,
        working_dir: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        app_clean = app_name.strip()
        if not app_clean:
            return ToolResult.fail("Application name cannot be empty.")

        target = _find_windows_app_path(app_clean) or app_clean
        log.info("Launching application '%s' (resolved target: '%s')", app_clean, target)

        try:
            cwd = working_dir if working_dir and Path(working_dir).exists() else None

            if target.startswith("ms-"):
                # Windows URI scheme
                subprocess.Popen(f"start {target}", shell=True, cwd=cwd)
            elif target.endswith(".lnk"):
                # Windows shortcut file
                os.startfile(target) if hasattr(os, "startfile") else subprocess.Popen(
                    ["start", "", target], shell=True, cwd=cwd
                )
            else:
                cmd_parts = [target]
                if arguments:
                    cmd_parts.extend(arguments.split())
                subprocess.Popen(cmd_parts, shell=True, cwd=cwd)

            return ToolResult.ok(
                f"Successfully opened {app_clean}",
                app_name=app_clean,
                resolved_target=target,
                arguments=arguments,
            )
        except Exception as e:
            log.error("Failed to launch application '%s': %s", app_clean, e)
            return ToolResult.fail(f"Could not open application '{app_clean}': {e}")


# ---------------------------------------------------------------------------
# Close Application
# ---------------------------------------------------------------------------


class CloseApplicationTool(BaseTool):
    """Close a running application by name, window title, or PID."""

    @property
    def name(self) -> str:
        return "close_application"

    @property
    def description(self) -> str:
        return (
            "Close a running application on the laptop by process name (e.g. 'notepad', 'chrome.exe'), "
            "window title, or process ID (PID). Gracefully closes by default."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Name or executable of the application to close (e.g. 'notepad', 'calc').",
                },
                "pid": {
                    "type": "integer",
                    "description": "Optional specific process ID (PID) to close.",
                },
                "force": {
                    "type": "boolean",
                    "description": "Whether to force kill the process immediately (default: false).",
                },
            },
            "required": [],
        }

    @property
    def category(self) -> str:
        return "application"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self,
        app_name: str | None = None,
        pid: int | None = None,
        force: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        if not app_name and pid is None:
            return ToolResult.fail("Please provide either 'app_name' or 'pid' to close.")

        closed_pids: list[int] = []
        app_target = app_name.lower().strip() if app_name else ""

        # Remove .exe extension if provided for matching
        clean_target = app_target[:-4] if app_target.endswith(".exe") else app_target

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                proc_pid = proc.info["pid"]
                proc_name = (proc.info["name"] or "").lower()
                clean_proc_name = proc_name[:-4] if proc_name.endswith(".exe") else proc_name

                match = False
                if (
                    pid is not None
                    and proc_pid == pid
                    or app_target
                    and (
                        clean_proc_name == clean_target
                        or clean_target in clean_proc_name
                        or (
                            proc.info.get("cmdline")
                            and any(clean_target in arg.lower() for arg in proc.info["cmdline"])
                        )
                    )
                ):
                    match = True

                if match:
                    p = psutil.Process(proc_pid)
                    if force:
                        p.kill()
                    else:
                        p.terminate()
                    closed_pids.append(proc_pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        if closed_pids:
            mode_str = "force-closed" if force else "closed"
            return ToolResult.ok(
                f"Successfully {mode_str} {len(closed_pids)} process(es) for '{app_name or pid}'.",
                closed_pids=closed_pids,
            )
        return ToolResult.fail(f"No running processes found matching '{app_name or pid}'.")


# ---------------------------------------------------------------------------
# Switch Application
# ---------------------------------------------------------------------------


class SwitchApplicationTool(BaseTool):
    """Switch to an application and bring its window to the foreground."""

    @property
    def name(self) -> str:
        return "switch_application"

    @property
    def description(self) -> str:
        return "Bring a running application window to the foreground by application name or window title."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Application name or window title to bring to front (e.g. 'notepad', 'chrome', 'Visual Studio Code').",
                },
            },
            "required": ["app_name"],
        }

    @property
    def category(self) -> str:
        return "application"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(self, app_name: str = "", **kwargs: Any) -> ToolResult:
        clean_name = app_name.strip()
        if not clean_name:
            return ToolResult.fail("Application name cannot be empty.")

        if platform.system() == "Windows":
            try:
                import ctypes

                user32 = ctypes.windll.user32

                matched_hwnd = None
                matched_title = ""

                def enum_windows_callback(hwnd: int, extra: Any) -> bool:
                    nonlocal matched_hwnd, matched_title
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            title = buff.value
                            if clean_name.lower() in title.lower():
                                matched_hwnd = hwnd
                                matched_title = title
                                return False  # Stop enumeration
                    return True

                enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
                user32.EnumWindows(enum_windows_proc(enum_windows_callback), 0)

                if matched_hwnd:
                    # Restore if minimized (SW_RESTORE = 9)
                    user32.ShowWindow(matched_hwnd, 9)
                    user32.SetForegroundWindow(matched_hwnd)
                    return ToolResult.ok(
                        f"Switched to '{matched_title}'",
                        window_title=matched_title,
                        hwnd=matched_hwnd,
                    )
            except Exception as e:
                log.warning("Win32 switch failed: %s, falling back to powershell", e)

            # PowerShell fallback
            ps_script = f"""
            $proc = Get-Process | Where-Object {{ $_.MainWindowTitle -match '{clean_name}' -or $_.ProcessName -match '{clean_name}' }} | Select-Object -First 1
            if ($proc -and $proc.MainWindowHandle -ne 0) {{
                $wsh = New-Object -ComObject WScript.Shell
                $wsh.AppActivate($proc.Id)
                Write-Output "OK:$($proc.MainWindowTitle)"
            }} else {{
                Write-Output "NOT_FOUND"
            }}
            """
            try:
                res = subprocess.run(
                    ["powershell", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                output = res.stdout.strip()
                if "OK:" in output:
                    title = output.replace("OK:", "").strip()
                    return ToolResult.ok(
                        f"Switched to application '{title or clean_name}'", window_title=title
                    )
            except Exception as e:
                log.error("PowerShell switch failed: %s", e)

        return ToolResult.fail(f"Could not find an active window matching '{clean_name}'.")


# ---------------------------------------------------------------------------
# Search Applications
# ---------------------------------------------------------------------------


class SearchApplicationsTool(BaseTool):
    """Search for installed applications on the computer."""

    @property
    def name(self) -> str:
        return "search_applications"

    @property
    def description(self) -> str:
        return (
            "Search for installed applications on the computer by keyword or name. "
            "Returns matching applications and their executable paths."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keyword or name of the application to search for.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 10).",
                },
            },
            "required": ["query"],
        }

    @property
    def category(self) -> str:
        return "application"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(self, query: str = "", max_results: int = 10, **kwargs: Any) -> ToolResult:
        query_clean = query.lower().strip()
        results: list[dict[str, str]] = []
        seen_names: set[str] = set()

        # 1. Search common map
        for name, exe in COMMON_APP_MAP.items():
            if query_clean in name:
                results.append({"name": name.title(), "executable": exe, "source": "known_apps"})
                seen_names.add(name.lower())

        # 2. Search Windows Start Menu
        if platform.system() == "Windows":
            start_menu_dirs = [
                Path(os.environ.get("APPDATA", ""))
                / "Microsoft"
                / "Windows"
                / "Start Menu"
                / "Programs",
                Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData"))
                / "Microsoft"
                / "Windows"
                / "Start Menu"
                / "Programs",
            ]
            for base_dir in start_menu_dirs:
                if base_dir.exists():
                    for lnk in base_dir.rglob("*.lnk"):
                        stem = lnk.stem
                        if query_clean in stem.lower() and stem.lower() not in seen_names:
                            results.append(
                                {
                                    "name": stem,
                                    "path": str(lnk),
                                    "source": "start_menu",
                                }
                            )
                            seen_names.add(stem.lower())
                            if len(results) >= max_results:
                                break

        # 3. Check system PATH
        for name in [query_clean, f"{query_clean}.exe", f"{query_clean}.cmd"]:
            path = shutil.which(name)
            if path and query_clean not in seen_names:
                results.append({"name": query_clean, "path": path, "source": "path"})
                seen_names.add(query_clean)

        results = results[:max_results]
        if not results:
            return ToolResult.ok(f"No installed applications found matching '{query}'.", apps=[])

        summary_lines = [f"Found {len(results)} application(s) matching '{query}':"]
        for item in results:
            summary_lines.append(
                f"  • {item['name']} ({item.get('path') or item.get('executable')})"
            )

        return ToolResult.ok("\n".join(summary_lines), apps=results, count=len(results))


# ---------------------------------------------------------------------------
# List Applications (Running)
# ---------------------------------------------------------------------------


class ListApplicationsTool(BaseTool):
    """List currently running applications and windows."""

    @property
    def name(self) -> str:
        return "list_applications"

    @property
    def description(self) -> str:
        return "List currently running GUI applications and active windows on the laptop."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of applications to list (default: 20).",
                },
            },
            "required": [],
        }

    @property
    def category(self) -> str:
        return "application"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(self, limit: int = 20, **kwargs: Any) -> ToolResult:
        running_apps: list[dict[str, Any]] = []

        if platform.system() == "Windows":
            try:
                import ctypes

                user32 = ctypes.windll.user32

                def enum_windows_callback(hwnd: int, extra: Any) -> bool:
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            title = buff.value.strip()
                            if title and title not in (
                                "Program Manager",
                                "Settings",
                                "NVIDIA GeForce Overlay",
                            ):
                                pid = ctypes.c_ulong()
                                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                                try:
                                    pname = psutil.Process(pid.value).name()
                                except Exception:
                                    pname = "unknown"
                                running_apps.append(
                                    {
                                        "title": title,
                                        "pid": pid.value,
                                        "process": pname,
                                        "hwnd": hwnd,
                                    }
                                )
                    return True

                enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
                user32.EnumWindows(enum_windows_proc(enum_windows_callback), 0)
            except Exception as e:
                log.warning("Win32 window list failed: %s", e)

        # Fallback to psutil process list if no GUI windows detected
        if not running_apps:
            for proc in psutil.process_iter(["pid", "name", "cpu_percent"]):
                try:
                    if proc.info["name"] and not proc.info["name"].startswith("System"):
                        running_apps.append(
                            {
                                "title": proc.info["name"],
                                "pid": proc.info["pid"],
                                "process": proc.info["name"],
                            }
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        running_apps = running_apps[:limit]
        summary = [f"Active applications ({len(running_apps)}):"]
        for app in running_apps:
            summary.append(f"  • [PID {app['pid']}] {app['title']} ({app.get('process', '')})")

        return ToolResult.ok("\n".join(summary), applications=running_apps, count=len(running_apps))


# ---------------------------------------------------------------------------
# Minimize / Maximize / Restore Application Window
# ---------------------------------------------------------------------------


class WindowStateTool(BaseTool):
    """Minimize, maximize, restore, or hide an application window on the laptop."""

    @property
    def name(self) -> str:
        return "window_state"

    @property
    def description(self) -> str:
        return (
            "Control application window states (minimize, maximize, restore, normal, hide) "
            "by application name or window title."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Application name or window title (e.g. 'notepad', 'chrome', 'Visual Studio Code').",
                },
                "action": {
                    "type": "string",
                    "enum": ["minimize", "maximize", "restore", "hide"],
                    "description": "Window action to perform: 'minimize', 'maximize', 'restore', or 'hide'.",
                },
            },
            "required": ["app_name", "action"],
        }

    @property
    def category(self) -> str:
        return "application"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self,
        app_name: str = "",
        action: str = "minimize",
        **kwargs: Any,
    ) -> ToolResult:
        clean_name = app_name.strip().lower()
        if not clean_name:
            return ToolResult.fail("Application name cannot be empty.")

        action_clean = action.strip().lower()
        cmd_map = {
            "hide": 0,
            "maximize": 3,
            "minimize": 6,
            "restore": 9,
            "normal": 1,
        }
        cmd_flag = cmd_map.get(action_clean, 6)

        if platform.system() == "Windows":
            try:
                import ctypes

                user32 = ctypes.windll.user32
                matched_hwnd = None
                matched_title = ""

                def enum_windows_callback(hwnd: int, extra: Any) -> bool:
                    nonlocal matched_hwnd, matched_title
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            title = buff.value
                            if clean_name in title.lower():
                                matched_hwnd = hwnd
                                matched_title = title
                                return False
                    return True

                enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
                user32.EnumWindows(enum_windows_proc(enum_windows_callback), 0)

                if matched_hwnd:
                    user32.ShowWindow(matched_hwnd, cmd_flag)
                    if action_clean in ("maximize", "restore"):
                        user32.SetForegroundWindow(matched_hwnd)
                    return ToolResult.ok(
                        f"Successfully performed '{action_clean}' on '{matched_title}'.",
                        app_name=app_name,
                        window_title=matched_title,
                        action=action_clean,
                    )
            except Exception as e:
                log.warning("Win32 window state control failed: %s", e)

        return ToolResult.fail(f"Could not find an active window matching '{app_name}' to {action_clean}.")

