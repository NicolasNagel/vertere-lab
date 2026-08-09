from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.identity.application.dtos import SessionIssuedDTO
from app.modules.identity.application.password_hasher import PasswordHasher
from app.modules.identity.application.session_tokens import SessionTokenGenerator
from app.modules.identity.domain.entities import RoleScope, Session
from app.modules.identity.domain.errors import AccountInactiveError, InvalidCredentialsError
from app.modules.identity.domain.repositories import (
    ClinicMembershipRepository,
    LabMembershipRepository,
    LoginFailureRepository,
    RoleRepository,
    SessionRepository,
    UserRepository,
)
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import RateLimitedError


@dataclass(frozen=True, kw_only=True)
class LoginCommand:
    login: str
    password: str
    remember_me: bool
    ip_address: str | None
    user_agent: str | None
    request_id: str | None


class LoginUseCase:
    def __init__(
        self,
        *,
        users: UserRepository,
        roles: RoleRepository,
        sessions: SessionRepository,
        memberships: LabMembershipRepository,
        clinic_memberships: ClinicMembershipRepository,
        login_failures: LoginFailureRepository,
        password_hasher: PasswordHasher,
        token_generator: SessionTokenGenerator,
        audit: AuditLogWriter,
        clock: Clock,
        session_ttl: timedelta,
        session_ttl_remember_me: timedelta,
        rate_limit_max_attempts: int,
        rate_limit_window: timedelta,
    ) -> None:
        self._users = users
        self._roles = roles
        self._sessions = sessions
        self._memberships = memberships
        self._clinic_memberships = clinic_memberships
        self._login_failures = login_failures
        self._password_hasher = password_hasher
        self._token_generator = token_generator
        self._audit = audit
        self._clock = clock
        self._session_ttl = session_ttl
        self._session_ttl_remember_me = session_ttl_remember_me
        self._rate_limit_max_attempts = rate_limit_max_attempts
        self._rate_limit_window = rate_limit_window

    def execute(self, command: LoginCommand) -> SessionIssuedDTO:
        normalized_login = command.login.strip().lower()
        now = self._clock.now()

        # Checado por login normalizado, não por IP: bloqueia quem está
        # tentando adivinhar a senha de UMA conta específica, inclusive
        # contra e-mail inexistente (rule: .claude/rules/06-auth-security-lgpd.md
        # — "proteção contra enumeração"). Antes de verificar a senha, não
        # depois: sem isso o Argon2 roda a cada tentativa mesmo já bloqueada,
        # o próprio hash vira o custo que o rate limit deveria evitar.
        recent_failures = self._login_failures.count_recent_failures(
            normalized_login, since=now - self._rate_limit_window
        )
        if recent_failures >= self._rate_limit_max_attempts:
            self._audit.record(
                AuditEntry(
                    actor_user_id=None,
                    actor_scope=ActorScope.ANONYMOUS,
                    action="auth.login_rate_limited",
                    entity_type="user",
                    entity_id=None,
                    ip_address=command.ip_address,
                    request_id=command.request_id,
                )
            )
            raise RateLimitedError("Muitas tentativas. Tente novamente mais tarde.")

        user = self._users.get_by_email(normalized_login)

        if user is None or not self._password_hasher.verify(command.password, user.password_hash):
            self._login_failures.record_failure(normalized_login, occurred_at=now)
            self._audit.record(
                AuditEntry(
                    actor_user_id=user.id if user is not None else None,
                    actor_scope=ActorScope.ANONYMOUS,
                    action="auth.login_failed",
                    entity_type="user",
                    entity_id=str(user.id) if user is not None else None,
                    after_state={"reason": "invalid_credentials"},
                    ip_address=command.ip_address,
                    request_id=command.request_id,
                )
            )
            raise InvalidCredentialsError("Usuário ou senha inválidos.")

        if not user.is_active:
            self._login_failures.record_failure(normalized_login, occurred_at=now)
            self._audit.record(
                AuditEntry(
                    actor_user_id=user.id,
                    actor_scope=ActorScope.LAB,
                    action="auth.login_failed",
                    entity_type="user",
                    entity_id=str(user.id),
                    after_state={"reason": "inactive"},
                    ip_address=command.ip_address,
                    request_id=command.request_id,
                )
            )
            raise AccountInactiveError(
                "Esta conta está inativa. Fale com o administrador.",
                details=[{"reason": "inactive"}],
            )

        role = self._roles.get_by_id(user.role_id)
        if role is None:
            raise RuntimeError(f"Papel {user.role_id} não encontrado para o usuário {user.id}.")

        lab_membership = self._memberships.get_active_by_user_id(user.id)
        clinic_ids = self._clinic_memberships.list_active_clinic_ids_for_user(user.id)
        access_available = (
            bool(clinic_ids) if role.scope is RoleScope.CLINIC else lab_membership is not None
        )
        if not access_available:
            self._login_failures.record_failure(normalized_login, occurred_at=now)
            self._audit.record(
                AuditEntry(
                    actor_user_id=user.id,
                    actor_scope=ActorScope.ANONYMOUS,
                    action="auth.login_failed",
                    entity_type="user",
                    entity_id=str(user.id),
                    after_state={"reason": "internal_access_unavailable"},
                    ip_address=command.ip_address,
                    request_id=command.request_id,
                )
            )
            raise InvalidCredentialsError("Usuário ou senha inválidos.")

        self._login_failures.clear(normalized_login)
        ttl = self._session_ttl_remember_me if command.remember_me else self._session_ttl
        token = self._token_generator.generate()
        session = Session(
            id=uuid4(),
            user_id=user.id,
            token_hash=self._token_generator.hash(token),
            created_at=now,
            last_seen_at=now,
            expires_at=now + ttl,
            remember_me=command.remember_me,
            ip_address=command.ip_address,
            user_agent=command.user_agent,
        )
        self._sessions.add(session)

        self._audit.record(
            AuditEntry(
                actor_user_id=user.id,
                actor_scope=ActorScope.LAB,
                action="auth.login_succeeded",
                entity_type="user",
                entity_id=str(user.id),
                ip_address=command.ip_address,
                request_id=command.request_id,
            )
        )

        authenticated = ActorContext(
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
        return SessionIssuedDTO(token=token, expires_at=session.expires_at, user=authenticated)
