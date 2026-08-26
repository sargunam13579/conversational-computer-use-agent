"""
NEXUS Desktop UI Interaction — Control Clicks, Typing, Scrolling, and Shortcut Actions.

Provides desktop automation via Win32 UIA, PyAutoGUI, and ctypes fallbacks.
"""

from __future__ import annotations

import importlib
import platform
import time
from typing import TYPE_CHECKING, Any

from nexus.automation.app_controller import DesktopAppController
from nexus.utils.logging import get_logger

if TYPE_CHECKING:
    from nexus.vision.ui_detector import UIElementDetector

log = get_logger("automation.ui_interaction")

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800


class DesktopUIInteraction:
    """Automates user interactions with desktop application controls."""

    def __init__(
        self,
        app_controller: DesktopAppController | None = None,
        detector: UIElementDetector | None = None,
    ) -> None:
        self._app_controller = app_controller or DesktopAppController()
        self._detector = detector
        self._is_windows = platform.system() == "Windows"

    def _get_detector(self) -> Any:
        if self._detector is None:
            from nexus.vision.ui_detector import UIElementDetector

            self._detector = UIElementDetector()
        return self._detector

    def click_element(
        self,
        element_name_or_query: str,
        double_click: bool = False,
        right_click: bool = False,
    ) -> bool:
        """Find a UI element by name in the active application and click it."""
        detector = self._get_detector()
        element = detector.find_element(element_name_or_query)
        if not element:
            log.warning("Could not find UI element: '%s'", element_name_or_query)
            return False

        cx, cy = element.center
        return self.click_at(cx, cy, double_click=double_click, right_click=right_click)

    def click_at(
        self,
        x: int,
        y: int,
        double_click: bool = False,
        right_click: bool = False,
    ) -> bool:
        """Click at absolute screen coordinates."""
        if not self._is_windows:
            return False

        try:
            import ctypes

            user32 = ctypes.windll.user32
            user32.SetCursorPos(x, y)
            time.sleep(0.05)

            if right_click:
                user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, x, y, 0, 0)
                user32.mouse_event(MOUSEEVENTF_RIGHTUP, x, y, 0, 0)
            else:
                user32.mouse_event(MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
                user32.mouse_event(MOUSEEVENTF_LEFTUP, x, y, 0, 0)
                if double_click:
                    time.sleep(0.1)
                    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
                    user32.mouse_event(MOUSEEVENTF_LEFTUP, x, y, 0, 0)
            return True
        except Exception as e:
            log.warning("Click at (%d, %d) failed: %s", x, y, e)
            try:
                pyautogui: Any = importlib.import_module("pyautogui")

                if double_click:
                    pyautogui.doubleClick(x, y)
                elif right_click:
                    pyautogui.rightClick(x, y)
                else:
                    pyautogui.click(x, y)
                return True
            except Exception:
                return False

    def type_into_element(
        self,
        text: str,
        element_name: str | None = None,
        press_enter: bool = False,
    ) -> bool:
        """Focus target element (or current active control) and type text."""
        if element_name:
            clicked = self.click_element(element_name)
            if not clicked:
                log.warning("Could not focus element '%s' before typing", element_name)
            time.sleep(0.1)

        if not self._is_windows:
            return False

        try:
            pyautogui: Any = importlib.import_module("pyautogui")

            pyautogui.write(text, interval=0.01)
            if press_enter:
                pyautogui.press("enter")
            return True
        except Exception as e:
            log.warning("PyAutoGUI type failed: %s, trying PowerShell fallback", e)
            try:
                import subprocess

                ps_script = f"""
                $wsh = New-Object -ComObject WScript.Shell
                $wsh.SendKeys('{text}')
                """
                if press_enter:
                    ps_script += "\n$wsh.SendKeys('{ENTER}')"
                subprocess.run(
                    ["powershell", "-Command", ps_script], capture_output=True, timeout=5
                )
                return True
            except Exception:
                return False

    def scroll(self, direction: str = "down", clicks: int = 5) -> bool:
        """Scroll mouse wheel in active application window."""
        if not self._is_windows:
            return False

        wheel_delta = -120 * clicks if direction.lower() in ("down", "bottom") else 120 * clicks
        try:
            import ctypes

            user32 = ctypes.windll.user32
            # mouse_event(dwFlags, dx, dy, dwData, dwExtraInfo)
            user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, wheel_delta, 0)
            return True
        except Exception as e:
            log.warning("ctypes scroll failed: %s, trying pyautogui fallback", e)
            try:
                pyautogui: Any = importlib.import_module("pyautogui")

                amount = -clicks if direction.lower() in ("down", "bottom") else clicks
                pyautogui.scroll(amount)
                return True
            except Exception:
                return False

    def send_hotkey(self, *keys: str) -> bool:
        """Send keyboard shortcut (e.g. 'ctrl', 's' or 'alt', 'f4')."""
        try:
            pyautogui: Any = importlib.import_module("pyautogui")

            pyautogui.hotkey(*keys)
            return True
        except Exception as e:
            log.warning("Hotkey %s failed: %s", keys, e)
            return False
