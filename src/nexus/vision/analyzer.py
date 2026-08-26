"""
NEXUS Screen Understanding & Scene Description Analyzer.

Combines screen capture, OCR, and UI element detection to produce high-level
natural language screen descriptions and resolve spatial element queries.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from nexus.utils.logging import get_logger
from nexus.vision.capture import ScreenCaptureController, WindowInfo
from nexus.vision.ocr import OCRResult, ScreenOCR
from nexus.vision.privacy import ScreenPrivacyManager
from nexus.vision.ui_detector import UIElement, UIElementDetector, UIElementType

log = get_logger("vision.analyzer")


@dataclass
class ScreenAnalysisReport:
    """Comprehensive analysis report of the screen state."""

    active_window: WindowInfo | None
    app_name: str
    window_title: str
    description: str
    elements: list[UIElement] = field(default_factory=list)
    buttons: list[str] = field(default_factory=list)
    input_fields: list[str] = field(default_factory=list)
    menus: list[str] = field(default_factory=list)
    ocr_text_preview: str = ""
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())


class ScreenAnalyzer:
    """
    High-level reasoning and scene understanding engine for the laptop screen.
    """

    def __init__(
        self,
        privacy_manager: ScreenPrivacyManager | None = None,
        capture_controller: ScreenCaptureController | None = None,
        ocr_engine: ScreenOCR | None = None,
        element_detector: UIElementDetector | None = None,
    ) -> None:
        self.privacy = privacy_manager or ScreenPrivacyManager()
        self.capture_ctrl = capture_controller or ScreenCaptureController(self.privacy)
        self.ocr = ocr_engine or ScreenOCR()
        self.detector = element_detector or UIElementDetector()

    def _infer_app_context(self, active_win: WindowInfo | None, ocr_text: str) -> str:
        """Infer application context and open document/task."""
        if not active_win:
            return "Windows Desktop"

        title = active_win.title.lower()
        proc = active_win.process_name.lower()

        if "code" in proc or "visual studio code" in title:
            if "error" in ocr_text.lower() or "exception" in ocr_text.lower():
                return (
                    f"VS Code (Active window: '{active_win.title}'). "
                    "There is code with a visible error or notification on screen."
                )
            return f"VS Code (Editing: '{active_win.title}')"
        elif "chrome" in proc or "edge" in proc or "firefox" in proc or "brave" in proc:
            return f"Web Browser (Viewing: '{active_win.title}')"
        elif "notepad" in proc:
            return f"Notepad (Document: '{active_win.title}')"
        elif "explorer" in proc:
            return f"File Explorer (Folder: '{active_win.title}')"
        elif "cmd" in proc or "powershell" in proc or "wt" in proc:
            return f"Terminal ({active_win.title})"

        return f"{active_win.process_name} ('{active_win.title}')"

    async def analyze_screen(
        self,
        crop_to_active_window: bool = False,
        source: str = "assistant",
    ) -> ScreenAnalysisReport:
        """
        Capture and perform complete screen understanding.
        """
        cap_res = await self.capture_ctrl.capture(
            crop_to_active_window=crop_to_active_window, source=source
        )

        if not cap_res.success:
            return ScreenAnalysisReport(
                active_window=cap_res.active_window,
                app_name="Unavailable",
                window_title="Unavailable",
                description=f"Screen capture could not be completed: {cap_res.error}",
            )

        # 1. OCR text detection
        target_img = cap_res.image_path or cap_res.image
        if target_img:
            ocr_res = await self.ocr.recognize(target_img)
        else:
            ocr_res = OCRResult(success=True, full_text="")

        # 2. UI element detection
        elements = self.detector.detect_elements(
            window_title=cap_res.active_window.title if cap_res.active_window else None
        )

        buttons = [e.name for e in elements if e.element_type == UIElementType.BUTTON and e.name]
        inputs = [
            e.name for e in elements if e.element_type == UIElementType.INPUT_FIELD and e.name
        ]
        menus = [
            e.name
            for e in elements
            if e.element_type in (UIElementType.MENU, UIElementType.MENU_ITEM) and e.name
        ]

        # 3. Context generation
        app_ctx = self._infer_app_context(cap_res.active_window, ocr_res.full_text)

        desc_parts = [f"You have {app_ctx}."]
        if buttons:
            desc_parts.append(f"Visible buttons include: {', '.join(buttons[:6])}.")
        if inputs:
            desc_parts.append(f"Input fields: {', '.join(inputs[:4])}.")
        if menus:
            desc_parts.append(f"Menus: {', '.join(menus[:6])}.")

        # Snippet of OCR text
        ocr_preview = ocr_res.full_text[:300].strip() if ocr_res.full_text else ""
        if ocr_preview:
            clean_snippet = " ".join(ocr_preview.split())
            desc_parts.append(f'Screen text: "{clean_snippet[:150]}..."')

        full_desc = " ".join(desc_parts)

        return ScreenAnalysisReport(
            active_window=cap_res.active_window,
            app_name=cap_res.active_window.process_name if cap_res.active_window else "Desktop",
            window_title=cap_res.active_window.title if cap_res.active_window else "Desktop",
            description=full_desc,
            elements=elements,
            buttons=buttons,
            input_fields=inputs,
            menus=menus,
            ocr_text_preview=ocr_preview,
        )

    def locate_element(
        self, query: str, element_type: str | None = None
    ) -> tuple[UIElement | None, str]:
        """
        Locate a specific element and return its spatial location explanation.

        Returns:
            (element, explanation_string)
        """
        target = self.detector.find_element(query, element_type=element_type)
        if not target:
            return None, f"Could not find UI element matching '{query}' on screen."

        loc_str = target.relative_position
        cx, cy = target.center
        explanation = (
            f"The '{target.name}' {target.element_type.value} is located at the {loc_str} "
            f"(coordinates: x={cx}, y={cy})."
        )
        return target, explanation
