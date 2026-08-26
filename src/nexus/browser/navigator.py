"""
NEXUS Browser Navigator — Web Navigation and Search Engine Querying.

Provides high-level navigation, query construction, and history traversal.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

from nexus.browser.controller import BrowserController
from nexus.utils.logging import get_logger

log = get_logger("browser.navigator")


class BrowserNavigator:
    """Manages URL navigation, searches, and history controls."""

    def __init__(self, controller: BrowserController | None = None) -> None:
        self._controller = controller or BrowserController()

    @property
    def controller(self) -> BrowserController:
        return self._controller

    def _format_url(self, target: str) -> str:
        """Ensure URL has valid schema (http/https) or convert to search query."""
        target = target.strip()
        if target.startswith(("http://", "https://", "about:", "chrome:", "edge:", "file://")):
            return target
        if "." in target and " " not in target:
            return f"https://{target}"
        # If phrase or keywords, format as DuckDuckGo search
        encoded = urllib.parse.quote_plus(target)
        return f"https://duckduckgo.com/?q={encoded}"

    async def navigate(
        self, url: str, wait_until: str = "domcontentloaded", timeout_ms: int = 20000
    ) -> dict[str, Any]:
        """Navigate active page to URL."""
        page = await self._controller.get_active_page()
        final_url = self._format_url(url)

        try:
            response = await page.goto(final_url, wait_until=wait_until, timeout=timeout_ms)
            status_code = response.status if response else 200
        except Exception as e:
            log.warning("Navigation to '%s' encountered error: %s", final_url, e)
            status_code = 500

        title = await page.title()
        current_url = page.url
        return {
            "title": title or "Page",
            "url": current_url,
            "status_code": status_code,
        }

    async def search(
        self,
        query: str,
        engine: str = "duckduckgo",
        wait_until: str = "domcontentloaded",
        timeout_ms: int = 20000,
    ) -> dict[str, Any]:
        """Perform search using specified engine (duckduckgo, google, bing)."""
        encoded_query = urllib.parse.quote_plus(query.strip())
        engine_clean = engine.lower().strip()

        if "google" in engine_clean:
            search_url = f"https://www.google.com/search?q={encoded_query}"
        elif "bing" in engine_clean:
            search_url = f"https://www.bing.com/search?q={encoded_query}"
        else:
            search_url = f"https://duckduckgo.com/?q={encoded_query}"

        return await self.navigate(search_url, wait_until=wait_until, timeout_ms=timeout_ms)

    async def go_back(self) -> bool:
        """Navigate back in page history."""
        page = await self._controller.get_active_page()
        try:
            res = await page.go_back(wait_until="domcontentloaded", timeout=10000)
            return res is not None
        except Exception:
            return False

    async def go_forward(self) -> bool:
        """Navigate forward in page history."""
        page = await self._controller.get_active_page()
        try:
            res = await page.go_forward(wait_until="domcontentloaded", timeout=10000)
            return res is not None
        except Exception:
            return False

    async def reload(self) -> bool:
        """Reload current active page."""
        page = await self._controller.get_active_page()
        try:
            await page.reload(wait_until="domcontentloaded", timeout=15000)
            return True
        except Exception:
            return False
