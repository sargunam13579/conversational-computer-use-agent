"""
NEXUS API — Middleware.

Error handling and request tracing middleware for the FastAPI application.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from nexus.utils.logging import get_logger

log = get_logger("api.middleware")


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Catches all unhandled exceptions and returns structured JSON error responses.

    This prevents raw stack traces from leaking to API consumers and ensures
    every error response has a consistent shape.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            log.error(
                "Unhandled exception on %s %s: %s",
                request.method,
                request.url.path,
                exc,
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "message": "An unexpected error occurred. Please try again.",
                    "detail": str(exc) if request.app.state.debug else None,
                },
            )


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Assigns a unique request ID to each incoming request for tracing.

    The ID is:
    - Taken from the X-Request-ID header if the client provides one
    - Auto-generated as a UUID4 otherwise
    - Returned in the response X-Request-ID header
    - Stored in request.state for use by handlers
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        start_time = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start_time

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed:.3f}s"

        log.debug(
            "%s %s → %d (%.3fs) [%s]",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
            request_id[:8],
        )

        return response
