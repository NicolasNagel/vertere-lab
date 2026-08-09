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
from sqlalchemy.orm import Session as SqlAlchemySession

from app.api.dependencies import get_session
from app.core.config import Settings
from app.modules.identity.application.get_current_user import (
    ResolveSessionCommand,
    ResolveSessionUseCase,
)
from app.modules.identity.infrastructure.repositories import (
    SqlAlchemyClinicMembershipRepository,
    SqlAlchemyLabMembershipRepository,
    SqlAlchemyRoleRepository,
    SqlAlchemySessionRepository,
    SqlAlchemyUserRepository,
)
from app.modules.identity.infrastructure.session_tokens import OpaqueSessionTokens
from app.shared.application.authorization import ActorContext
from app.shared.domain.errors import ForbiddenError, UnauthenticatedError
from app.shared.infrastructure.clock import SystemClock

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
    session: SqlAlchemySession = Depends(get_session),
    token: str | None = Depends(get_session_token),
) -> ActorContext:
    if token is None:
        raise UnauthenticatedError("Sessão não encontrada.")

    settings = _settings(request)
    use_case = ResolveSessionUseCase(
        sessions=SqlAlchemySessionRepository(session),
        users=SqlAlchemyUserRepository(session),
        roles=SqlAlchemyRoleRepository(session),
        memberships=SqlAlchemyLabMembershipRepository(session),
        clinic_memberships=SqlAlchemyClinicMembershipRepository(session),
        token_generator=OpaqueSessionTokens(),
        clock=SystemClock(),
        session_ttl=timedelta(minutes=settings.session_ttl_minutes),
        session_ttl_remember_me=timedelta(days=settings.session_ttl_remember_me_days),
        renewal_threshold=timedelta(minutes=settings.session_renewal_threshold_minutes),
    )
    user = use_case.execute(ResolveSessionCommand(token=token))
    # Exceção deliberada: esta dependency de leitura comita a renovação
    # deslizante da sessão (um UPDATE pequeno), pois não há um caso de uso
    # de escrita separado só para isso.
    session.commit()
    return user


def require_permission(
    permission_code: str, *, clinic_scoped: bool = False
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
        return current_user

    return _dependency
