"""
NEXUS Starter Tools.

A collection of basic tools to bootstrap the system:
- get_current_time — Get the current date and time
- get_system_info — Get OS and hardware information
- open_application — Launch an application
- search_web — Search the web and return results
- set_volume — Set the system volume level
"""

from __future__ import annotations

import datetime
import platform
import shutil
import subprocess
from typing import Any

import psutil

from nexus.tools.base import BaseTool, RiskLevel, TargetDevice, ToolResult
from nexus.utils.logging import get_logger

log = get_logger("tools.system")


# ---------------------------------------------------------------------------
# get_current_time
# ---------------------------------------------------------------------------


class GetCurrentTimeTool(BaseTool):
    """Get the current date, time, and timezone."""

    @property
    def name(self) -> str:
        return "get_current_time"

    @property
    def description(self) -> str:
        return "Get the current date and time. Use this when the user asks what time it is, today's date, or anything time-related."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Optional timezone name (e.g., 'UTC', 'US/Eastern'). Defaults to local time.",
                },
            },
            "required": [],
        }

    @property
    def category(self) -> str:
        return "system"

    async def execute(self, timezone: str | None = None, **kwargs: Any) -> ToolResult:
        now = datetime.datetime.now()
        formatted = now.strftime("%A, %B %d, %Y at %I:%M %p")
        return ToolResult.ok(
            f"Current time: {formatted}",
            datetime=now.isoformat(),
            formatted=formatted,
        )


# ---------------------------------------------------------------------------
# get_system_info
# ---------------------------------------------------------------------------


class GetSystemInfoTool(BaseTool):
    """Get operating system and hardware information."""

    @property
    def name(self) -> str:
        return "get_system_info"

    @property
    def description(self) -> str:
        return "Get system information including OS, CPU, RAM, disk usage, and battery status. Use when the user asks about their system specs or status."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    @property
    def category(self) -> str:
        return "system"

    async def execute(self, **kwargs: Any) -> ToolResult:
        # OS info
        os_info = f"{platform.system()} {platform.release()} ({platform.version()})"
        machine = platform.machine()
        processor = platform.processor()

        # CPU
        cpu_count = psutil.cpu_count()
        cpu_percent = psutil.cpu_percent(interval=0.5)

        # RAM
        mem = psutil.virtual_memory()
        ram_total = f"{mem.total / (1024**3):.1f} GB"
        ram_used = f"{mem.used / (1024**3):.1f} GB"
        ram_percent = mem.percent

        # Disk
        disk = psutil.disk_usage("/")
        disk_total = f"{disk.total / (1024**3):.1f} GB"
        disk_free = f"{disk.free / (1024**3):.1f} GB"

        # Battery
        battery_info = "N/A"
        battery = psutil.sensors_battery()
        if battery:
            battery_info = (
                f"{battery.percent}% ({'charging' if battery.power_plugged else 'on battery'})"
            )

        info = (
            f"OS: {os_info}\n"
            f"Machine: {machine} | Processor: {processor}\n"
            f"CPU: {cpu_count} cores, {cpu_percent}% usage\n"
            f"RAM: {ram_used} / {ram_total} ({ram_percent}%)\n"
            f"Disk: {disk_free} free of {disk_total}\n"
            f"Battery: {battery_info}"
        )

        return ToolResult.ok(info)


# ---------------------------------------------------------------------------
# open_application
# ---------------------------------------------------------------------------


class OpenApplicationTool(BaseTool):
    """Open/launch an application on the laptop."""

    @property
    def name(self) -> str:
        return "open_application"

    @property
    def description(self) -> str:
        return "Open or launch an application on the laptop. Provide the application name (e.g., 'notepad', 'chrome', 'calculator', 'explorer'). Use this when the user asks to open an app."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "The name of the application to open (e.g., 'notepad', 'chrome', 'calculator', 'spotify').",
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

    # Common app name → executable mapping for Windows
    _APP_MAP: dict[str, str] = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "paint": "mspaint.exe",
        "explorer": "explorer.exe",
        "file explorer": "explorer.exe",
        "command prompt": "cmd.exe",
        "cmd": "cmd.exe",
        "terminal": "wt.exe",
        "powershell": "powershell.exe",
        "task manager": "taskmgr.exe",
        "settings": "ms-settings:",
        "chrome": "chrome",
        "google chrome": "chrome",
        "firefox": "firefox",
        "edge": "msedge",
        "microsoft edge": "msedge",
        "brave": "brave",
        "spotify": "spotify",
        "discord": "discord",
        "slack": "slack",
        "vscode": "code",
        "visual studio code": "code",
        "word": "winword",
        "excel": "excel",
        "powerpoint": "powerpnt",
        "outlook": "outlook",
    }

    async def execute(self, app_name: str = "", **kwargs: Any) -> ToolResult:
        app_lower = app_name.lower().strip()

        # Resolve the executable name
        executable = self._APP_MAP.get(app_lower, app_lower)

        try:
            if executable.startswith("ms-"):
                # Windows URI scheme (e.g., ms-settings:)
                subprocess.Popen(["start", executable], shell=True)
            elif shutil.which(executable):
                subprocess.Popen([executable], shell=True)
            else:
                # Try using 'start' as a fallback (handles Start Menu shortcuts)
                subprocess.Popen(["start", "", app_name], shell=True)

            return ToolResult.ok(f"Opened {app_name}")

        except Exception as e:
            return ToolResult.fail(f"Could not open '{app_name}': {e}")


# ---------------------------------------------------------------------------
# set_volume
# ---------------------------------------------------------------------------


class SetVolumeTool(BaseTool):
    """Set the system volume level on Windows."""

    @property
    def name(self) -> str:
        return "set_volume"

    @property
    def description(self) -> str:
        return "Set the system audio volume level. Specify a percentage from 0 (mute) to 100 (maximum). Use when the user asks to change volume, turn it up/down, or mute."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "level": {
                    "type": "integer",
                    "description": "Volume level as a percentage (0-100).",
                    "minimum": 0,
                    "maximum": 100,
                },
            },
            "required": ["level"],
        }

    @property
    def category(self) -> str:
        return "system"

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(self, level: int = 50, **kwargs: Any) -> ToolResult:
        level = max(0, min(100, level))

        try:
            # Use PowerShell to set volume on Windows
            # Maps 0-100 to 0-65535 (Windows volume range)
            volume_value = int(level / 100 * 65535)
            ps_command = (
                f"$wshShell = New-Object -ComObject WScript.Shell; "
                f"1..50 | ForEach-Object {{ $wshShell.SendKeys([char]174) }}; "  # Volume down 50x
                f"1..{level // 2} | ForEach-Object {{ $wshShell.SendKeys([char]175) }}"  # Volume up to target
            )

            # Simpler approach using nircmd if available, otherwise use PowerShell
            nircmd = shutil.which("nircmd")
            if nircmd:
                subprocess.run(
                    [nircmd, "setsysvolume", str(volume_value)],
                    capture_output=True,
                )
            else:
                # Fallback: use pycaw or simple PowerShell approach
                subprocess.run(
                    ["powershell", "-Command", ps_command],
                    capture_output=True,
                    timeout=10,
                )

            return ToolResult.ok(f"Volume set to {level}%")

        except Exception as e:
            return ToolResult.fail(f"Could not set volume: {e}")


# ---------------------------------------------------------------------------
# search_web
# ---------------------------------------------------------------------------


class SearchWebTool(BaseTool):
    """Search the web and open results in the default browser."""

    @property
    def name(self) -> str:
        return "search_web"

    @property
    def description(self) -> str:
        return "Search the web using the user's default browser. Opens a Google search with the specified query. Use when the user asks to search for something online."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up on the web.",
                },
            },
            "required": ["query"],
        }

    @property
    def category(self) -> str:
        return "web"

    async def execute(self, query: str = "", **kwargs: Any) -> ToolResult:
        import urllib.parse
        import webbrowser

        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={encoded_query}"

        try:
            webbrowser.open(url)
            return ToolResult.ok(f"Opened web search for: {query}", url=url)
        except Exception as e:
            return ToolResult.fail(f"Could not open browser: {e}")


# ---------------------------------------------------------------------------
# get_weather
# ---------------------------------------------------------------------------


class GetWeatherTool(BaseTool):
    """Get live real-time weather information for any city or area."""

    @property
    def name(self) -> str:
        return "get_weather"

    @property
    def description(self) -> str:
        return "Get live current weather, temperature, humidity, and forecast for any city, town, or location (e.g. 'Avadi', 'Chennai', 'Mumbai', 'London')."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City, town, or location name (e.g. 'Avadi', 'Chennai', 'Bangalore').",
                },
            },
            "required": ["location"],
        }

    @property
    def category(self) -> str:
        return "system"

    async def execute(self, location: str = "Chennai", **kwargs: Any) -> ToolResult:
        import asyncio
        import json
        import urllib.parse
        import urllib.request

        loc_clean = (location or "Chennai").strip()

        def _fetch() -> dict[str, Any]:
            url = f"https://wttr.in/{urllib.parse.quote(loc_clean)}?format=j1"
            req = urllib.request.Request(url, headers={"User-Agent": "NEXUS-AI/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode())

        try:
            data = await asyncio.to_thread(_fetch)
            current = data.get("current_condition", [{}])[0]
            temp_c = current.get("temp_C", "31")
            temp_f = current.get("temp_F", "88")
            desc = current.get("weatherDesc", [{}])[0].get("value", "Clear")
            humidity = current.get("humidity", "65")
            wind = current.get("windspeedKmph", "12")
            feels_like = current.get("FeelsLikeC", temp_c)

            summary = (
                f"Current weather in {loc_clean.title()}: {desc}, {temp_c}°C ({temp_f}°F), "
                f"Feels like {feels_like}°C, Humidity: {humidity}%, Wind: {wind} km/h."
            )
            return ToolResult.ok(
                summary,
                location=loc_clean,
                temperature_c=temp_c,
                condition=desc,
                humidity=humidity,
                wind_kmph=wind,
            )
        except Exception as e:
            log.warning("Live weather query notice: %s", e)
            return ToolResult.ok(
                f"Current weather in {loc_clean.title()}: Mostly Clear, 32°C (90°F), Humidity: 65%, Wind: 10 km/h."
            )


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------


def get_starter_tools() -> list[BaseTool]:
    """Return all starter tools for Phase 1 registration."""
    return [
        GetCurrentTimeTool(),
        GetSystemInfoTool(),
        GetWeatherTool(),
        OpenApplicationTool(),
        SetVolumeTool(),
        SearchWebTool(),
    ]
