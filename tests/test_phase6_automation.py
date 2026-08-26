"""
Comprehensive Test Suite for Phase 6 — NEXUS Browser & Desktop Application Automation.

Tests:
1. BrowserController & Tab Management
2. BrowserNavigator (URL formatting, search engines, navigation)
3. BrowserInteraction (click, type, scroll, form fill)
4. BrowserDownloader (downloads, hashing, folder placement)
5. PageReader (structured text, headings, links)
6. DesktopAppController & DesktopUIInteraction
7. ErrorRecoveryManager (retry, exponential backoff)
8. MultiStepWorkflowEngine (search+read, search+download+file)
9. Browser & Desktop LLM Tools Suite
10. FastAPI Browser & Automation Endpoints
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from nexus.api.app import create_app
from nexus.automation.app_controller import ActiveAppInfo, DesktopAppController
from nexus.automation.error_recovery import with_retry
from nexus.automation.ui_interaction import DesktopUIInteraction
from nexus.automation.workflow import MultiStepWorkflowEngine, WorkflowResult
from nexus.browser.controller import BrowserController, TabInfo
from nexus.browser.downloader import BrowserDownloader, DownloadResult
from nexus.browser.interaction import BrowserInteraction
from nexus.browser.navigator import BrowserNavigator
from nexus.browser.page_reader import PageContent, PageLink, PageReader
from nexus.tools.browser.web_tools import (
    ClickWebElementTool,
    DownloadWebFileTool,
    ManageWebTabsTool,
    NavigateWebTool,
    OpenBrowserTool,
    ScrollWebTool,
    WebSearchBrowserTool,
    get_browser_tools,
)
from nexus.tools.desktop.app_tools import (
    InteractAppTool,
    MultiStepTaskTool,
    ScrollAppTool,
    get_desktop_automation_tools,
)

# ===========================================================================
# 1. BROWSER CONTROLLER & TAB MANAGEMENT TESTS
# ===========================================================================


class TestBrowserController:
    """Tests for Playwright browser lifecycle and tab management."""

    @pytest.mark.asyncio
    async def test_tab_lifecycle_and_switching(self):
        ctrl = BrowserController()

        mock_page_1 = AsyncMock()
        mock_page_1.title = AsyncMock(return_value="Page 1")
        mock_page_1.url = "https://example.com/1"
        mock_page_1.is_closed = MagicMock(return_value=False)
        mock_page_1.close = AsyncMock()

        mock_page_2 = AsyncMock()
        mock_page_2.title = AsyncMock(return_value="Page 2")
        mock_page_2.url = "https://example.com/2"
        mock_page_2.is_closed = MagicMock(return_value=False)
        mock_page_2.close = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(side_effect=[mock_page_1, mock_page_2])
        mock_context.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.is_connected = MagicMock(return_value=True)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_chromium = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)

        mock_playwright = AsyncMock()
        mock_playwright.chromium = mock_chromium
        mock_playwright.stop = AsyncMock()

        mock_pw_cm = AsyncMock()
        mock_pw_cm.start = AsyncMock(return_value=mock_playwright)

        with patch("playwright.async_api.async_playwright", return_value=mock_pw_cm):
            # 1. Start controller
            await ctrl.start()
            assert ctrl.is_running is True

            # 2. Get active page
            page = await ctrl.get_active_page()
            assert page == mock_page_1

            # 3. Open new tab
            tab2 = await ctrl.new_tab(url="https://example.com/2")
            assert tab2.index == 1
            assert tab2.title == "Page 2"

            # 4. List tabs
            tabs = await ctrl.list_tabs()
            assert len(tabs) == 2
            assert tabs[1].is_active is True

            # 5. Switch tab
            switched = await ctrl.switch_tab(0)
            assert switched.index == 0

            # 6. Close tab
            closed = await ctrl.close_tab(1)
            assert closed is True

            # 7. Teardown
            await ctrl.stop()
            assert ctrl.is_running is False


# ===========================================================================
# 2. BROWSER NAVIGATOR TESTS
# ===========================================================================


class TestBrowserNavigator:
    """Tests for URL formatting and search querying."""

    def test_url_formatting(self):
        nav = BrowserNavigator(controller=BrowserController())

        assert nav._format_url("https://github.com") == "https://github.com"
        assert nav._format_url("google.com") == "https://google.com"
        assert "duckduckgo.com/?q=python+interview" in nav._format_url("python interview")

    @pytest.mark.asyncio
    async def test_navigate_and_search(self):
        ctrl = BrowserController()
        mock_page = AsyncMock()
        mock_page.title.return_value = "Python Search"
        mock_page.url = "https://duckduckgo.com/?q=python"
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_page.goto.return_value = mock_resp

        with patch.object(ctrl, "get_active_page", return_value=mock_page):
            nav = BrowserNavigator(controller=ctrl)

            # Navigate
            res_nav = await nav.navigate("https://python.org")
            assert res_nav["status_code"] == 200

            # Search
            res_search = await nav.search("python", engine="duckduckgo")
            assert "python" in res_search["url"]
            assert res_search["status_code"] == 200


# ===========================================================================
# 3. BROWSER INTERACTION TESTS
# ===========================================================================


class TestBrowserInteraction:
    """Tests for DOM clicking, typing, scrolling, and form filling."""

    @pytest.mark.asyncio
    async def test_click_and_type(self):
        ctrl = BrowserController()
        mock_page = AsyncMock()
        mock_locator = AsyncMock()
        mock_locator.is_visible.return_value = True
        mock_page.locator.return_value.first = mock_locator
        mock_page.get_by_text.return_value.first = mock_locator

        with patch.object(ctrl, "get_active_page", return_value=mock_page):
            interaction = BrowserInteraction(controller=ctrl)

            # Click
            clicked = await interaction.click("Submit Button")
            assert clicked is True

            # Type
            typed = await interaction.type_text(
                target="#username", text="nexus_user", press_enter=True
            )
            assert typed is True

            # Scroll
            scrolled = await interaction.scroll(direction="down", amount=300)
            assert scrolled is True

            # Fill Form
            filled = await interaction.fill_form({"#user": "admin", "#pass": "secret"})
            assert len(filled) == 2
            assert filled["#user"] is True


# ===========================================================================
# 4. BROWSER DOWNLOADER TESTS
# ===========================================================================


class TestBrowserDownloader:
    """Tests for downloading files, hashing, and moving to folders."""

    @pytest.mark.asyncio
    async def test_direct_url_download(self, tmp_path: Path):
        ctrl = BrowserController()
        downloader = BrowserDownloader(controller=ctrl)

        sample_content = b"%PDF-1.4 Mock Java Interview Questions Document"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = sample_content
        mock_resp.headers = {"content-disposition": "attachment; filename=java_interview.pdf"}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            res = await downloader.download(
                url_or_click_target="https://example.com/java_interview.pdf",
                destination_folder=str(tmp_path),
            )

            assert res.success is True
            assert res.filename == "java_interview.pdf"
            assert res.file_size_bytes == len(sample_content)
            assert res.sha256_hash is not None
            assert res.file_path is not None
            assert Path(res.file_path).exists()


# ===========================================================================
# 5. PAGE READER TESTS
# ===========================================================================


class TestPageReader:
    """Tests for structured text extraction and link discovery."""

    @pytest.mark.asyncio
    async def test_page_reading_and_link_extraction(self):
        ctrl = BrowserController()
        mock_page = AsyncMock()
        mock_page.title.return_value = "Java Tutorial & PDF Guide"
        mock_page.url = "https://learnjava.com"

        mock_dom_data = {
            "bodyText": (
                "Java is a popular class-based programming language. "
                "Learn OOP, JVM, and concurrency."
            ),
            "headings": ["Introduction to Java", "Core Features"],
            "links": [
                {
                    "text": "Download Java Cheatsheet PDF",
                    "url": "https://learnjava.com/cheatsheet.pdf",
                    "is_download": True,
                },
                {
                    "text": "Community Forum",
                    "url": "https://learnjava.com/forum",
                    "is_download": False,
                },
            ],
        }
        mock_page.evaluate.return_value = mock_dom_data

        with patch.object(ctrl, "get_active_page", return_value=mock_page):
            reader = PageReader(controller=ctrl)

            content = await reader.read()
            assert isinstance(content, PageContent)
            assert "Java" in content.title
            assert len(content.headings) == 2
            assert len(content.links) == 2
            assert content.total_words > 5

            pdf_links = await reader.find_download_links(extension="pdf")
            assert len(pdf_links) == 1
            assert pdf_links[0].url.endswith(".pdf")


# ===========================================================================
# 6. DESKTOP APP CONTROLLER & INTERACTION TESTS
# ===========================================================================


class TestDesktopAppControllerAndInteraction:
    """Tests for desktop window tracking and control interaction."""

    def test_active_app_and_interaction(self):
        app_ctrl = DesktopAppController()
        active = app_ctrl.get_active_app()
        if active is not None:
            assert isinstance(active, ActiveAppInfo)
            assert active.width >= 0

        interact = DesktopUIInteraction(app_controller=app_ctrl)

        # Direct coordinate clicking
        with (
            patch("ctypes.windll.user32.SetCursorPos"),
            patch("ctypes.windll.user32.mouse_event"),
        ):
            clicked = interact.click_at(100, 200)
            assert clicked is True

            scrolled = interact.scroll(direction="down", clicks=3)
            assert scrolled is True


# ===========================================================================
# 7. ERROR RECOVERY MANAGER TESTS
# ===========================================================================


class TestErrorRecoveryManager:
    """Tests for retry with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_success_after_failure(self):
        call_count = 0

        @with_retry(max_attempts=3, base_delay_seconds=0.01)
        async def flaky_action() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionResetError("Flaky network connection")
            return "success"

        result = await flaky_action()
        assert result == "success"
        assert call_count == 2


# ===========================================================================
# 8. MULTI-STEP WORKFLOW ENGINE TESTS
# ===========================================================================


class TestMultiStepWorkflowEngine:
    """Tests for chained workflow tasks (Search + Read, Search + Download)."""

    @pytest.mark.asyncio
    async def test_search_and_read_workflow(self):
        engine = MultiStepWorkflowEngine()

        mock_content = PageContent(
            title="Java Interview Questions 2026",
            url="https://javatutorial.org/interview",
            text_content="Q1: What is JVM? Java Virtual Machine executes bytecode.",
            headings=["Top Questions", "Java Basics"],
            links=[],
            total_words=10,
        )

        with (
            patch.object(
                engine._navigator,
                "search",
                return_value={"title": "Search", "url": "https://ddg.com"},
            ),
            patch.object(engine._page_reader, "read", return_value=mock_content),
        ):
            res = await engine.execute_web_search_and_read(query="Java interview questions")

            assert isinstance(res, WorkflowResult)
            assert res.success is True
            assert len(res.steps) == 3
            assert "Java Interview Questions" in res.summary

    @pytest.mark.asyncio
    async def test_search_download_and_file_workflow(self, tmp_path: Path):
        engine = MultiStepWorkflowEngine()

        mock_links = [
            PageLink("Java Cheat Sheet PDF", "https://example.com/java.pdf", is_download=True)
        ]
        mock_dl_result = DownloadResult(
            success=True,
            file_path=str(tmp_path / "java.pdf"),
            filename="java.pdf",
            file_size_bytes=1024,
            sha256_hash="abcdef1234567890",
            destination_folder=str(tmp_path),
        )

        with (
            patch.object(
                engine._navigator,
                "search",
                return_value={"title": "Search", "url": "https://ddg.com"},
            ),
            patch.object(engine._page_reader, "find_download_links", return_value=mock_links),
            patch.object(engine._downloader, "download", return_value=mock_dl_result),
        ):
            res = await engine.execute_search_download_and_file(
                search_query="Java PDF cheat sheet",
                file_extension="pdf",
                destination_folder=str(tmp_path),
            )

            assert res.success is True
            assert len(res.steps) == 5
            assert "java.pdf" in res.summary


# ===========================================================================
# 9. BROWSER & DESKTOP TOOLS SUITE TESTS
# ===========================================================================


class TestBrowserAndDesktopToolsSuite:
    """Tests for all browser and desktop automation LLM tools."""

    @pytest.mark.asyncio
    async def test_open_browser_and_navigate_tools(self):
        open_tool = OpenBrowserTool()
        assert open_tool.name == "open_browser"
        assert open_tool.category == "browser"

        with (
            patch.object(open_tool._controller, "start"),
            patch.object(open_tool._controller, "get_active_page") as mock_gap,
        ):
            mock_p = AsyncMock()
            mock_p.title.return_value = "Home"
            mock_p.url = "https://google.com"
            mock_gap.return_value = mock_p

            res = await open_tool.execute()
            assert res.success is True

        nav_tool = NavigateWebTool()
        with patch.object(
            nav_tool._navigator,
            "navigate",
            return_value={"title": "GitHub", "url": "https://github.com", "status_code": 200},
        ):
            res_nav = await nav_tool.execute(url="https://github.com")
            assert res_nav.success is True
            assert "GitHub" in res_nav.output

    @pytest.mark.asyncio
    async def test_search_and_click_and_scroll_tools(self):
        search_tool = WebSearchBrowserTool()
        with patch.object(
            search_tool._navigator,
            "search",
            return_value={"title": "Results", "url": "https://ddg.com"},
        ):
            res_search = await search_tool.execute(query="Python asyncio")
            assert res_search.success is True

        click_tool = ClickWebElementTool()
        with patch.object(click_tool._interaction, "click", return_value=True):
            res_click = await click_tool.execute(target="Submit")
            assert res_click.success is True

        scroll_tool = ScrollWebTool()
        with patch.object(scroll_tool._interaction, "scroll", return_value=True):
            res_scroll = await scroll_tool.execute(direction="down", amount=400)
            assert res_scroll.success is True

    @pytest.mark.asyncio
    async def test_tabs_and_download_tools(self, tmp_path: Path):
        tab_tool = ManageWebTabsTool()
        with patch.object(
            tab_tool._controller,
            "list_tabs",
            return_value=[TabInfo(0, "Tab 1", "https://t1.com", True)],
        ):
            res_tabs = await tab_tool.execute(action="list")
            assert res_tabs.success is True
            assert "Tab 1" in res_tabs.output

        dl_tool = DownloadWebFileTool()
        mock_res = DownloadResult(
            success=True,
            file_path=str(tmp_path / "test.pdf"),
            filename="test.pdf",
            file_size_bytes=500,
            sha256_hash="hash123",
        )
        with patch.object(dl_tool._downloader, "download", return_value=mock_res):
            res_dl = await dl_tool.execute(target="https://example.com/test.pdf")
            assert res_dl.success is True
            assert "test.pdf" in res_dl.output

    @pytest.mark.asyncio
    async def test_desktop_automation_tools(self):
        interact_tool = InteractAppTool()
        assert interact_tool.name == "interact_desktop_app"

        with patch.object(interact_tool._ui_interact, "click_element", return_value=True):
            res_click = await interact_tool.execute(element_name="Save")
            assert res_click.success is True

        scroll_tool = ScrollAppTool()
        with patch.object(scroll_tool._ui_interact, "scroll", return_value=True):
            res_scroll = await scroll_tool.execute(direction="down", clicks=3)
            assert res_scroll.success is True

        multistep_tool = MultiStepTaskTool()
        mock_wf_res = WorkflowResult(success=True, summary="Workflow finished", steps=[])
        with patch.object(
            multistep_tool._engine, "execute_web_search_and_read", return_value=mock_wf_res
        ):
            res_multi = await multistep_tool.execute(task_type="search_and_read", query="AI trends")
            assert res_multi.success is True

    def test_tool_factories(self):
        browser_tools = get_browser_tools()
        assert len(browser_tools) == 10

        desktop_tools = get_desktop_automation_tools()
        assert len(desktop_tools) == 4


# ===========================================================================
# 10. FASTAPI BROWSER & AUTOMATION ENDPOINTS TESTS
# ===========================================================================


class TestFastAPIBrowserAndAutomationRoutes:
    """Tests for REST API routes on /api/browser/ and /api/automation/."""

    @pytest.mark.asyncio
    async def test_browser_routes(self):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Navigate
            with patch(
                "nexus.api.routes.browser._navigator.navigate",
                return_value={"title": "Test", "url": "https://test.com", "status_code": 200},
            ):
                res = await ac.post("/api/browser/navigate", json={"url": "https://test.com"})
                assert res.status_code == 200
                assert res.json()["title"] == "Test"

            # 2. Search
            with patch(
                "nexus.api.routes.browser._navigator.search",
                return_value={"title": "Search", "url": "https://ddg.com", "status_code": 200},
            ):
                res_search = await ac.post("/api/browser/search", json={"query": "python"})
                assert res_search.status_code == 200

            # 3. Content
            mock_content = PageContent("Test Page", "https://t.com", "Some text", ["H1"], [], 2)
            with patch("nexus.api.routes.browser._reader.read", return_value=mock_content):
                res_content = await ac.get("/api/browser/content")
                assert res_content.status_code == 200
                assert res_content.json()["title"] == "Test Page"

            # 4. Tabs
            with patch(
                "nexus.api.routes.browser._browser_ctrl.list_tabs",
                return_value=[TabInfo(0, "T1", "https://t1.com", True)],
            ):
                res_tabs = await ac.post("/api/browser/tabs", json={"action": "list"})
                assert res_tabs.status_code == 200
                assert len(res_tabs.json()["tabs"]) == 1

    @pytest.mark.asyncio
    async def test_automation_routes(self):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Active App
            mock_app = ActiveAppInfo("code.exe", "VS Code", 1234, 5678, 0, 0, 1920, 1080)
            with patch(
                "nexus.api.routes.automation._app_ctrl.get_active_app", return_value=mock_app
            ):
                res_app = await ac.get("/api/automation/app/active")
                assert res_app.status_code == 200
                assert res_app.json()["name"] == "code.exe"

            # 2. Workflow Execute
            mock_wf = WorkflowResult(True, "Workflow completed successfully", [])
            with patch(
                "nexus.api.routes.automation._workflow_engine.execute_web_search_and_read",
                return_value=mock_wf,
            ):
                res_wf = await ac.post(
                    "/api/automation/workflow/execute",
                    json={"task_type": "search_and_read", "query": "Python tips"},
                )
                assert res_wf.status_code == 200
                assert res_wf.json()["success"] is True
