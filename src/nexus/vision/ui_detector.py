"""
NEXUS UI Element Detection & Spatial Localization Engine.

Detects, classifies, and indexes interactive UI elements on the Windows screen:
- Buttons, input fields, menus, tabs, checkboxes, comboboxes, tree items
- Computes exact pixel coordinates (x, y, w, h) and center click targets (cx, cy)
- Resolves spatial descriptions ("top-right", "bottom-center", "left panel")
- Semantic element searching and fuzzy matching
"""

from __future__ import annotations

import difflib
import platform
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from nexus.utils.logging import get_logger

log = get_logger("vision.ui_detector")


class UIElementType(StrEnum):
    """Types of detected UI controls."""

    BUTTON = "button"
    INPUT_FIELD = "input_field"
    MENU = "menu"
    MENU_ITEM = "menu_item"
    TAB = "tab"
    CHECKBOX = "checkbox"
    COMBOBOX = "combobox"
    TEXT = "text"
    WINDOW = "window"
    LINK = "link"
    TREE_ITEM = "tree_item"
    UNKNOWN = "unknown"


@dataclass
class UIElement:
    """A detected interactive or structural UI element on screen."""

    element_id: str
    element_type: UIElementType
    name: str
    x: int
    y: int
    width: int
    height: int
    is_enabled: bool = True
    window_title: str | None = None
    automation_id: str = ""
    control_type: str = ""
    confidence: float = 1.0

    @property
    def center(self) -> tuple[int, int]:
        """Center point (cx, cy) of the element for clicking."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        """Bounding box tuple (x, y, w, h)."""
        return (self.x, self.y, self.width, self.height)

    @property
    def relative_position(self) -> str:
        """Calculate human-friendly spatial location on 1920x1080 normalized screen."""
        cx, cy = self.center
        # Assume standard 1920x1080 screen bounds for relative quadrant
        horiz = "left" if cx < 640 else ("right" if cx > 1280 else "center")
        vert = "top" if cy < 360 else ("bottom" if cy > 720 else "middle")

        if horiz == "center" and vert == "middle":
            return "center of the screen"
        return f"{vert}-{horiz}"


class UIElementDetector:
    """
    Inspects Windows desktop and extracts structured UI elements.
    """

    def __init__(self) -> None:
        self._is_windows = platform.system() == "Windows"

    def _map_control_type(self, control_type_str: str) -> UIElementType:
        """Map Windows control type name to UIElementType enum."""
        c = control_type_str.lower()
        if "button" in c:
            return UIElementType.BUTTON
        elif "edit" in c or "textbox" in c or "document" in c:
            return UIElementType.INPUT_FIELD
        elif "menuitem" in c:
            return UIElementType.MENU_ITEM
        elif "menu" in c:
            return UIElementType.MENU
        elif "tab" in c:
            return UIElementType.TAB
        elif "check" in c:
            return UIElementType.CHECKBOX
        elif "combo" in c or "drop" in c:
            return UIElementType.COMBOBOX
        elif "tree" in c:
            return UIElementType.TREE_ITEM
        elif "hyperlink" in c or "link" in c:
            return UIElementType.LINK
        elif "text" in c or "label" in c:
            return UIElementType.TEXT
        elif "window" in c or "pane" in c:
            return UIElementType.WINDOW
        return UIElementType.UNKNOWN

    def _default_mock_elements(self) -> list[UIElement]:
        """Return fallback UI elements when UIA is unavailable or in headless mode."""
        return [
            UIElement(
                "btn-1",
                UIElementType.BUTTON,
                "Run",
                1600,
                80,
                80,
                32,
                window_title="Visual Studio Code",
            ),
            UIElement(
                "btn-2",
                UIElementType.BUTTON,
                "Debug",
                1700,
                80,
                80,
                32,
                window_title="Visual Studio Code",
            ),
            UIElement(
                "input-1",
                UIElementType.INPUT_FIELD,
                "Search",
                800,
                50,
                300,
                30,
                window_title="Visual Studio Code",
            ),
            UIElement(
                "menu-1",
                UIElementType.MENU_ITEM,
                "File",
                20,
                10,
                40,
                20,
                window_title="Visual Studio Code",
            ),
            UIElement(
                "menu-2",
                UIElementType.MENU_ITEM,
                "Edit",
                70,
                10,
                40,
                20,
                window_title="Visual Studio Code",
            ),
        ]

    def detect_elements(self, window_title: str | None = None) -> list[UIElement]:
        """
        Detect interactive UI elements from foreground window or desktop.
        """
        if not self._is_windows:
            return self._default_mock_elements()

        elements: list[UIElement] = []
        try:
            import ctypes
            import importlib

            pywinauto: Any = importlib.import_module("pywinauto")

            top_win = None
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                try:
                    app = pywinauto.Application(backend="uia").connect(handle=hwnd)
                    top_win = app.window(handle=hwnd)
                except Exception:
                    pass

            if top_win is None:
                desktop = pywinauto.Desktop(backend="uia")
                wins = desktop.windows()
                top_win = wins[0] if wins else None

            if top_win:
                win_name = top_win.window_text()
                descendants = top_win.descendants()
                idx = 1
                for control in descendants:
                    try:
                        c_type_str = (
                            control.friendly_class_name() or control.element_info.control_type or ""
                        )
                        elem_type = self._map_control_type(c_type_str)

                        if elem_type in (UIElementType.UNKNOWN, UIElementType.WINDOW):
                            continue

                        name = control.window_text().strip()
                        rect = control.rectangle()
                        w = rect.width()
                        h = rect.height()

                        if w <= 0 or h <= 0 or not control.is_visible():
                            continue

                        elem_id = f"el-{idx}"
                        idx += 1

                        auto_id = getattr(control.element_info, "automation_id", "") or ""
                        enabled = control.is_enabled() if hasattr(control, "is_enabled") else True

                        elements.append(
                            UIElement(
                                element_id=elem_id,
                                element_type=elem_type,
                                name=name or auto_id or f"Unnamed {elem_type.value}",
                                x=rect.left,
                                y=rect.top,
                                width=w,
                                height=h,
                                is_enabled=enabled,
                                window_title=win_name,
                                automation_id=auto_id,
                                control_type=c_type_str,
                            )
                        )
                    except Exception:
                        continue
        except Exception as e:
            log.warning("UI Automation element detection error: %s", e)

        return elements

    def detect_interactive_elements(self, window_title: str | None = None) -> list[UIElement]:
        """Alias for detect_elements returning interactive controls."""
        return self.detect_elements(window_title=window_title)

    def find_element(
        self,
        query: str,
        element_type: UIElementType | str | None = None,
        elements: list[UIElement] | None = None,
    ) -> UIElement | None:
        """
        Locate the best matching UI element by name, role, or label.

        Args:
            query: Label or keyword to search (e.g. "Run", "Search", "File").
            element_type: Optional filter by UIElementType.
            elements: Optional pre-detected element list.
        """
        candidates = elements if elements is not None else self.detect_elements()
        query_clean = query.strip().lower()

        target_type_str = str(element_type).lower() if element_type else None

        best_match: UIElement | None = None
        best_score = 0.0

        for el in candidates:
            if (
                target_type_str
                and el.element_type.value.lower() != target_type_str
                and target_type_str not in el.element_type.value.lower()
            ):
                continue

            el_name = el.name.lower()
            el_id = el.automation_id.lower()

            # 1. Exact match
            if query_clean in (el_name, el_id):
                return el

            # 2. Substring match
            if query_clean in el_name:
                score = 0.8 + (len(query_clean) / max(len(el_name), 1)) * 0.15
            else:
                # 3. Fuzzy similarity ratio
                score = difflib.SequenceMatcher(None, query_clean, el_name).ratio()

            if score > best_score and score >= 0.5:
                best_score = score
                best_match = el

        return best_match
