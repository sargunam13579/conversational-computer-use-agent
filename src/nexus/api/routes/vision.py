"""
NEXUS API — Vision & Screen Understanding Endpoints.

Provides REST endpoints for:
- Screen scene description
- UI element location
- Click & UI automation
- Privacy settings and capture audit logs
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from nexus.vision.analyzer import ScreenAnalyzer
from nexus.vision.privacy import ScreenPermissionMode

router = APIRouter(prefix="/vision", tags=["Vision & Screen"])

# Global shared vision analyzer instance
_analyzer = ScreenAnalyzer()


class LocateRequest(BaseModel):
    element_name: str
    element_type: str | None = None


class ClickRequest(BaseModel):
    element_name: str | None = None
    x: int | None = None
    y: int | None = None
    double_click: bool = False


class PrivacyUpdateRequest(BaseModel):
    mode: str | None = None
    add_sensitive_pattern: str | None = None
    remove_sensitive_pattern: str | None = None


@router.get("/screen/describe")
async def describe_screen(crop_to_active_window: bool = Query(default=False)) -> dict[str, Any]:
    """Capture and return comprehensive natural language description of screen."""
    report = await _analyzer.analyze_screen(
        crop_to_active_window=crop_to_active_window, source="api"
    )
    return {
        "description": report.description,
        "app_name": report.app_name,
        "window_title": report.window_title,
        "buttons": report.buttons,
        "input_fields": report.input_fields,
        "menus": report.menus,
        "ocr_text_preview": report.ocr_text_preview,
        "elements_count": len(report.elements),
        "timestamp": report.timestamp,
    }


@router.post("/screen/locate")
async def locate_element(req: LocateRequest) -> dict[str, Any]:
    """Locate a UI element on screen by name/label."""
    element, explanation = _analyzer.locate_element(req.element_name, element_type=req.element_type)
    if not element:
        raise HTTPException(status_code=404, detail=explanation)

    cx, cy = element.center
    return {
        "found": True,
        "explanation": explanation,
        "name": element.name,
        "type": element.element_type.value,
        "x": element.x,
        "y": element.y,
        "cx": cx,
        "cy": cy,
        "width": element.width,
        "height": element.height,
        "relative_position": element.relative_position,
    }


@router.post("/screen/click")
async def click_element(req: ClickRequest) -> dict[str, Any]:
    """Click on a UI element or screen coordinates."""
    from nexus.tools.vision.screen_tools import ClickElementTool

    tool = ClickElementTool(analyzer=_analyzer)

    res = await tool.execute(
        element_name=req.element_name,
        x=req.x,
        y=req.y,
        double_click=req.double_click,
    )
    if not res.success:
        raise HTTPException(status_code=400, detail=res.error or res.output)

    return {
        "success": True,
        "output": res.output,
        "data": res.data,
    }


@router.get("/screen/privacy")
async def get_privacy_settings() -> dict[str, Any]:
    """Get current screen privacy settings and sensitive application filter."""
    return {
        "mode": _analyzer.privacy.mode.value,
        "sensitive_patterns": _analyzer.privacy.sensitive_patterns,
    }


@router.post("/screen/privacy")
async def update_privacy_settings(req: PrivacyUpdateRequest) -> dict[str, Any]:
    """Update screen privacy settings."""
    if req.mode:
        try:
            _analyzer.privacy.mode = ScreenPermissionMode(req.mode)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}") from err

    if req.add_sensitive_pattern:
        _analyzer.privacy.add_sensitive_pattern(req.add_sensitive_pattern)

    if req.remove_sensitive_pattern:
        _analyzer.privacy.remove_sensitive_pattern(req.remove_sensitive_pattern)

    return {
        "status": "updated",
        "mode": _analyzer.privacy.mode.value,
        "sensitive_patterns": _analyzer.privacy.sensitive_patterns,
    }


@router.get("/screen/logs")
async def get_screen_logs(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    """Retrieve audit logs of screen capture and analysis events."""
    logs = _analyzer.privacy.get_audit_logs(limit=limit)
    return [
        {
            "log_id": item.log_id,
            "timestamp": item.timestamp,
            "request_source": item.request_source,
            "window_title": item.window_title,
            "is_sensitive": item.is_sensitive,
            "allowed": item.allowed,
            "reason": item.reason,
            "image_hash": item.image_hash,
            "elements_detected": item.elements_detected,
            "duration_ms": item.duration_ms,
        }
        for item in logs
    ]
