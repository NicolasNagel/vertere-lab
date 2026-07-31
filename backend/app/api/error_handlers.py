"""Error envelope for the whole API.

Every error response has the shape
``{"error": {"code", "message", "request_id", "details"}}`` with a stable
code. Stack traces never reach the client; unexpected errors are logged
server-side and answered as INTERNAL_ERROR.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.logging import request_id_var
from app.shared.domain.errors import DomainError, ErrorCode

logger = logging.getLogger("app.errors")

ERROR_STATUS: dict[ErrorCode, int] = {
    ErrorCode.UNAUTHENTICATED: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.FORBIDDEN: status.HTTP_403_FORBIDDEN,
    ErrorCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.VALIDATION_ERROR: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.CONFLICT: status.HTTP_409_CONFLICT,
    ErrorCode.INVALID_STATE_TRANSITION: status.HTTP_409_CONFLICT,
    ErrorCode.IDEMPOTENCY_CONFLICT: status.HTTP_409_CONFLICT,
    ErrorCode.ATTENDANCE_ALREADY_CLOSED: status.HTTP_409_CONFLICT,
    ErrorCode.CLOSURE_ALREADY_EXISTS: status.HTTP_409_CONFLICT,
    ErrorCode.PRICE_NOT_AVAILABLE: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.RATE_LIMITED: status.HTTP_429_TOO_MANY_REQUESTS,
    ErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def error_response(
    code: ErrorCode,
    message: str,
    *,
    status_code: int | None = None,
    details: list[dict[str, str]] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code or ERROR_STATUS[code],
        content={
            "error": {
                "code": code.value,
                "message": message,
                "request_id": request_id_var.get(),
                "details": details or [],
            }
        },
    )


async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    return error_response(exc.code, exc.message, details=exc.details)


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {
            "field": ".".join(str(part) for part in err.get("loc", [])),
            "reason": str(err.get("msg", "")),
        }
        for err in exc.errors()
    ]
    return error_response(
        ErrorCode.VALIDATION_ERROR,
        "Os dados enviados são inválidos.",
        details=details,
    )


_HTTP_STATUS_CODES: dict[int, ErrorCode] = {
    status.HTTP_401_UNAUTHORIZED: ErrorCode.UNAUTHENTICATED,
    status.HTTP_403_FORBIDDEN: ErrorCode.FORBIDDEN,
    status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
    status.HTTP_409_CONFLICT: ErrorCode.CONFLICT,
}


async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _HTTP_STATUS_CODES.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    message = exc.detail if isinstance(exc.detail, str) else "Erro ao processar a requisição."
    return error_response(code, message, status_code=exc.status_code)


async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
    # Last-resort net: a use case that skipped an explicit existence/
    # uniqueness check (or lost a race under real concurrency) hits a
    # DB constraint directly. Never leak table/column/constraint names to
    # the client (rule: .claude/rules/00-global.md, "erro não expõe detalhe
    # interno") — the safe fix belongs in the use case, this only prevents
    # a raw 500.
    logger.warning("integrity_error", extra={"path": request.url.path})
    return error_response(
        ErrorCode.CONFLICT,
        "A operação não pôde ser concluída porque conflita com dados existentes.",
    )


async def handle_stale_data_error(request: Request, exc: StaleDataError) -> JSONResponse:
    # Raised by SQLAlchemy's `version_id_col` optimistic locking
    # (`app/modules/attendances/infrastructure/models.py`) when a concurrent
    # write already changed the row — never a 500, the client should
    # reload and retry (rule: .claude/rules/12-attendance.md, "conflito de
    # versão retorna HTTP 409").
    logger.warning("stale_data_error", extra={"path": request.url.path})
    return error_response(
        ErrorCode.CONFLICT,
        "O registro foi alterado por outra operação. Recarregue e tente novamente.",
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error", extra={"path": request.url.path})
    return error_response(
        ErrorCode.INTERNAL_ERROR,
        "Erro interno. Tente novamente ou contate o suporte.",
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, handle_domain_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(IntegrityError, handle_integrity_error)  # type: ignore[arg-type]
    app.add_exception_handler(StaleDataError, handle_stale_data_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, handle_unexpected_error)
