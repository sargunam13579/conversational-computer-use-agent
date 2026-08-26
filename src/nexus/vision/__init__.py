"""
NEXUS Vision & Screen Understanding Engine.

Provides screen capture, OCR, UI element detection, spatial localization,
and privacy-controlled scene analysis.
"""

from nexus.vision.analyzer import ScreenAnalysisReport, ScreenAnalyzer
from nexus.vision.capture import ScreenCaptureController, ScreenCaptureResult, WindowInfo
from nexus.vision.ocr import OCRResult, ScreenOCR, TextBlock
from nexus.vision.privacy import (
    ScreenAnalysisLog,
    ScreenPermissionMode,
    ScreenPrivacyManager,
)
from nexus.vision.ui_detector import UIElement, UIElementDetector, UIElementType

__all__ = [
    "ScreenPrivacyManager",
    "ScreenPermissionMode",
    "ScreenAnalysisLog",
    "ScreenCaptureController",
    "ScreenCaptureResult",
    "WindowInfo",
    "ScreenOCR",
    "OCRResult",
    "TextBlock",
    "UIElementDetector",
    "UIElement",
    "UIElementType",
    "ScreenAnalyzer",
    "ScreenAnalysisReport",
]
