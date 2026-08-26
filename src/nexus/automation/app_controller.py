"""
NEXUS Desktop Application Controller.

Provides application focus, foreground window discovery, and geometry management.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass

from nexus.utils.logging import get_logger

log = get_logger("automation.app_controller")


@dataclass
class ActiveAppInfo:
    """Metadata describing the currently active foreground application."""

    name: str
    window_title: str
    pid: int
    hwnd: int
    x: int
    y: int
    width: int
    height: int


class DesktopAppController:
    """Controls desktop application focus and window state."""

    def __init__(self) -> None:
        self._is_windows = platform.system() == "Windows"

    def get_active_app(self) -> ActiveAppInfo | None:
        """Retrieve details about the foreground active application."""
        if not self._is_windows:
            return None

        try:
            import ctypes

            import psutil

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None

            # Get Window Title
            length = user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value

            # Get PID & Process Name
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc_name = "Unknown"
            try:
                proc = psutil.Process(pid.value)
                proc_name = proc.name()
            except Exception:
                pass

            # Get Window Rect
            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            w = rect.right - rect.left
            h = rect.bottom - rect.top

            return ActiveAppInfo(
                name=proc_name,
                window_title=title,
                pid=pid.value,
                hwnd=hwnd,
                x=rect.left,
                y=rect.top,
                width=w,
                height=h,
            )
        except Exception as e:
            log.warning("Could not get active application info: %s", e)
            return None

    def focus_app(self, app_name_or_title: str) -> bool:
        """Bring application matching name or title to the foreground."""
        if not self._is_windows:
            return False

        try:
            import ctypes

            user32 = ctypes.windll.user32
            target_clean = app_name_or_title.lower().strip()
            matched_hwnd = None

            def enum_proc(hwnd: int, _lparam: int) -> bool:
                nonlocal matched_hwnd
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value.lower()
                        if target_clean in title:
                            matched_hwnd = hwnd
                            return False
                return True

            wnd_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            user32.EnumWindows(wnd_proc(enum_proc), 0)

            if matched_hwnd:
                user32.ShowWindow(matched_hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(matched_hwnd)
                return True

            return False
        except Exception as e:
            log.warning("Focusing app '%s' failed: %s", app_name_or_title, e)
            return False
