"""
NEXUS Screen OCR & Text Detection Engine.

Extracts visible text, labels, coordinates, and bounding boxes from screenshots
and active application windows.
"""

from __future__ import annotations

import json
import platform
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from nexus.utils.logging import get_logger

log = get_logger("vision.ocr")


@dataclass
class TextBlock:
    """A detected text block with bounding box and confidence."""

    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0
    line_number: int = 1

    @property
    def center(self) -> tuple[int, int]:
        """Center coordinate (cx, cy) of text block."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        """Bounding box tuple (x, y, w, h)."""
        return (self.x, self.y, self.width, self.height)


@dataclass
class OCRResult:
    """Result of screen text recognition."""

    success: bool
    full_text: str
    blocks: list[TextBlock] = field(default_factory=list)
    word_count: int = 0
    line_count: int = 0
    duration_ms: float = 0.0
    error: str | None = None


class ScreenOCR:
    """
    Multi-engine OCR processor for Windows screen images.
    """

    def __init__(self) -> None:
        self._is_windows = platform.system() == "Windows"

    def _ocr_via_windows_media_ocr(self, image_path: str) -> list[TextBlock]:
        """Run native Windows.Media.Ocr via PowerShell WinRT bridge."""
        if not self._is_windows:
            return []

        ps_script = f"""
        [Windows.Globalization.Language, Windows.Foundation, ContentType = WindowsRuntime] `
            | Out-Null
        [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime] `
            | Out-Null
        [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] `
            | Out-Null

        $path = '{image_path}'
        $file = [System.IO.File]::OpenRead($path)
        $stream = $file.AsRandomAccessStream()
        $decOp = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
        $decoder = $decOp.GetAwaiter().GetResult()
        $bitmap = $decoder.GetSoftwareBitmapAsync().GetAwaiter().GetResult()
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
        if (-not $engine) {{
            $lang = [Windows.Globalization.Language]::new('en-US')
            $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
        }}
        $result = $engine.RecognizeAsync($bitmap).GetAwaiter().GetResult()

        $items = @()
        $lineNum = 1
        foreach ($line in $result.Lines) {{
            foreach ($word in $line.Words) {{
                $rect = $word.BoundingRect
                $items += @{{
                    text = $word.Text
                    x = [int]$rect.X
                    y = [int]$rect.Y
                    width = [int]$rect.Width
                    height = [int]$rect.Height
                    line = $lineNum
                }}
            }}
            $lineNum++
        }}
        $stream.Dispose()
        $file.Dispose()
        $items | ConvertTo-Json -Compress
        """

        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            out = proc.stdout.strip()
            if out and out.startswith("[") or out.startswith("{"):
                data = json.loads(out)
                if isinstance(data, dict):
                    data = [data]
                blocks = []
                for item in data:
                    blocks.append(
                        TextBlock(
                            text=item.get("text", ""),
                            x=int(item.get("x", 0)),
                            y=int(item.get("y", 0)),
                            width=int(item.get("width", 0)),
                            height=int(item.get("height", 0)),
                            line_number=int(item.get("line", 1)),
                        )
                    )
                return blocks
        except Exception as e:
            log.debug("Windows.Media.Ocr PowerShell invocation failed: %s", e)

        return []

    def _ocr_via_uia_text(self) -> list[TextBlock]:
        """Extract native accessible text from foreground window using UI Automation."""
        if not self._is_windows:
            return []

        blocks: list[TextBlock] = []
        try:
            import importlib

            pywinauto: Any = importlib.import_module("pywinauto")

            app = pywinauto.Desktop(backend="uia")
            top_win = app.top_window()

            # Iterate visible controls and get texts
            elements = top_win.descendants()
            line_idx = 1
            for el in elements:
                try:
                    elem_text = el.window_text().strip()
                    if elem_text:
                        r = el.rectangle()
                        blocks.append(
                            TextBlock(
                                text=elem_text,
                                x=r.left,
                                y=r.top,
                                width=max(0, r.width()),
                                height=max(0, r.height()),
                                line_number=line_idx,
                            )
                        )
                        line_idx += 1
                except Exception:
                    continue
        except Exception as e:
            log.debug("UIA text extraction failed: %s", e)

        return blocks

    async def recognize(self, image_input: str | Path | Image.Image) -> OCRResult:
        """
        Perform OCR on a screenshot path or PIL image.
        """
        start_time = time.time()
        blocks: list[TextBlock] = []

        # Resolve file path
        if isinstance(image_input, (str, Path)):
            img_path = str(Path(image_input).resolve())
        else:
            # Save temporary image for OCR
            from nexus.core.config import get_settings

            temp_path = get_settings().resolved_data_dir / "cache" / "ocr_temp.png"
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            image_input.save(str(temp_path), "PNG")
            img_path = str(temp_path)

        # Tier 1: Windows Native Media OCR
        blocks = self._ocr_via_windows_media_ocr(img_path)

        # Tier 2: UIA Text fallback if Media OCR returned nothing
        if not blocks:
            blocks = self._ocr_via_uia_text()

        # Build full text
        full_text_lines: list[str] = []
        current_line = 1
        current_line_words: list[str] = []

        for b in blocks:
            if b.line_number != current_line:
                if current_line_words:
                    full_text_lines.append(" ".join(current_line_words))
                    current_line_words = []
                current_line = b.line_number
            current_line_words.append(b.text)

        if current_line_words:
            full_text_lines.append(" ".join(current_line_words))

        full_text = "\n".join(full_text_lines)
        duration_ms = (time.time() - start_time) * 1000

        return OCRResult(
            success=True,
            full_text=full_text,
            blocks=blocks,
            word_count=len(blocks),
            line_count=len(full_text_lines),
            duration_ms=duration_ms,
        )
