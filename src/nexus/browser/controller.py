"""
NEXUS Browser Controller — Playwright-backed Browser & Tab Management.

Provides high-performance browser lifecycle management:
- Starting/stopping Playwright Chromium/Edge instances
- Context and multi-tab lifecycle (open, close, switch, list)
- Auto-reconnection and headless/headed mode support
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import Any

from nexus.utils.logging import get_logger

log = get_logger("browser.controller")


@dataclass
class TabInfo:
    """Metadata describing a browser tab/page."""

    index: int
    title: str
    url: str
    is_active: bool = False


class BrowserController:
    """Manages Playwright browser engine, browser contexts, and tab instances."""

    def __init__(self, headless: bool = True, browser_type: str = "chromium") -> None:
        self._headless = headless
        self._browser_type = browser_type
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._pages: list[Any] = []
        self._active_page_idx: int = 0
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        """Check if browser process is actively running."""
        return self._browser is not None and self._browser.is_connected()

    async def start(self) -> None:
        """Start Playwright browser engine and default page context."""
        async with self._lock:
            if self.is_running:
                return

            try:
                import importlib

                playwright_mod = importlib.import_module("playwright.async_api")
                async_playwright = playwright_mod.async_playwright

                self._playwright = await async_playwright().start()

                browser_launcher = getattr(
                    self._playwright, self._browser_type, self._playwright.chromium
                )
                self._browser = await browser_launcher.launch(
                    headless=self._headless,
                    args=["--no-sandbox", "--disable-setuid-sandbox"],
                )

                self._context = await self._browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    accept_downloads=True,
                )

                page = await self._context.new_page()
                self._pages = [page]
                self._active_page_idx = 0
                log.info("Browser controller started successfully (%s)", self._browser_type)
            except Exception as e:
                log.warning("Could not launch Playwright browser: %s", e)
                # Ensure state is reset
                await self._cleanup()
                raise

    async def get_active_page(self) -> Any:
        """Get current active Playwright Page instance, starting browser if necessary."""
        if not self.is_running:
            await self.start()

        async with self._lock:
            if not self._pages:
                if self._context:
                    page = await self._context.new_page()
                    self._pages.append(page)
                    self._active_page_idx = 0
                else:
                    raise RuntimeError("Browser context not available")

            idx = max(0, min(self._active_page_idx, len(self._pages) - 1))
            return self._pages[idx]

    async def new_tab(self, url: str | None = None) -> TabInfo:
        """Open a new browser tab and optionally navigate to URL."""
        if not self.is_running:
            await self.start()

        async with self._lock:
            if not self._context:
                raise RuntimeError("Browser context is not initialized")

            page = await self._context.new_page()
            self._pages.append(page)
            self._active_page_idx = len(self._pages) - 1

        if url:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except Exception as e:
                log.warning("Navigation to '%s' timed out or failed: %s", url, e)

        title = await page.title() or "New Tab"
        return TabInfo(
            index=self._active_page_idx,
            title=title,
            url=page.url or (url or "about:blank"),
            is_active=True,
        )

    async def close_tab(self, index: int | None = None) -> bool:
        """Close a specific tab or active tab."""
        if not self.is_running:
            return False

        async with self._lock:
            if not self._pages:
                return False

            target_idx = self._active_page_idx if index is None else index
            if target_idx < 0 or target_idx >= len(self._pages):
                return False

            page_to_close = self._pages.pop(target_idx)
            try:
                await page_to_close.close()
            except Exception as e:
                log.warning("Error closing page: %s", e)

            # Adjust active tab index
            if not self._pages:
                if self._context:
                    new_p = await self._context.new_page()
                    self._pages.append(new_p)
                    self._active_page_idx = 0
            else:
                self._active_page_idx = min(self._active_page_idx, len(self._pages) - 1)

            return True

    async def switch_tab(self, index: int) -> TabInfo:
        """Switch active tab to specified index."""
        if not self.is_running:
            await self.start()

        async with self._lock:
            if index < 0 or index >= len(self._pages):
                raise IndexError(f"Tab index {index} out of range (0-{len(self._pages) - 1})")

            self._active_page_idx = index
            page = self._pages[index]

        title = await page.title() or "Tab"
        return TabInfo(
            index=index,
            title=title,
            url=page.url,
            is_active=True,
        )

    async def list_tabs(self) -> list[TabInfo]:
        """List all open browser tabs and their URLs."""
        if not self.is_running:
            return []

        tabs: list[TabInfo] = []
        for i, page in enumerate(self._pages):
            try:
                t = await page.title() or "Untitled"
                u = page.url or "about:blank"
                tabs.append(
                    TabInfo(
                        index=i,
                        title=t,
                        url=u,
                        is_active=(i == self._active_page_idx),
                    )
                )
            except Exception:
                tabs.append(
                    TabInfo(
                        index=i, title="Tab", url="unknown", is_active=(i == self._active_page_idx)
                    )
                )

        return tabs

    async def _cleanup(self) -> None:
        """Internal resource teardown."""
        self._pages.clear()
        self._active_page_idx = 0
        if self._context:
            with contextlib.suppress(Exception):
                await self._context.close()
            self._context = None

        if self._browser:
            with contextlib.suppress(Exception):
                await self._browser.close()
            self._browser = None

        if self._playwright:
            with contextlib.suppress(Exception):
                await self._playwright.stop()
            self._playwright = None

    async def stop(self) -> None:
        """Stop and close all browser instances."""
        async with self._lock:
            await self._cleanup()
            log.info("Browser controller stopped.")
