"""
NEXUS API — Browser Automation Endpoints.

Provides REST endpoints for:
- Opening browser and navigating URLs
- Web searches
- Element interaction (click, type, scroll, form fill)
- Tab management
- Downloading files and reading page content
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from nexus.browser.controller import BrowserController
from nexus.browser.downloader import BrowserDownloader
from nexus.browser.interaction import BrowserInteraction
from nexus.browser.navigator import BrowserNavigator
from nexus.browser.page_reader import PageReader

router = APIRouter(prefix="/browser", tags=["Browser Automation"])

# Global shared instances
_browser_ctrl = BrowserController()
_navigator = BrowserNavigator(controller=_browser_ctrl)
_interaction = BrowserInteraction(controller=_browser_ctrl)
_downloader = BrowserDownloader(controller=_browser_ctrl)
_reader = PageReader(controller=_browser_ctrl)


class NavigateRequest(BaseModel):
    url: str


class SearchRequest(BaseModel):
    query: str
    engine: str = "duckduckgo"


class ClickRequest(BaseModel):
    target: str


class TypeRequest(BaseModel):
    text: str
    target: str | None = None
    press_enter: bool = False


class ScrollRequest(BaseModel):
    direction: str = "down"
    amount: int = 500


class TabActionRequest(BaseModel):
    action: str = Field(description="'list', 'new', 'switch', 'close'")
    index: int | None = None
    url: str | None = None


class DownloadRequest(BaseModel):
    target: str
    destination_folder: str = "Documents"
    filename: str | None = None


class FormFillRequest(BaseModel):
    fields: dict[str, str]


@router.post("/navigate")
async def navigate(req: NavigateRequest) -> dict[str, Any]:
    """Navigate active browser page to URL."""
    res = await _navigator.navigate(req.url)
    return res


@router.post("/search")
async def search(req: SearchRequest) -> dict[str, Any]:
    """Search web using specified search engine."""
    res = await _navigator.search(req.query, engine=req.engine)
    return res


@router.post("/click")
async def click_element(req: ClickRequest) -> dict[str, Any]:
    """Click element on active page."""
    success = await _interaction.click(req.target)
    if not success:
        raise HTTPException(status_code=400, detail=f"Could not click target '{req.target}'")
    return {"success": True, "target": req.target}


@router.post("/type")
async def type_element(req: TypeRequest) -> dict[str, Any]:
    """Type text into element or focused control."""
    success = await _interaction.type_text(
        target=req.target, text=req.text, press_enter=req.press_enter
    )
    if not success:
        raise HTTPException(status_code=400, detail=f"Could not type into target '{req.target}'")
    return {"success": True, "text_length": len(req.text)}


@router.post("/scroll")
async def scroll_page(req: ScrollRequest) -> dict[str, Any]:
    """Scroll webpage."""
    success = await _interaction.scroll(direction=req.direction, amount=req.amount)
    return {"success": success, "direction": req.direction, "amount": req.amount}


@router.get("/content")
async def read_page(max_words: int = Query(default=600, ge=50, le=5000)) -> dict[str, Any]:
    """Extract readable text content and links from active page."""
    content = await _reader.read(max_length=max_words * 6)
    return {
        "title": content.title,
        "url": content.url,
        "total_words": content.total_words,
        "headings": content.headings,
        "text_content": content.text_content,
        "links_count": len(content.links),
    }


@router.post("/tabs")
async def manage_tabs(req: TabActionRequest) -> dict[str, Any]:
    """Manage browser tabs."""
    act = req.action.lower()
    if act == "list":
        tabs = await _browser_ctrl.list_tabs()
        return {
            "tabs": [
                {"index": t.index, "title": t.title, "url": t.url, "active": t.is_active}
                for t in tabs
            ]
        }
    elif act == "new":
        tab = await _browser_ctrl.new_tab(url=req.url)
        return {"action": "new", "index": tab.index, "title": tab.title, "url": tab.url}
    elif act == "switch":
        if req.index is None:
            raise HTTPException(status_code=400, detail="Missing 'index' parameter")
        tab = await _browser_ctrl.switch_tab(req.index)
        return {"action": "switch", "index": tab.index, "title": tab.title, "url": tab.url}
    elif act == "close":
        closed = await _browser_ctrl.close_tab(req.index)
        return {"action": "close", "success": closed}
    raise HTTPException(status_code=400, detail=f"Invalid tab action '{req.action}'")


@router.post("/download")
async def download_file(req: DownloadRequest) -> dict[str, Any]:
    """Download a file and save to target directory."""
    res = await _downloader.download(
        url_or_click_target=req.target,
        destination_folder=req.destination_folder,
        filename=req.filename,
    )
    if not res.success:
        raise HTTPException(status_code=400, detail=res.error or "Download failed")
    return {
        "success": True,
        "file_path": res.file_path,
        "filename": res.filename,
        "size_bytes": res.file_size_bytes,
        "sha256": res.sha256_hash,
    }


@router.post("/form")
async def fill_form(req: FormFillRequest) -> dict[str, Any]:
    """Fill multiple fields in a form."""
    results = await _interaction.fill_form(req.fields)
    return {"results": results, "filled": sum(1 for v in results.values() if v)}
