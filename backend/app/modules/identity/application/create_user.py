from __future__ import annotations

import secrets
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.identity.application.dtos import (
    AuthenticatedUserDTO,
    UserCreatedDTO,
    UserSummaryDTO,
)
from app.modules.identity.application.password_hasher import PasswordHasher
from app.modules.identity.domain.entities import LabMembership, User
from app.modules.identity.domain.errors import EmailAlreadyExistsError
from app.modules.identity.domain.repositories import (
    LabMembershipRepository,
    RoleRepository,
    UserRepository,
)
from app.modules.identity.domain.value_objects import Email
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "users.create"
_TEMPORARY_PASSWORD_BYTES = 12


@dataclass(frozen=True, kw_only=True)
class CreateUserCommand:
    actor: AuthenticatedUserDTO
    email: str
    full_name: str
    role_id: UUID


class CreateUserUseCase:
    """Creates a user directly, without a transactional-email invite flow.

    There is no outbox/e-mail infrastructure in this slice, so the temporary
    password is returned once, in the response, to the creator (never
    logged). The created user must change it on first login
    (`must_change_password`, enforced by the presentation layer / a future
    increment — not re-validated here beyond flagging it).
    """

    def __init__(
        self,
        *,
        users: UserRepository,
        roles: RoleRepository,
        memberships: LabMembershipRepository,
        password_hasher: PasswordHasher,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._users = users
        self._roles = roles
        self._memberships = memberships
        self._password_hasher = password_hasher
        self._audit = audit
        self._clock = clock

    def execute(self, command: CreateUserCommand) -> UserCreatedDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        email = Email(command.email)
        if self._users.get_by_email(str(email)) is not None:
            raise EmailAlreadyExistsError("E-mail já cadastrado.")

        role = self._roles.get_by_id(command.role_id)
        if role is None:
            raise NotFoundError("Papel não encontrado.")

        now = self._clock.now()
        temporary_password = secrets.token_urlsafe(_TEMPORARY_PASSWORD_BYTES)
        user = User(
            id=uuid4(),
            email=email,
            full_name=command.full_name,
            password_hash=self._password_hasher.hash(temporary_password),
            is_active=True,
            role_id=role.id,
            created_by=command.actor.id,
            created_at=now,
            updated_at=now,
        )
        self._users.add(user)
        self._memberships.add(
            LabMembership(
                id=uuid4(),
                user_id=user.id,
                granted_at=now,
                granted_by=command.actor.id,
            )
        )

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="users.created",
                entity_type="user",
                entity_id=str(user.id),
                after_state={"email": str(email), "role_id": str(role.id)},
                request_id=None,
            )
        )

        return UserCreatedDTO(
            user=UserSummaryDTO(
                id=user.id,
                email=str(user.email),
                full_name=user.full_name,
                is_active=user.is_active,
                role_id=role.id,
                role_name=role.name,
                created_at=user.created_at,
            ),
            temporary_password=temporary_password,
        )
