"""Request context middleware: request id + structured access log."""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.logging import request_id_var

logger = logging.getLogger("app.access")

REQUEST_ID_HEADER = "X-Request-ID"
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, trusted_browser_origins: tuple[str, ...] = ()) -> None:
        super().__init__(app)
        self._trusted_browser_origins = frozenset(
            origin.rstrip("/") for origin in trusted_browser_origins
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        response: Response
        try:
            if self._has_untrusted_origin(request):
                response = JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "CSRF_ORIGIN_FORBIDDEN",
                            "message": "Origem da requisição não autorizada.",
                            "details": [],
                            "request_id": request_id,
                        }
                    },
                )
            else:
                response = await call_next(request)
        finally:
            request_id_var.reset(token)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    def _has_untrusted_origin(self, request: Request) -> bool:
        if request.method in SAFE_METHODS:
            return False
        origin = request.headers.get("origin")
        if origin is None:
            return False
        normalized_origin = origin.rstrip("/")
        request_origin = f"{request.url.scheme}://{request.url.netloc}"
        return (
            normalized_origin != request_origin
            and normalized_origin not in self._trusted_browser_origins
        )
