"""Dependency-free HTTP request telemetry for the portfolio service."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import Request, Response

RequestHandler = Callable[[Request], Awaitable[Response]]


async def request_observability(request: Request, call_next: RequestHandler) -> Response:
    """Attach a request ID and emit one structured completion event."""
    request_id = request.headers.get("x-request-id") or str(uuid4())
    started = perf_counter()
    status_code = 500
    error_classification: str | None = None
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as error:
        error_classification = type(error).__name__
        raise
    finally:
        structlog.get_logger("workflowtwin.request").info(
            "http_request_completed",
            request_id=request_id,
            method=request.method,
            endpoint=request.url.path,
            status=status_code,
            duration_ms=round((perf_counter() - started) * 1000, 2),
            error_classification=error_classification,
            pilot_mutation=(
                request.method != "GET" and request.url.path.startswith("/api/v1/pilot")
            ),
        )
    response.headers["x-request-id"] = request_id
    return response
