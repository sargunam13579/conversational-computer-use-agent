"""
NEXUS API — Health Endpoint.

Provides system status, version, uptime, and subsystem health information.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Request

from nexus.api.schemas import HealthResponse
from nexus.utils.logging import get_logger

log = get_logger("api.health")

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System health check",
    description="Returns NEXUS system status including version, uptime, LLM providers, and database connectivity.",
)
async def health_check(request: Request) -> HealthResponse:
    """Return the current health status of NEXUS."""
    app = request.app

    # Calculate uptime
    uptime = time.time() - app.state.start_time

    # Check database status
    db_status = "unknown"
    try:
        from nexus.database.engine import get_engine

        engine = get_engine()
        # Quick connectivity check
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_status = "connected"
    except RuntimeError:
        db_status = "not_initialized"
    except Exception as e:
        db_status = f"error: {e}"
        log.warning("Health check DB probe failed: %s", e)

    # Gather brain info
    brain = app.state.brain
    providers = brain._router.available_providers if brain.is_initialized else []
    tool_count = len(brain.available_tools) if brain.is_initialized else 0

    settings = app.state.settings

    return HealthResponse(
        status="ok",
        version=settings.version,
        uptime_seconds=round(uptime, 2),
        llm_providers=providers,
        tool_count=tool_count,
        database_status=db_status,
        environment=settings.log_level,
    )
