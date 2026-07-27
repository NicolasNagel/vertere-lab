"""Domain errors with stable codes.

The presentation layer maps these to HTTP responses; messages must always be
safe to show to a client (no internals, no PII, no stack traces).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum


class ErrorCode(StrEnum):
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CONFLICT = "CONFLICT"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    ATTENDANCE_ALREADY_CLOSED = "ATTENDANCE_ALREADY_CLOSED"
    CLOSURE_ALREADY_EXISTS = "CLOSURE_ALREADY_EXISTS"
    PRICE_NOT_AVAILABLE = "PRICE_NOT_AVAILABLE"
    EXTERNAL_SERVICE_UNAVAILABLE = "EXTERNAL_SERVICE_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class DomainError(Exception):
    """Base class for expected business errors.

    Subclasses set ``code``; an expected error is never a 500.
    """

    code: ErrorCode = ErrorCode.INTERNAL_ERROR

    def __init__(
        self,
        message: str,
        *,
        details: Sequence[Mapping[str, str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details: list[dict[str, str]] = [dict(item) for item in details or []]


class NotFoundError(DomainError):
    code = ErrorCode.NOT_FOUND


class ForbiddenError(DomainError):
    code = ErrorCode.FORBIDDEN


class UnauthenticatedError(DomainError):
    code = ErrorCode.UNAUTHENTICATED


class ConflictError(DomainError):
    code = ErrorCode.CONFLICT


class ValidationError(DomainError):
    code = ErrorCode.VALIDATION_ERROR


class InvalidStateTransitionError(DomainError):
    code = ErrorCode.INVALID_STATE_TRANSITION


class ExternalServiceUnavailableError(DomainError):
    code = ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE


class RateLimitedError(DomainError):
    code = ErrorCode.RATE_LIMITED
