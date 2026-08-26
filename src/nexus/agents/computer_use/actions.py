"""
NEXUS Computer-Use Low-Level OS Action Primitives.

Executes precise mouse clicks, dragging, scrolling, text typing,
and keyboard combinations safely on Windows OS.
"""

from __future__ import annotations

import asyncio
import importlib.util
import time
from typing import Any

from nexus.agents.computer_use.protocol import ActionType, ComputerAction
from nexus.utils.logging import get_logger

log = get_logger("agents.computer_use.actions")

try:
    import pyautogui

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.01
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

HAS_PYWINAUTO = importlib.util.find_spec("pywinauto") is not None


class ComputerActionExecutor:
    """Executes atomic computer actions on Windows OS with safety boundaries."""

    def __init__(self, smooth_mouse: bool = False) -> None:
        self._smooth_mouse = smooth_mouse
        self._screen_width = 1920
        self._screen_height = 1080
        self._refresh_screen_geometry()

    def _refresh_screen_geometry(self) -> None:
        """Update cached screen dimensions."""
        if HAS_PYAUTOGUI:
            try:
                w, h = pyautogui.size()
                self._screen_width = w
                self._screen_height = h
            except Exception as e:
                log.debug("Could not determine screen size: %s", e)

    @property
    def screen_dimensions(self) -> tuple[int, int]:
        return (self._screen_width, self._screen_height)

    def _clamp_coordinates(self, x: int | None, y: int | None) -> tuple[int, int]:
        """Ensure coordinates fall strictly within screen bounds."""
        self._refresh_screen_geometry()
        px = max(0, min(x or 0, self._screen_width - 1))
        py = max(0, min(y or 0, self._screen_height - 1))
        return (px, py)

    async def execute(self, action: ComputerAction) -> dict[str, Any]:
        """Execute a ComputerAction asynchronously."""
        log.info("Executing computer action: %s", action.action_type)
        start_time = time.perf_counter()
        res: dict[str, Any]

        try:
            match action.action_type:
                case ActionType.CLICK:
                    res = await self._click(action)
                case ActionType.DOUBLE_CLICK:
                    res = await self._double_click(action)
                case ActionType.RIGHT_CLICK:
                    res = await self._right_click(action)
                case ActionType.MIDDLE_CLICK:
                    res = await self._middle_click(action)
                case ActionType.MOUSE_MOVE:
                    res = await self._mouse_move(action)
                case ActionType.MOUSE_DRAG:
                    res = await self._mouse_drag(action)
                case ActionType.MOUSE_SCROLL:
                    res = await self._mouse_scroll(action)
                case ActionType.TYPE_TEXT:
                    res = await self._type_text(action)
                case ActionType.CLIPBOARD_PASTE:
                    res = await self._clipboard_paste(action)
                case ActionType.KEY_PRESS:
                    res = await self._key_press(action)
                case ActionType.HOTKEY:
                    res = await self._hotkey(action)
                case ActionType.OPEN_APP:
                    res = await self._open_app(action)
                case ActionType.FOCUS_WINDOW:
                    res = await self._focus_window(action)
                case ActionType.SWITCH_WINDOW:
                    res = await self._switch_window(action)
                case ActionType.WINDOW_MINIMIZE:
                    res = await self._window_minimize(action)
                case ActionType.WINDOW_MAXIMIZE:
                    res = await self._window_maximize(action)
                case ActionType.WINDOW_CLOSE:
                    res = await self._window_close(action)
                case ActionType.WAIT:
                    await asyncio.sleep(max(0.1, min(action.seconds, 30.0)))
                    res = {"status": "waited", "seconds": action.seconds}
                case ActionType.INSPECT_SCREEN | ActionType.SCREENSHOT:
                    res = await self._screenshot(action)
                case ActionType.ASK_USER | ActionType.FINISH:
                    res = {"status": str(action.action_type)}
                case _:
                    res = {"status": "unsupported", "action": str(action.action_type)}

            elapsed = time.perf_counter() - start_time
            res["elapsed_seconds"] = round(elapsed, 3)
            res["success"] = True
            return res

        except Exception as err:
            log.exception("Failed executing action %s: %s", action.action_type, err)
            elapsed = time.perf_counter() - start_time
            return {
                "success": False,
                "error": str(err),
                "action": str(action.action_type),
                "elapsed_seconds": round(elapsed, 3),
            }

    async def _click(self, action: ComputerAction) -> dict[str, Any]:
        if action.x is not None and action.y is not None:
            cx, cy = self._clamp_coordinates(action.x, action.y)
            if HAS_PYAUTOGUI:
                duration = 0.2 if self._smooth_mouse else 0.0
                await asyncio.to_thread(pyautogui.click, x=cx, y=cy, clicks=action.clicks, duration=duration)
            return {"action": "click", "x": cx, "y": cy, "clicks": action.clicks}
        else:
            if HAS_PYAUTOGUI:
                await asyncio.to_thread(pyautogui.click, clicks=action.clicks)
            return {"action": "click", "current_position": True}

    async def _double_click(self, action: ComputerAction) -> dict[str, Any]:
        if action.x is not None and action.y is not None:
            cx, cy = self._clamp_coordinates(action.x, action.y)
            if HAS_PYAUTOGUI:
                await asyncio.to_thread(pyautogui.doubleClick, x=cx, y=cy)
            return {"action": "double_click", "x": cx, "y": cy}
        else:
            if HAS_PYAUTOGUI:
                await asyncio.to_thread(pyautogui.doubleClick)
            return {"action": "double_click", "current_position": True}

    async def _right_click(self, action: ComputerAction) -> dict[str, Any]:
        if action.x is not None and action.y is not None:
            cx, cy = self._clamp_coordinates(action.x, action.y)
            if HAS_PYAUTOGUI:
                await asyncio.to_thread(pyautogui.rightClick, x=cx, y=cy)
            return {"action": "right_click", "x": cx, "y": cy}
        else:
            if HAS_PYAUTOGUI:
                await asyncio.to_thread(pyautogui.rightClick)
            return {"action": "right_click", "current_position": True}

    async def _mouse_move(self, action: ComputerAction) -> dict[str, Any]:
        cx, cy = self._clamp_coordinates(action.x, action.y)
        if HAS_PYAUTOGUI:
            duration = 0.2 if self._smooth_mouse else 0.0
            await asyncio.to_thread(pyautogui.moveTo, cx, cy, duration=duration)
        return {"action": "mouse_move", "x": cx, "y": cy}

    async def _mouse_drag(self, action: ComputerAction) -> dict[str, Any]:
        start_x, start_y = self._clamp_coordinates(action.x, action.y)
        end_x, end_y = self._clamp_coordinates(action.end_x, action.end_y)
        if HAS_PYAUTOGUI:
            await asyncio.to_thread(pyautogui.moveTo, start_x, start_y)
            await asyncio.to_thread(pyautogui.dragTo, end_x, end_y, duration=0.5, button="left")
        return {
            "action": "mouse_drag",
            "from": (start_x, start_y),
            "to": (end_x, end_y),
        }

    async def _mouse_scroll(self, action: ComputerAction) -> dict[str, Any]:
        amount = action.amount if action.direction.lower() in ("up", "top") else -action.amount
        if HAS_PYAUTOGUI:
            if action.x is not None and action.y is not None:
                cx, cy = self._clamp_coordinates(action.x, action.y)
                await asyncio.to_thread(pyautogui.scroll, amount * 120, x=cx, y=cy)
            else:
                await asyncio.to_thread(pyautogui.scroll, amount * 120)
        return {"action": "mouse_scroll", "direction": action.direction, "amount": action.amount}

    async def _type_text(self, action: ComputerAction) -> dict[str, Any]:
        text = action.text or ""
        if HAS_PYAUTOGUI:
            # Fast type execution
            await asyncio.to_thread(pyautogui.write, text, interval=0.005)
        return {"action": "type_text", "length": len(text)}

    async def _key_press(self, action: ComputerAction) -> dict[str, Any]:
        key = (action.key or "").lower().strip()
        if HAS_PYAUTOGUI and key:
            await asyncio.to_thread(pyautogui.press, key)
        return {"action": "key_press", "key": key}

    async def _hotkey(self, action: ComputerAction) -> dict[str, Any]:
        keys = action.keys or []
        if not keys and action.key:
            keys = [k.strip() for k in action.key.split("+")]
        if HAS_PYAUTOGUI and keys:
            await asyncio.to_thread(pyautogui.hotkey, *keys)
        return {"action": "hotkey", "keys": keys}

    async def _clipboard_paste(self, action: ComputerAction) -> dict[str, Any]:
        """Paste text using system clipboard for rapid and 100% accurate multiline typing."""
        text = action.text or ""
        try:
            import pyperclip

            await asyncio.to_thread(pyperclip.copy, text)
            if HAS_PYAUTOGUI:
                await asyncio.to_thread(pyautogui.hotkey, "ctrl", "v")
            return {"action": "clipboard_paste", "length": len(text), "success": True}
        except Exception as e:
            log.debug("Clipboard paste fallback to direct typing: %s", e)
            if HAS_PYAUTOGUI:
                await asyncio.to_thread(pyautogui.write, text, interval=0.01)
            return {"action": "clipboard_paste", "fallback_typed": True, "length": len(text)}

    async def _middle_click(self, action: ComputerAction) -> dict[str, Any]:
        if action.x is not None and action.y is not None:
            cx, cy = self._clamp_coordinates(action.x, action.y)
            if HAS_PYAUTOGUI:
                await asyncio.to_thread(pyautogui.middleClick, x=cx, y=cy)
            return {"action": "middle_click", "x": cx, "y": cy}
        else:
            if HAS_PYAUTOGUI:
                await asyncio.to_thread(pyautogui.middleClick)
            return {"action": "middle_click", "current_position": True}

    async def _open_app(self, action: ComputerAction) -> dict[str, Any]:
        """Directly launch a Windows application or executable by name or common alias."""
        import subprocess

        target = (action.app_name or action.text or "").strip().lower()
        if not target:
            return {"action": "open_app", "success": False, "error": "No app name provided"}

        app_map = {
            "notepad": "notepad.exe",
            "calc": "calc.exe",
            "calculator": "calc.exe",
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "edge": "msedge.exe",
            "microsoft edge": "msedge.exe",
            "browser": "msedge.exe",
            "explorer": "explorer.exe",
            "file explorer": "explorer.exe",
            "files": "explorer.exe",
            "terminal": "powershell.exe",
            "powershell": "powershell.exe",
            "cmd": "cmd.exe",
            "command prompt": "cmd.exe",
            "vscode": "code",
            "vs code": "code",
            "code": "code",
            "task manager": "taskmgr.exe",
            "taskmgr": "taskmgr.exe",
            "settings": "ms-settings:",
            "battery saver": "ms-settings:batterysaver",
            "energy saver": "ms-settings:batterysaver",
            "battery": "ms-settings:batterysaver",
            "wifi": "ms-settings:network-wifi",
            "bluetooth": "ms-settings:bluetooth",
            "sound": "ms-settings:sound",
            "volume": "ms-settings:sound",
            "display": "ms-settings:display",
            "camera": "microsoft.windows.camera:",
            "webcam": "microsoft.windows.camera:",
            "photos": "ms-photos:",
            "paint": "mspaint.exe",
            "snipping tool": "snippingtool.exe",
            "word": "winword.exe",
            "excel": "excel.exe",
            "powerpoint": "powerpnt.exe",
            "spotify": "spotify.exe",
            "slack": "slack.exe",
            "discord": "discord.exe",
        }

        # 1. Direct Web Search / URL launch
        if target.startswith("http://") or target.startswith("https://") or target.startswith("www."):
            import webbrowser
            url = target if target.startswith("http") else f"https://{target}"
            webbrowser.open(url)
            await asyncio.sleep(1.0)
            return {"action": "open_app", "target": url, "success": True}

        if "google" in target or "search" in target:
            import urllib.parse
            import webbrowser
            query = target.replace("google", "").replace("search", "").replace("for", "").replace("la", "").replace("pannu", "").strip()
            if not query:
                query = "weather"
            url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
            webbrowser.open(url)
            await asyncio.sleep(1.0)
            return {"action": "open_app", "target": url, "success": True}

        cmd = app_map.get(target, target)
        try:
            if ":" in cmd and not cmd.endswith(".exe"):
                import os
                os.startfile(cmd)
            else:
                subprocess.Popen(cmd, shell=True)
            
            # Wait for app window to appear and bring it to foreground without shrinking
            await asyncio.sleep(1.0)
            await self._bring_window_to_foreground(target)
            return {"action": "open_app", "target": cmd, "success": True}
        except Exception as err:
            log.warning("Could not launch app %s: %s", cmd, err)
            return {"action": "open_app", "target": cmd, "success": False, "error": str(err)}

    async def _bring_window_to_foreground(self, query: str) -> bool:
        """Force bring a matching window to the top foreground without resizing/shrinking maximized windows."""
        def _force_front() -> bool:
            try:
                import ctypes
                import pygetwindow as gw

                q = query.lower().strip()
                windows = gw.getAllWindows()
                matched = [w for w in windows if (q in w.title.lower() or w.title.lower() in q) and w.title.strip()]
                
                # If specific app aliases like camera
                if not matched and ("camera" in q or "webcam" in q):
                    matched = [w for w in windows if "camera" in w.title.lower()]

                if matched:
                    win = matched[0]
                    hwnd = win._hWnd
                    user32 = ctypes.windll.user32
                    # Only restore if currently minimized (IsIconic) to avoid un-maximizing maximized windows!
                    if user32.IsIconic(hwnd):
                        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    else:
                        user32.ShowWindow(hwnd, 5)  # SW_SHOW (preserves maximized state!)

                    # Simulate ALT key to bypass Windows SetForegroundWindow restrictions
                    user32.keybd_event(0x12, 0, 0, 0)
                    user32.SetForegroundWindow(hwnd)
                    user32.keybd_event(0x12, 0, 2, 0)
                    try:
                        win.activate()
                    except Exception:
                        pass
                    return True
            except Exception as e:
                log.debug("Foreground activation notice: %s", e)
            return False

        return await asyncio.to_thread(_force_front)

    async def _focus_window(self, action: ComputerAction) -> dict[str, Any]:
        """Focus an existing window by title match and bring to foreground."""
        target_title = (action.text or action.app_name or "").strip().lower()
        if not target_title:
            return {"action": "focus_window", "success": False}

        brought = await self._bring_window_to_foreground(target_title)
        if brought:
            return {"action": "focus_window", "target": target_title, "success": True}

        try:
            import pygetwindow as gw
            windows = gw.getAllWindows()
            matched = [w for w in windows if target_title in w.title.lower()]
            if matched:
                win = matched[0]
                if win.isMinimized:
                    win.restore()
                win.activate()
                return {"action": "focus_window", "title": win.title, "success": True}
        except Exception as e:
            log.debug("Window focus notice: %s", e)

        return {"action": "focus_window", "target": target_title, "success": False}

    async def _switch_window(self, action: ComputerAction) -> dict[str, Any]:
        """Switch window using Alt+Tab."""
        if HAS_PYAUTOGUI:
            await asyncio.to_thread(pyautogui.hotkey, "alt", "tab")
        return {"action": "switch_window", "success": True}

    async def _window_minimize(self, action: ComputerAction) -> dict[str, Any]:
        """Minimize the active window or target window."""
        try:
            import pygetwindow as gw
            win = gw.getActiveWindow()
            if win:
                win.minimize()
                return {"action": "window_minimize", "title": win.title, "success": True}
        except Exception as e:
            log.debug("Window minimize notice: %s", e)
        if HAS_PYAUTOGUI:
            await asyncio.to_thread(pyautogui.hotkey, "win", "down")
        return {"action": "window_minimize", "success": True}

    async def _window_maximize(self, action: ComputerAction) -> dict[str, Any]:
        """Maximize the active window or target window."""
        try:
            import pygetwindow as gw
            win = gw.getActiveWindow()
            if win:
                win.maximize()
                return {"action": "window_maximize", "title": win.title, "success": True}
        except Exception as e:
            log.debug("Window maximize notice: %s", e)
        if HAS_PYAUTOGUI:
            await asyncio.to_thread(pyautogui.hotkey, "win", "up")
        return {"action": "window_maximize", "success": True}

    async def _window_close(self, action: ComputerAction) -> dict[str, Any]:
        """Close target application window or active window safely."""
        target_app = (action.app_name or action.text or "").strip().lower()

        # If a specific app was targeted (e.g. camera, notepad, chrome)
        if target_app:
            try:
                import pygetwindow as gw
                windows = gw.getAllWindows()
                matched = [w for w in windows if (target_app in w.title.lower() or w.title.lower() in target_app) and w.title.strip()]
                if matched:
                    win = matched[0]
                    # Focus first then close
                    win.activate()
                    await asyncio.sleep(0.2)
                    win.close()
                    return {"action": "window_close", "target": target_app, "title": win.title, "success": True}
            except Exception as e:
                log.debug("Targeted window close fallback: %s", e)

        # Active window close
        try:
            import pygetwindow as gw
            win = gw.getActiveWindow()
            if win:
                title = win.title.lower()
                # Safety protection: never close Nexus app unless explicitly forced
                if "nexus" in title and not target_app:
                    log.warning("Protected active Nexus window from accidental window_close.")
                    return {"action": "window_close", "skipped": True, "reason": "Protected Nexus window"}
                win.close()
                return {"action": "window_close", "title": win.title, "success": True}
        except Exception as e:
            log.debug("Active window close notice: %s", e)

        if HAS_PYAUTOGUI:
            await asyncio.to_thread(pyautogui.hotkey, "alt", "f4")
        return {"action": "window_close", "success": True}

    async def _screenshot(self, action: ComputerAction) -> dict[str, Any]:
        """Capture live screen state."""
        from nexus.vision.capture import ScreenCaptureController
        cap = ScreenCaptureController()
        shot = await cap.capture()
        return {"action": "screenshot", "path": shot.image_path, "success": True}
