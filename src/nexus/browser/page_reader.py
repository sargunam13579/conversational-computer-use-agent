"""
NEXUS Browser Page Reader — DOM Text Extraction, Headings & Link Discovery.

Extracts structured, readable page content, headings, and discoverable downloadable links.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from nexus.browser.controller import BrowserController
from nexus.utils.logging import get_logger

log = get_logger("browser.page_reader")


@dataclass
class PageLink:
    """A hyperlink discovered on the page."""

    text: str
    url: str
    is_download: bool = False


@dataclass
class PageContent:
    """Structured representation of extracted web page content."""

    title: str
    url: str
    text_content: str
    headings: list[str]
    links: list[PageLink]
    total_words: int


class PageReader:
    """Reads and parses active web page content."""

    def __init__(self, controller: BrowserController | None = None) -> None:
        self._controller = controller or BrowserController()

    @property
    def controller(self) -> BrowserController:
        return self._controller

    async def read(self, max_length: int = 4000) -> PageContent:
        """Extract structured text, headings, and links from active page."""
        page = await self._controller.get_active_page()

        title = await page.title() or "Untitled"
        url = page.url or "about:blank"

        # Extract structured content via JS evaluation
        dom_data = await page.evaluate(
            """() => {
            // Remove noise (scripts, styles, hidden elements)
            const scripts = document.querySelectorAll('script, style, noscript, nav, footer, svg');
            scripts.forEach(s => s.remove());

            // Extract Headings
            const headings = [];
            document.querySelectorAll('h1, h2, h3').forEach(h => {
                const t = h.innerText.trim();
                if (t.length > 0) headings.push(t);
            });

            // Extract Links
            const links = [];
            document.querySelectorAll('a[href]').forEach(a => {
                const t = a.innerText.trim();
                const u = a.href;
                if (t.length > 0 && u.startsWith('http')) {
                    links.push({
                        text: t.substring(0, 100),
                        url: u,
                        is_download: /\\.(pdf|zip|tar|gz|exe|docx|xlsx|csv)(\\?.*)?$/i.test(u)
                    });
                }
            });

            // Extract Body Text
            const bodyText = document.body ? document.body.innerText : '';
            return {
                headings: headings.slice(0, 20),
                links: links.slice(0, 50),
                bodyText: bodyText
            };
        }"""
        )

        raw_text = dom_data.get("bodyText", "")
        # Clean multiple spaces and blank lines
        clean_text = re.sub(r"\n\s*\n+", "\n\n", raw_text).strip()
        if len(clean_text) > max_length:
            clean_text = clean_text[:max_length] + "\n... [Content truncated for display]"

        headings = dom_data.get("headings", [])
        raw_links = dom_data.get("links", [])
        page_links = [
            PageLink(
                text=link_item.get("text", ""),
                url=link_item.get("url", ""),
                is_download=link_item.get("is_download", False),
            )
            for link_item in raw_links
        ]

        words = len(clean_text.split())
        return PageContent(
            title=title,
            url=url,
            text_content=clean_text,
            headings=headings,
            links=page_links,
            total_words=words,
        )

    async def find_download_links(self, extension: str = "pdf") -> list[PageLink]:
        """Find links on the page pointing to downloadable files of specific extension."""
        content = await self.read()
        ext_clean = extension.lower().lstrip(".")
        matches = [
            link
            for link in content.links
            if ext_clean in link.url.lower() or ext_clean in link.text.lower()
        ]
        return matches
