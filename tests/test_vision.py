"""
Comprehensive test suite for Phase 5 — NEXUS Vision & Screen Understanding Engine.

Tests:
1. ScreenPrivacyManager (permissions, sensitive window filter, audit logs)
2. ScreenCaptureController (screen grab, window crop, privacy blocking)
3. ScreenOCR (text recognition, text blocks, coordinates)
4. UIElementDetector (buttons, fields, menus, spatial positioning, fuzzy search)
5. ScreenAnalyzer (scene description, semantic reasoning, locate element)
6. Vision Tools (describe, locate, click, type, OCR, active window)
7. FastAPI Vision Routes (/describe, /locate, /click, /privacy, /logs)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from nexus.api.app import create_app
from nexus.tools.base import RiskLevel
from nexus.tools.vision.screen_tools import (
    ClickElementTool,
    DescribeScreenTool,
    GetActiveWindowTool,
    LocateElementTool,
    ReadScreenTextTool,
    TypeIntoElementTool,
    get_vision_tools,
)
from nexus.vision.analyzer import ScreenAnalysisReport, ScreenAnalyzer
from nexus.vision.capture import ScreenCaptureController, ScreenCaptureResult, WindowInfo
from nexus.vision.ocr import OCRResult, ScreenOCR, TextBlock
from nexus.vision.privacy import (
    ScreenAnalysisLog,
    ScreenPermissionMode,
    ScreenPrivacyManager,
)
from nexus.vision.ui_detector import UIElement, UIElementDetector, UIElementType

# ===========================================================================
# 1. SCREEN PRIVACY MANAGER TESTS
# ===========================================================================


class TestScreenPrivacyManager:
    """Tests for privacy permissions and sensitive window filtering."""

    def test_permission_modes(self):
        # 1. Allow always
        pm_allow = ScreenPrivacyManager(mode=ScreenPermissionMode.ALLOW_ALWAYS)
        allowed, reason = pm_allow.check_permission("VS Code")
        assert allowed is True

        # 2. Deny mode
        pm_deny = ScreenPrivacyManager(mode=ScreenPermissionMode.DENY)
        allowed, reason = pm_deny.check_permission("VS Code")
        assert allowed is False
        assert "disabled by user" in reason

    def test_sensitive_application_blocking(self):
        pm = ScreenPrivacyManager(mode=ScreenPermissionMode.ALLOW_ALWAYS)

        # Sensitive applications should be blocked
        sensitive_windows = [
            "1Password - Password Manager",
            "Bitwarden Vault - Chrome",
            "Google Chrome (Incognito)",
            "MyBank Login - Personal Banking - Edge",
            "KeePass 2 - Passwords",
        ]

        for win in sensitive_windows:
            assert pm.is_sensitive_window(win) is True
            allowed, reason = pm.check_permission(win)
            assert allowed is False
            assert "sensitive content" in reason

        # Normal applications should be permitted
        safe_windows = [
            "main.py - nexus - Visual Studio Code",
            "Command Prompt",
            "NEXUS Architecture - Google Docs - Chrome",
            "Spotify Free",
        ]
        for win in safe_windows:
            assert pm.is_sensitive_window(win) is False
            allowed, reason = pm.check_permission(win)
            assert allowed is True

    def test_audit_logging_and_patterns(self):
        pm = ScreenPrivacyManager()
        log_entry = pm.log_capture(
            request_source="test",
            window_title="Visual Studio Code",
            allowed=True,
            reason="Success",
            image_bytes=b"dummy_png_bytes",
            elements_count=15,
            duration_ms=42.5,
        )
        assert isinstance(log_entry, ScreenAnalysisLog)
        assert log_entry.window_title == "Visual Studio Code"
        assert log_entry.elements_detected == 15
        assert log_entry.image_hash is not None

        logs = pm.get_audit_logs(limit=10)
        assert len(logs) == 1
        assert logs[0].log_id == log_entry.log_id

        # Pattern management
        pm.add_sensitive_pattern("confidential_financial_report")
        assert pm.is_sensitive_window("Q4 confidential_financial_report.xlsx") is True
        assert pm.remove_sensitive_pattern("confidential_financial_report") is True


# ===========================================================================
# 2. SCREEN CAPTURE CONTROLLER TESTS
# ===========================================================================


class TestScreenCaptureController:
    """Tests for on-demand screen capture controller."""

    @pytest.mark.asyncio
    async def test_capture_success(self, tmp_path: Path):
        pm = ScreenPrivacyManager(mode=ScreenPermissionMode.ALLOW_ALWAYS)
        ctrl = ScreenCaptureController(privacy_manager=pm)

        target_file = tmp_path / "test_cap.png"
        res = await ctrl.capture(save_path=str(target_file))

        assert res.success is True
        assert res.image is not None
        assert res.width > 0
        assert res.height > 0
        assert target_file.exists()

    @pytest.mark.asyncio
    async def test_capture_blocked_by_privacy(self):
        pm = ScreenPrivacyManager(mode=ScreenPermissionMode.DENY)
        ctrl = ScreenCaptureController(privacy_manager=pm)

        res = await ctrl.capture()
        assert res.success is False
        assert res.image is None
        assert "disabled by user" in (res.error or "")

    def test_active_window_info(self):
        ctrl = ScreenCaptureController()
        win = ctrl.get_active_window_info()
        if win is not None:
            assert isinstance(win, WindowInfo)
            assert win.width >= 0
            assert win.height >= 0


# ===========================================================================
# 3. SCREEN OCR TESTS
# ===========================================================================


class TestScreenOCR:
    """Tests for text detection and coordinate extraction."""

    @pytest.mark.asyncio
    async def test_ocr_text_blocks_and_full_text(self):
        ocr = ScreenOCR()

        # Mock Media OCR output
        mock_blocks = [
            TextBlock(text="File", x=10, y=10, width=30, height=20, line_number=1),
            TextBlock(text="Edit", x=50, y=10, width=30, height=20, line_number=1),
            TextBlock(text="Compilation", x=100, y=80, width=80, height=20, line_number=2),
            TextBlock(text="Error", x=190, y=80, width=40, height=20, line_number=2),
        ]

        with patch.object(ocr, "_ocr_via_windows_media_ocr", return_value=mock_blocks):
            dummy_img = Image.new("RGB", (800, 600), color=(30, 30, 30))
            res = await ocr.recognize(dummy_img)

            assert res.success is True
            assert res.word_count == 4
            assert res.line_count == 2
            assert "File Edit" in res.full_text
            assert "Compilation Error" in res.full_text

            # Check bounding box and center calculations
            b1 = res.blocks[0]
            assert b1.center == (25, 20)
            assert b1.bounds == (10, 10, 30, 20)


# ===========================================================================
# 4. UI ELEMENT DETECTOR TESTS
# ===========================================================================


class TestUIElementDetector:
    """Tests for button, input field, and menu element detection."""

    def test_detect_elements_and_spatial_location(self):
        detector = UIElementDetector()
        elements = detector.detect_elements()
        assert len(elements) > 0

        btn_run = UIElement(
            element_id="btn-run",
            element_type=UIElementType.BUTTON,
            name="Run",
            x=1600,
            y=80,
            width=80,
            height=32,
        )
        assert btn_run.relative_position == "top-right"
        assert btn_run.center == (1640, 96)

        search_input = UIElement(
            element_id="inp-search",
            element_type=UIElementType.INPUT_FIELD,
            name="Search Files",
            x=800,
            y=500,
            width=300,
            height=30,
        )
        assert search_input.relative_position == "center of the screen"

    def test_fuzzy_find_element(self):
        detector = UIElementDetector()
        mock_elements = [
            UIElement("btn-1", UIElementType.BUTTON, "Run Code", 1600, 80, 80, 32),
            UIElement("btn-2", UIElementType.BUTTON, "Debug Java", 1700, 80, 80, 32),
            UIElement("inp-1", UIElementType.INPUT_FIELD, "Search", 800, 50, 300, 30),
            UIElement("menu-1", UIElementType.MENU_ITEM, "File", 20, 10, 40, 20),
        ]

        # Exact match
        found = detector.find_element("File", elements=mock_elements)
        assert found is not None
        assert found.element_id == "menu-1"

        # Substring / partial match
        found_btn = detector.find_element("Run", element_type="button", elements=mock_elements)
        assert found_btn is not None
        assert found_btn.name == "Run Code"

        # Fuzzy match
        found_dbg = detector.find_element("debug", elements=mock_elements)
        assert found_dbg is not None
        assert found_dbg.name == "Debug Java"

        # Non-existent
        not_found = detector.find_element("NonExistentButtonXYZ", elements=mock_elements)
        assert not_found is None


# ===========================================================================
# 5. SCREEN ANALYZER TESTS
# ===========================================================================


class TestScreenAnalyzer:
    """Tests for high-level screen scene understanding."""

    @pytest.mark.asyncio
    async def test_screen_analyzer_full_report(self):
        pm = ScreenPrivacyManager(mode=ScreenPermissionMode.ALLOW_ALWAYS)
        analyzer = ScreenAnalyzer(privacy_manager=pm)

        mock_win = WindowInfo(
            hwnd=1234,
            title="App.java - my-project - Visual Studio Code",
            process_name="code.exe",
            pid=5555,
            x=0,
            y=0,
            width=1920,
            height=1080,
        )

        mock_cap_res = ScreenCaptureResult(
            success=True,
            image=Image.new("RGB", (1920, 1080), color=(20, 20, 20)),
            image_path=None,
            width=1920,
            height=1080,
            active_window=mock_win,
            timestamp="2026-08-19T12:00:00Z",
        )

        mock_ocr_res = OCRResult(
            success=True,
            full_text=(
                "public class App { System.out.println('Hello'); Compilation Error: ';' expected }"
            ),
            word_count=10,
            line_count=2,
        )

        mock_elements = [
            UIElement("btn-1", UIElementType.BUTTON, "Run", 1600, 80, 80, 32),
            UIElement("btn-2", UIElementType.BUTTON, "Debug", 1700, 80, 80, 32),
            UIElement("inp-1", UIElementType.INPUT_FIELD, "Search", 800, 50, 300, 30),
        ]

        with (
            patch.object(analyzer.capture_ctrl, "capture", return_value=mock_cap_res),
            patch.object(analyzer.ocr, "recognize", return_value=mock_ocr_res),
            patch.object(analyzer.detector, "detect_elements", return_value=mock_elements),
        ):
            report = await analyzer.analyze_screen()

            assert isinstance(report, ScreenAnalysisReport)
            assert "VS Code" in report.description
            assert "error" in report.description.lower()
            assert "Run" in report.buttons
            assert "Debug" in report.buttons
            assert "Search" in report.input_fields

    def test_locate_element_query_explanation(self):
        analyzer = ScreenAnalyzer()
        mock_elements = [
            UIElement("btn-1", UIElementType.BUTTON, "Run", 1600, 80, 80, 32),
        ]

        with patch.object(analyzer.detector, "detect_elements", return_value=mock_elements):
            el, explanation = analyzer.locate_element("Run")
            assert el is not None
            assert "Run" in explanation
            assert "top-right" in explanation
            assert "1640" in explanation  # Center X


# ===========================================================================
# 6. VISION TOOLS SUITE TESTS
# ===========================================================================


class TestVisionToolsSuite:
    """Tests for all LLM vision tools."""

    @pytest.mark.asyncio
    async def test_describe_screen_tool(self):
        tool = DescribeScreenTool()
        assert tool.name == "describe_screen"
        assert tool.category == "vision"
        assert tool.risk_level == RiskLevel.LOW

        res = await tool.execute()
        assert res.success is True
        assert len(res.output) > 0

    @pytest.mark.asyncio
    async def test_locate_element_tool(self):
        tool = LocateElementTool()
        assert tool.name == "locate_ui_element"

        # Mock locator
        mock_el = UIElement("btn-run", UIElementType.BUTTON, "Run", 1600, 80, 80, 32)
        with patch.object(
            tool._analyzer,
            "locate_element",
            return_value=(mock_el, "The Run button is at top-right"),
        ):
            res = await tool.execute(element_name="Run")
            assert res.success is True
            assert "Run button is at top-right" in res.output
            assert res.data["cx"] == 1640

    @pytest.mark.asyncio
    async def test_click_element_tool(self):
        tool = ClickElementTool()
        assert tool.name == "click_ui_element"
        assert tool.risk_level == RiskLevel.MEDIUM

        # Click by direct coordinates
        with (
            patch("ctypes.windll.user32.SetCursorPos"),
            patch("ctypes.windll.user32.mouse_event"),
        ):
            res = await tool.execute(x=100, y=200)
            assert res.success is True
            assert "(x=100, y=200)" in res.output

    @pytest.mark.asyncio
    async def test_type_into_element_tool(self):
        tool = TypeIntoElementTool()
        assert tool.name == "type_into_element"

        with patch("pyautogui.write"):
            sample_text = "print('Hello NEXUS')"
            res = await tool.execute(text=sample_text)
            assert res.success is True
            assert f"{len(sample_text)} characters" in res.output

    @pytest.mark.asyncio
    async def test_read_screen_text_tool(self):
        tool = ReadScreenTextTool()
        assert tool.name == "read_screen_text"

        mock_ocr = OCRResult(
            success=True,
            full_text="Line 1\nLine 2\nLine 3",
            word_count=6,
            line_count=3,
        )
        with patch.object(tool._ocr, "recognize", return_value=mock_ocr):
            res = await tool.execute()
            assert res.success is True
            assert "Line 1" in res.output

    @pytest.mark.asyncio
    async def test_get_active_window_tool(self):
        tool = GetActiveWindowTool()
        assert tool.name == "get_active_window"

        res = await tool.execute()
        assert res.success is True

    def test_get_vision_tools_factory(self):
        tools = get_vision_tools()
        assert len(tools) == 6
        names = {t.name for t in tools}
        assert names == {
            "describe_screen",
            "locate_ui_element",
            "click_ui_element",
            "type_into_element",
            "read_screen_text",
            "get_active_window",
        }


# ===========================================================================
# 7. FASTAPI VISION ROUTES TESTS
# ===========================================================================


class TestFastAPIVisionRoutes:
    """Tests for REST endpoints on /api/vision/."""

    @pytest.mark.asyncio
    async def test_vision_describe_and_locate_endpoints(self):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Describe
            res_desc = await ac.get("/api/vision/screen/describe")
            assert res_desc.status_code == 200
            data_desc = res_desc.json()
            assert "description" in data_desc
            assert "app_name" in data_desc
            assert "buttons" in data_desc

            # 2. Locate (Mocked find)
            with patch("nexus.api.routes.vision._analyzer.locate_element") as mock_loc:
                mock_el = UIElement("btn-1", UIElementType.BUTTON, "Run", 1600, 80, 80, 32)
                mock_loc.return_value = (mock_el, "The Run button is at top-right")
                res_loc = await ac.post("/api/vision/screen/locate", json={"element_name": "Run"})
                assert res_loc.status_code == 200
                data_loc = res_loc.json()
                assert data_loc["found"] is True
                assert data_loc["name"] == "Run"
                assert data_loc["cx"] == 1640

    @pytest.mark.asyncio
    async def test_vision_privacy_and_logs_endpoints(self):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Get privacy
            res_priv = await ac.get("/api/vision/screen/privacy")
            assert res_priv.status_code == 200
            data_priv = res_priv.json()
            assert "mode" in data_priv
            assert "sensitive_patterns" in data_priv

            # 2. Update privacy
            res_update = await ac.post(
                "/api/vision/screen/privacy",
                json={"add_sensitive_pattern": "custom_secret_app"},
            )
            assert res_update.status_code == 200
            assert "custom_secret_app" in res_update.json()["sensitive_patterns"]

            # 3. Get audit logs
            res_logs = await ac.get("/api/vision/screen/logs")
            assert res_logs.status_code == 200
            assert isinstance(res_logs.json(), list)
