"""Identity-specific domain errors — stable codes, safe messages.

Login failures for "user does not exist" and "wrong password" both raise
`InvalidCredentialsError` with the exact same message, on purpose (rule:
.claude/rules/auth-security-lgpd.md — protection against user enumeration).
`AccountInactiveError` is only ever raised *after* the password has already
matched, so revealing "this account is inactive" does not leak anything to
someone who does not already know the password.
"""

from __future__ import annotations

from app.shared.domain.errors import ConflictError, UnauthenticatedError


class InvalidCredentialsError(UnauthenticatedError):
    pass


class AccountInactiveError(UnauthenticatedError):
    pass


class SessionExpiredError(UnauthenticatedError):
    pass


class SelfLockoutError(ConflictError):
    pass


class EmailAlreadyExistsError(ConflictError):
    pass


class RoleNameAlreadyExistsError(ConflictError):
    pass
