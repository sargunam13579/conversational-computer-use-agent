"""
NEXUS Visual Grounding & Set-of-Marks (SoM) Engine.

Translates visual cues, bounding boxes, UI trees, and coordinates
into actionable targets for the Multimodal LLM.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from nexus.agents.computer_use.protocol import Coordinate, ScreenObservation
from nexus.utils.logging import get_logger
from nexus.vision.capture import ScreenCaptureController
from nexus.vision.ocr import ScreenOCR
from nexus.vision.ui_detector import UIElementDetector

log = get_logger("agents.computer_use.grounding")


class VisualGroundingEngine:
    """Provides visual grounding, element tagging, and coordinate translation."""

    def __init__(
        self,
        capture: ScreenCaptureController | None = None,
        detector: UIElementDetector | None = None,
        ocr: ScreenOCR | None = None,
    ) -> None:
        self._capture = capture or ScreenCaptureController()
        self._detector = detector or UIElementDetector()
        self._ocr = ocr or ScreenOCR()

    async def observe_screen(self, tag_elements: bool = True) -> ScreenObservation:
        """Capture screen and detect UI elements with optional Set-of-Marks visual overlay."""
        timestamp = time.time()
        obs = ScreenObservation(timestamp=timestamp)

        # 1. Screen Capture
        shot = await self._capture.capture()
        obs.screenshot_path = shot.image_path
        obs.screen_width = shot.width
        obs.screen_height = shot.height
        if shot.active_window:
            obs.active_window = shot.active_window.title

        # 2. Extract UI controls and OCR text blocks
        detected: list[dict[str, Any]] = []
        try:
            elements = await asyncio.to_thread(self._detector.detect_elements)
            for el in elements[:30]:
                detected.append(
                    {
                        "id": el.element_id,
                        "name": el.name,
                        "type": str(el.element_type),
                        "x": el.x,
                        "y": el.y,
                        "width": el.width,
                        "height": el.height,
                        "center": el.center,
                    }
                )
        except Exception as e:
            log.debug("UI element detection notice: %s", e)

        # Extract visible text labels & chat titles via OCR for browser/canvas UI
        try:
            if obs.screenshot_path and os.path.exists(obs.screenshot_path):
                ocr_res = await self._ocr.recognize(obs.screenshot_path)
                text_blocks = []
                for b in ocr_res.blocks[:40]:
                    txt = b.text.strip()
                    if txt and len(txt) > 1:
                        text_blocks.append(b)
                        detected.append(
                            {
                                "id": f"txt-{len(detected)+1}",
                                "name": txt,
                                "type": "label",
                                "x": b.x,
                                "y": b.y,
                                "width": b.width,
                                "height": b.height,
                                "center": b.center,
                            }
                        )

                # Contextual 3-dot / More Options detection for sidebar chat cards & list items:
                # In sidebar cards (width ~200-250px on left side), each chat item row has a 3-dots button on its right side.
                for b in text_blocks:
                    txt = b.text.strip()
                    # If item is located in left sidebar (x < 260) and is not a header/system label
                    if b.x < 220 and b.y > 60 and len(txt) > 1 and not any(kw in txt.lower() for kw in ["nex", "agent", "history", "search", "new chat"]):
                        # Synthesize 3-dot menu button coordinate at the right edge of this chat row
                        dot_cx = min(int(obs.screen_width * 0.12), b.x + 190)
                        dot_cy = b.center[1]
                        detected.append(
                            {
                                "id": f"btn-3dot-{len(detected)+1}",
                                "name": f"3-dots options menu for '{txt}'",
                                "type": "button",
                                "x": dot_cx - 14,
                                "y": dot_cy - 14,
                                "width": 28,
                                "height": 28,
                                "center": (dot_cx, dot_cy),
                            }
                        )
        except Exception as ocr_err:
            log.debug("OCR visual grounding notice: %s", ocr_err)

        for idx, item in enumerate(detected[:70]):
            item["index"] = idx + 1
        obs.detected_elements = detected[:70]

        # 3. Create Set-of-Marks Overlay Image
        if tag_elements and obs.screenshot_path and os.path.exists(obs.screenshot_path) and obs.detected_elements:
            try:
                som_path = await self._generate_som_image(obs.screenshot_path, obs.detected_elements)
                obs.som_screenshot_path = som_path
            except Exception as e:
                log.warning("Could not generate SoM overlay: %s", e)
                obs.som_screenshot_path = obs.screenshot_path
        else:
            obs.som_screenshot_path = obs.screenshot_path

        # 4. Optional base64 encoding for fast API delivery
        target_path = obs.som_screenshot_path or obs.screenshot_path
        if target_path and os.path.exists(target_path):
            try:
                import base64
                with open(target_path, "rb") as f:
                    obs.som_base64_image = base64.b64encode(f.read()).decode("utf-8")
                if obs.screenshot_path and os.path.exists(obs.screenshot_path) and obs.screenshot_path != target_path:
                    with open(obs.screenshot_path, "rb") as f:
                        obs.base64_image = base64.b64encode(f.read()).decode("utf-8")
                else:
                    obs.base64_image = obs.som_base64_image
            except Exception as e:
                log.debug("Screenshot base64 conversion notice: %s", e)

        return obs

    async def _generate_som_image(
        self, original_path: str, elements: list[dict[str, Any]]
    ) -> str:
        """Render numerical tag badges and bounding boxes onto a copy of the screenshot."""
        def _draw() -> str:
            with Image.open(original_path) as img:
                annotated = img.convert("RGBA")
                overlay = Image.new("RGBA", annotated.size, (255, 255, 255, 0))
                draw = ImageDraw.Draw(overlay)

                # Try loading basic font or default
                try:
                    font = ImageFont.load_default()
                except Exception:
                    font = None

                for el in elements:
                    idx = el.get("index", 1)
                    x, y, w, h = el["x"], el["y"], el["width"], el["height"]

                    if w <= 0 or h <= 0:
                        continue

                    # Draw high-visibility bounding box
                    draw.rectangle(
                        [x, y, x + w, y + h],
                        outline=(0, 240, 255, 220),
                        width=2,
                    )

                    # Draw badge label in top-left corner
                    badge_w, badge_h = max(24, len(str(idx)) * 10 + 10), 18
                    badge_y = max(0, y - badge_h)
                    draw.rectangle(
                        [x, badge_y, x + badge_w, badge_y + badge_h],
                        fill=(10, 15, 30, 230),
                        outline=(0, 240, 255, 255),
                        width=1,
                    )
                    draw.text(
                        (x + 4, badge_y + 2),
                        f"#{idx}",
                        fill=(0, 240, 255, 255),
                        font=font,
                    )

                combined = Image.alpha_composite(annotated, overlay).convert("RGB")
                tmp_dir = tempfile.gettempdir()
                som_path = os.path.join(tmp_dir, f"nexus_som_{int(time.time() * 1000)}.png")
                combined.save(som_path, format="PNG")
                return som_path

        return await asyncio.to_thread(_draw)

    def find_element(
        self, elements: list[dict[str, Any]], query: str | int
    ) -> dict[str, Any] | None:
        """Find detected element by numeric badge index or text name."""
        if isinstance(query, int) or (isinstance(query, str) and query.isdigit()):
            target_idx = int(query)
            for el in elements:
                if el.get("index") == target_idx:
                    return el

        if isinstance(query, str):
            q_lower = query.lower().strip()
            # Exact name match first
            for el in elements:
                if (el.get("name") or "").lower().strip() == q_lower:
                    return el
            # Substring match
            for el in elements:
                if q_lower in (el.get("name") or "").lower():
                    return el

        return None

    def normalize_coordinates(
        self, norm_x: float, norm_y: float, screen_width: int, screen_height: int
    ) -> Coordinate:
        """Convert relative [0, 1000] coordinates to absolute screen pixels."""
        px = int((norm_x / 1000.0) * screen_width)
        py = int((norm_y / 1000.0) * screen_height)
        return Coordinate(x=px, y=py)

    def denormalize_coordinates(
        self, px: int, py: int, screen_width: int, screen_height: int
    ) -> tuple[int, int]:
        """Convert absolute screen pixels to normalized [0, 1000] coordinates."""
        norm_x = int((px / max(1, screen_width)) * 1000)
        norm_y = int((py / max(1, screen_height)) * 1000)
        return (norm_x, norm_y)
