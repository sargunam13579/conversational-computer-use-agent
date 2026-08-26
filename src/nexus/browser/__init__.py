"""
NEXUS Browser Engine Package.

Provides high-performance web browsing, navigation, tab management, DOM interaction,
downloads, and page parsing.
"""

from nexus.browser.controller import BrowserController, TabInfo
from nexus.browser.downloader import BrowserDownloader, DownloadResult
from nexus.browser.interaction import BrowserInteraction
from nexus.browser.navigator import BrowserNavigator
from nexus.browser.page_reader import PageContent, PageLink, PageReader

__all__ = [
    "BrowserController",
    "TabInfo",
    "BrowserNavigator",
    "BrowserInteraction",
    "BrowserDownloader",
    "DownloadResult",
    "PageReader",
    "PageContent",
    "PageLink",
]
