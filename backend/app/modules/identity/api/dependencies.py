"""FastAPI dependencies for authentication/authorization.

Extends `app.api.dependencies` (session/unit-of-work) rather than
duplicating it. `require_permission` already accepts `clinic_scoped` so
Fase 2 can plug clinic-scoped authorization in without changing this
interface — no caller passes `clinic_scoped=True` yet, since there is no
`Clinic`/`ClinicMembership` to check against.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from fastapi import Depends, Request, Security
from fastapi.security import APIKeyCookie

from app.api.dependencies import get_unit_of_work
from app.core.config import Settings
from app.modules.identity.application.get_current_user import (
    ResolveSessionCommand,
)
from app.modules.identity.application.session_handlers import (
    handle_resolve_session,
)
from app.modules.identity.infrastructure.session_tokens import OpaqueSessionTokens
from app.modules.identity.infrastructure.uow import SqlAlchemyIdentityUnitOfWork
from app.shared.application.authorization import ActorContext, RoleScope
from app.shared.domain.errors import ForbiddenError, UnauthenticatedError
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork

session_cookie_scheme = APIKeyCookie(
    name="vertere_session",
    scheme_name="SessionCookie",
    auto_error=False,
)


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_session_token(
    request: Request,
    _documented_token: str | None = Security(session_cookie_scheme),
) -> str | None:
    settings = _settings(request)
    return request.cookies.get(settings.session_cookie_name)


def get_current_user(
    request: Request,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    token: str | None = Depends(get_session_token),
) -> ActorContext:
    if token is None:
        raise UnauthenticatedError("Sessão não encontrada.")

    settings = _settings(request)
    return handle_resolve_session(
        uow=SqlAlchemyIdentityUnitOfWork(uow),
        command=ResolveSessionCommand(token=token),
        token_generator=OpaqueSessionTokens(),
        clock=SystemClock(),
        session_ttl=timedelta(minutes=settings.session_ttl_minutes),
        session_ttl_remember_me=timedelta(days=settings.session_ttl_remember_me_days),
        renewal_threshold=timedelta(minutes=settings.session_renewal_threshold_minutes),
    )


def require_permission(
    permission_code: str,
    *,
    clinic_scoped: bool = False,
    allowed_scopes: frozenset[RoleScope] | None = None,
) -> Callable[..., ActorContext]:
    if clinic_scoped:
        raise NotImplementedError(
            "Escopo de clínica ainda não implementado — chega com Clinic na Fase 2."
        )

    def _dependency(
        current_user: ActorContext = Depends(get_current_user),
    ) -> ActorContext:
        if permission_code not in current_user.permissions:
            raise ForbiddenError(f"Permissão ausente: {permission_code}")
        if allowed_scopes is not None and current_user.role_scope not in allowed_scopes:
            raise ForbiddenError("Este recurso é exclusivo do laboratório.")
        return current_user

    return _dependency
