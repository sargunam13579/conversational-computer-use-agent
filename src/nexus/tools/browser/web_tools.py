"""
NEXUS Browser Tools for LLM & Agents.

Exposes web browsing, search, navigation, tab management, DOM clicks/typing,
form filling, downloads, and page reading to the NEXUS Brain and Laptop Agent.
"""

from __future__ import annotations

from typing import Any

from nexus.browser.controller import BrowserController
from nexus.browser.downloader import BrowserDownloader
from nexus.browser.interaction import BrowserInteraction
from nexus.browser.navigator import BrowserNavigator
from nexus.browser.page_reader import PageReader
from nexus.tools.base import BaseTool, RiskLevel, TargetDevice, ToolResult
from nexus.utils.logging import get_logger

log = get_logger("tools.browser.web")

# Shared default controller instance
_default_browser_ctrl = BrowserController()


# ---------------------------------------------------------------------------
# Open Browser
# ---------------------------------------------------------------------------


class OpenBrowserTool(BaseTool):
    """Open or start the web browser and optionally navigate to a URL."""

    def __init__(self, controller: BrowserController | None = None) -> None:
        self._controller = controller or _default_browser_ctrl

    @property
    def name(self) -> str:
        return "open_browser"

    @property
    def description(self) -> str:
        return "Open the web browser and optionally navigate to a specific URL."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Optional initial URL to navigate to (e.g. 'https://google.com').",
                },
            },
            "required": [],
        }

    @property
    def category(self) -> str:
        return "browser"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(self, url: str | None = None, **kwargs: Any) -> ToolResult:
        try:
            if not self._controller.is_running:
                await self._controller.start()

            page = await self._controller.get_active_page()
            if url:
                navigator = BrowserNavigator(controller=self._controller)
                nav_res = await navigator.navigate(url)
                msg = (
                    f"Browser opened and navigated to '{nav_res['url']}' "
                    f"(Title: '{nav_res['title']}')."
                )
                return ToolResult.ok(
                    msg,
                    title=nav_res["title"],
                    url=nav_res["url"],
                )

            title = await page.title() or "New Tab"
            return ToolResult.ok("Browser opened successfully.", title=title, url=page.url)
        except Exception as e:
            return ToolResult.fail(f"Failed to open browser: {e}")


# ---------------------------------------------------------------------------
# Navigate Web
# ---------------------------------------------------------------------------


class NavigateWebTool(BaseTool):
    """Navigate the active browser tab to a URL."""

    def __init__(self, controller: BrowserController | None = None) -> None:
        self._controller = controller or _default_browser_ctrl
        self._navigator = BrowserNavigator(controller=self._controller)

    @property
    def name(self) -> str:
        return "navigate_web"

    @property
    def description(self) -> str:
        return "Navigate active browser page to a specific URL or web address."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Target URL to navigate to (e.g. 'https://github.com').",
                },
            },
            "required": ["url"],
        }

    @property
    def category(self) -> str:
        return "browser"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(self, url: str = "", **kwargs: Any) -> ToolResult:
        if not url:
            return ToolResult.fail("Parameter 'url' is required.")

        try:
            res = await self._navigator.navigate(url)
            msg = (
                f"Navigated to '{res['url']}' "
                f"(Title: '{res['title']}', Status: {res['status_code']})."
            )
            return ToolResult.ok(
                msg,
                title=res["title"],
                url=res["url"],
                status_code=res["status_code"],
            )
        except Exception as e:
            return ToolResult.fail(f"Navigation failed: {e}")


# ---------------------------------------------------------------------------
# Web Search Browser
# ---------------------------------------------------------------------------


class WebSearchBrowserTool(BaseTool):
    """Perform a search on DuckDuckGo, Google, or Bing in the browser."""

    def __init__(self, controller: BrowserController | None = None) -> None:
        self._controller = controller or _default_browser_ctrl
        self._navigator = BrowserNavigator(controller=self._controller)

    @property
    def name(self) -> str:
        return "web_search_browser"

    @property
    def description(self) -> str:
        return "Search the web using DuckDuckGo, Google, or Bing in the browser."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query keywords or question.",
                },
                "engine": {
                    "type": "string",
                    "enum": ["duckduckgo", "google", "bing"],
                    "description": "Search engine to use (default: duckduckgo).",
                },
            },
            "required": ["query"],
        }

    @property
    def category(self) -> str:
        return "browser"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self, query: str = "", engine: str = "duckduckgo", **kwargs: Any
    ) -> ToolResult:
        if not query:
            return ToolResult.fail("Parameter 'query' is required.")

        try:
            res = await self._navigator.search(query, engine=engine)
            msg = (
                f"Searched '{query}' on {engine.capitalize()}. "
                f"Current page: '{res['title']}' ({res['url']})."
            )
            return ToolResult.ok(
                msg,
                title=res["title"],
                url=res["url"],
            )
        except Exception as e:
            return ToolResult.fail(f"Search failed: {e}")


# ---------------------------------------------------------------------------
# Click Web Element
# ---------------------------------------------------------------------------


class ClickWebElementTool(BaseTool):
    """Click a button, link, or element on the current web page."""

    def __init__(self, controller: BrowserController | None = None) -> None:
        self._controller = controller or _default_browser_ctrl
        self._interaction = BrowserInteraction(controller=self._controller)

    @property
    def name(self) -> str:
        return "click_web_element"

    @property
    def description(self) -> str:
        return "Click a button, link, or element on the current web page by text or CSS selector."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": (
                        "Text, button label, link title, or CSS/XPath selector of element to click."
                    ),
                },
            },
            "required": ["target"],
        }

    @property
    def category(self) -> str:
        return "browser"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(self, target: str = "", **kwargs: Any) -> ToolResult:
        if not target:
            return ToolResult.fail("Parameter 'target' is required.")

        try:
            success = await self._interaction.click(target)
            if success:
                return ToolResult.ok(f"Successfully clicked web element '{target}'.")
            return ToolResult.fail(f"Could not click element matching '{target}'.")
        except Exception as e:
            return ToolResult.fail(f"Click failed: {e}")


# ---------------------------------------------------------------------------
# Type Web Element
# ---------------------------------------------------------------------------


class TypeWebElementTool(BaseTool):
    """Type text into an input field or textarea on the current web page."""

    def __init__(self, controller: BrowserController | None = None) -> None:
        self._controller = controller or _default_browser_ctrl
        self._interaction = BrowserInteraction(controller=self._controller)

    @property
    def name(self) -> str:
        return "type_web_element"

    @property
    def description(self) -> str:
        return "Type text into a web input field, search box, or form element."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to type.",
                },
                "target": {
                    "type": "string",
                    "description": (
                        "Optional placeholder, label, name, or selector of target input."
                    ),
                },
                "press_enter": {
                    "type": "boolean",
                    "description": "Whether to press Enter after typing (default: false).",
                },
            },
            "required": ["text"],
        }

    @property
    def category(self) -> str:
        return "browser"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self,
        text: str = "",
        target: str | None = None,
        press_enter: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        if not text:
            return ToolResult.fail("Parameter 'text' cannot be empty.")

        try:
            success = await self._interaction.type_text(
                target=target, text=text, press_enter=press_enter
            )
            if success:
                return ToolResult.ok(
                    f"Typed {len(text)} characters into '{target or 'active field'}'.",
                    text_length=len(text),
                )
            return ToolResult.fail(f"Could not type into element '{target}'.")
        except Exception as e:
            return ToolResult.fail(f"Typing failed: {e}")


# ---------------------------------------------------------------------------
# Scroll Web
# ---------------------------------------------------------------------------


class ScrollWebTool(BaseTool):
    """Scroll the current web page."""

    def __init__(self, controller: BrowserController | None = None) -> None:
        self._controller = controller or _default_browser_ctrl
        self._interaction = BrowserInteraction(controller=self._controller)

    @property
    def name(self) -> str:
        return "scroll_web"

    @property
    def description(self) -> str:
        return "Scroll the current webpage up, down, top, or bottom."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["down", "up", "top", "bottom"],
                    "description": "Scroll direction (default: down).",
                },
                "amount": {
                    "type": "integer",
                    "description": "Pixel amount to scroll (default: 500).",
                },
            },
            "required": [],
        }

    @property
    def category(self) -> str:
        return "browser"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self, direction: str = "down", amount: int = 500, **kwargs: Any
    ) -> ToolResult:
        try:
            success = await self._interaction.scroll(direction=direction, amount=amount)
            if success:
                return ToolResult.ok(f"Scrolled page {direction} by {amount}px.")
            return ToolResult.fail("Could not scroll page.")
        except Exception as e:
            return ToolResult.fail(f"Scroll failed: {e}")


# ---------------------------------------------------------------------------
# Read Web Page
# ---------------------------------------------------------------------------


class ReadWebPageTool(BaseTool):
    """Extract and read structured text content and links from the current web page."""

    def __init__(self, controller: BrowserController | None = None) -> None:
        self._controller = controller or _default_browser_ctrl
        self._reader = PageReader(controller=self._controller)

    @property
    def name(self) -> str:
        return "read_web_page"

    @property
    def description(self) -> str:
        return "Extract readable text content, headings, and links from the active web page."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "max_words": {
                    "type": "integer",
                    "description": "Max number of words to return (default: 600).",
                },
            },
            "required": [],
        }

    @property
    def category(self) -> str:
        return "browser"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(self, max_words: int = 600, **kwargs: Any) -> ToolResult:
        try:
            content = await self._reader.read(max_length=max_words * 6)
            summary = (
                f"Page Title: {content.title}\n"
                f"URL: {content.url}\n"
                f"Word Count: {content.total_words}\n\n"
                f"--- Content ---\n{content.text_content}"
            )
            return ToolResult.ok(
                summary,
                title=content.title,
                url=content.url,
                headings=content.headings,
                total_words=content.total_words,
            )
        except Exception as e:
            return ToolResult.fail(f"Reading page content failed: {e}")


# ---------------------------------------------------------------------------
# Manage Web Tabs
# ---------------------------------------------------------------------------


class ManageWebTabsTool(BaseTool):
    """Manage browser tabs: open new tab, close tab, switch tab, or list tabs."""

    def __init__(self, controller: BrowserController | None = None) -> None:
        self._controller = controller or _default_browser_ctrl

    @property
    def name(self) -> str:
        return "manage_web_tabs"

    @property
    def description(self) -> str:
        return "Manage browser tabs: 'list' tabs, 'new' tab, 'switch' tab, or 'close' tab."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "new", "switch", "close"],
                    "description": "Action to perform on tabs.",
                },
                "index": {
                    "type": "integer",
                    "description": "Tab index for 'switch' or 'close' actions.",
                },
                "url": {
                    "type": "string",
                    "description": "URL to open when creating a 'new' tab.",
                },
            },
            "required": ["action"],
        }

    @property
    def category(self) -> str:
        return "browser"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self,
        action: str = "list",
        index: int | None = None,
        url: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        act = action.lower().strip()
        try:
            if act == "list":
                tabs = await self._controller.list_tabs()
                if not tabs:
                    return ToolResult.ok("No browser tabs open.", tabs=[])
                lines = [
                    f"[{t.index}] {'* ' if t.is_active else '  '}{t.title} ({t.url})" for t in tabs
                ]
                return ToolResult.ok(
                    "Open Tabs:\n" + "\n".join(lines),
                    tabs=[
                        {"index": t.index, "title": t.title, "url": t.url, "active": t.is_active}
                        for t in tabs
                    ],
                )

            elif act == "new":
                tab_info = await self._controller.new_tab(url=url)
                return ToolResult.ok(
                    f"Opened new tab [{tab_info.index}]: '{tab_info.title}' ({tab_info.url}).",
                    index=tab_info.index,
                    title=tab_info.title,
                    url=tab_info.url,
                )

            elif act == "switch":
                if index is None:
                    return ToolResult.fail("Parameter 'index' is required for 'switch' action.")
                tab_info = await self._controller.switch_tab(index)
                return ToolResult.ok(
                    f"Switched to tab [{tab_info.index}]: '{tab_info.title}'.",
                    index=tab_info.index,
                    title=tab_info.title,
                    url=tab_info.url,
                )

            elif act == "close":
                closed = await self._controller.close_tab(index)
                if closed:
                    return ToolResult.ok(f"Closed tab {index if index is not None else 'active'}.")
                return ToolResult.fail("Could not close tab.")

            return ToolResult.fail(f"Unknown action '{action}'. Valid: list, new, switch, close.")
        except Exception as e:
            return ToolResult.fail(f"Tab operation failed: {e}")


# ---------------------------------------------------------------------------
# Download Web File
# ---------------------------------------------------------------------------


class DownloadWebFileTool(BaseTool):
    """Download a file from a URL or web element and save to destination folder."""

    def __init__(self, controller: BrowserController | None = None) -> None:
        self._controller = controller or _default_browser_ctrl
        self._downloader = BrowserDownloader(controller=self._controller)

    @property
    def name(self) -> str:
        return "download_web_file"

    @property
    def description(self) -> str:
        return (
            "Download a file (PDF, archive, document) from a URL or web link "
            "and save it to Documents or Downloads."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Download URL or element label/selector to click for download.",
                },
                "destination_folder": {
                    "type": "string",
                    "description": (
                        "Target folder name (e.g. 'Documents', 'Downloads') or custom path."
                    ),
                },
                "filename": {
                    "type": "string",
                    "description": "Optional custom filename to save as.",
                },
            },
            "required": ["target"],
        }

    @property
    def category(self) -> str:
        return "browser"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self,
        target: str = "",
        destination_folder: str | None = "Documents",
        filename: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        if not target:
            return ToolResult.fail("Parameter 'target' is required.")

        try:
            res = await self._downloader.download(
                url_or_click_target=target,
                destination_folder=destination_folder,
                filename=filename,
            )
            if not res.success:
                return ToolResult.fail(res.error or "Download failed")

            msg = (
                f"Successfully downloaded '{res.filename}' "
                f"({res.file_size_bytes} bytes) to {res.file_path}."
            )
            return ToolResult.ok(
                msg,
                file_path=res.file_path,
                filename=res.filename,
                size_bytes=res.file_size_bytes,
                sha256=res.sha256_hash,
            )
        except Exception as e:
            return ToolResult.fail(f"Download failed: {e}")


# ---------------------------------------------------------------------------
# Fill Web Form
# ---------------------------------------------------------------------------


class FillWebFormTool(BaseTool):
    """Autofill multiple fields in a web form."""

    def __init__(self, controller: BrowserController | None = None) -> None:
        self._controller = controller or _default_browser_ctrl
        self._interaction = BrowserInteraction(controller=self._controller)

    @property
    def name(self) -> str:
        return "fill_web_form"

    @property
    def description(self) -> str:
        return "Fill multiple form fields on current web page using a key-value mapping."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "object",
                    "description": (
                        "Key-value mapping of field labels/placeholders to input values."
                    ),
                },
            },
            "required": ["fields"],
        }

    @property
    def category(self) -> str:
        return "browser"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(self, fields: dict[str, str] | None = None, **kwargs: Any) -> ToolResult:
        if not fields:
            return ToolResult.fail("Parameter 'fields' dictionary is required.")

        try:
            results = await self._interaction.fill_form(fields)
            filled_count = sum(1 for v in results.values() if v)
            return ToolResult.ok(
                f"Filled {filled_count}/{len(fields)} form fields.",
                results=results,
            )
        except Exception as e:
            return ToolResult.fail(f"Form filling failed: {e}")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_browser_tools(controller: BrowserController | None = None) -> list[BaseTool]:
    """Return all browser automation tools."""
    ctrl = controller or _default_browser_ctrl
    return [
        OpenBrowserTool(controller=ctrl),
        NavigateWebTool(controller=ctrl),
        WebSearchBrowserTool(controller=ctrl),
        ClickWebElementTool(controller=ctrl),
        TypeWebElementTool(controller=ctrl),
        ScrollWebTool(controller=ctrl),
        ReadWebPageTool(controller=ctrl),
        ManageWebTabsTool(controller=ctrl),
        DownloadWebFileTool(controller=ctrl),
        FillWebFormTool(controller=ctrl),
    ]
