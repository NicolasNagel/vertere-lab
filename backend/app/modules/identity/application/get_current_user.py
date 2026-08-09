from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.modules.identity.application.session_tokens import SessionTokenGenerator
from app.modules.identity.domain.entities import RoleScope
from app.modules.identity.domain.errors import AccountInactiveError, SessionExpiredError
from app.modules.identity.domain.repositories import (
    ClinicMembershipRepository,
    LabMembershipRepository,
    RoleRepository,
    SessionRepository,
    UserRepository,
)
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock


@dataclass(frozen=True, kw_only=True)
class ResolveSessionCommand:
    token: str


class ResolveSessionUseCase:
    """Validates an opaque session token and returns the current user.

    Also performs sliding renewal: a session close to expiry is extended
    on every valid request, so an active user is never logged out
    mid-session (rule: sessão revogável, mas usuário ativo continua ativo).
    """

    def __init__(
        self,
        *,
        sessions: SessionRepository,
        users: UserRepository,
        roles: RoleRepository,
        memberships: LabMembershipRepository,
        clinic_memberships: ClinicMembershipRepository,
        token_generator: SessionTokenGenerator,
        clock: Clock,
        session_ttl: timedelta,
        session_ttl_remember_me: timedelta,
        renewal_threshold: timedelta,
    ) -> None:
        self._sessions = sessions
        self._users = users
        self._roles = roles
        self._memberships = memberships
        self._clinic_memberships = clinic_memberships
        self._token_generator = token_generator
        self._clock = clock
        self._session_ttl = session_ttl
        self._session_ttl_remember_me = session_ttl_remember_me
        self._renewal_threshold = renewal_threshold

    def execute(self, command: ResolveSessionCommand) -> ActorContext:
        token_hash = self._token_generator.hash(command.token)
        session = self._sessions.get_by_token_hash(token_hash)
        now = self._clock.now()

        if session is None or not session.is_valid(now=now):
            raise SessionExpiredError("Sessão expirada. Faça login novamente.")

        user = self._users.get_by_id(session.user_id)
        if user is None or not user.is_active:
            raise AccountInactiveError("Esta conta está inativa. Fale com o administrador.")

        role = self._roles.get_by_id(user.role_id)
        if role is None:
            raise RuntimeError(f"Papel {user.role_id} não encontrado para o usuário {user.id}.")

        clinic_ids = self._clinic_memberships.list_active_clinic_ids_for_user(user.id)
        access_available = (
            bool(clinic_ids)
            if role.scope is RoleScope.CLINIC
            else self._memberships.get_active_by_user_id(user.id) is not None
        )
        if not access_available:
            raise SessionExpiredError("Sessão expirada. Faça login novamente.")

        if session.expires_at - now < self._renewal_threshold:
            ttl = self._session_ttl_remember_me if session.remember_me else self._session_ttl
            session.renew(now=now, ttl=ttl)
            self._sessions.save(session)

        return ActorContext(
            user_id=user.id,
            email=str(user.email),
            full_name=user.full_name,
            role_id=role.id,
            role_name=role.name,
            role_scope=role.scope.value,
            permissions=role.permission_codes,
            clinic_ids=clinic_ids,
            row_version=user.row_version,
        )
