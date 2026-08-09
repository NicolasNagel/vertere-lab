from __future__ import annotations

import secrets
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.identity.application.dtos import UserCreatedDTO, UserSummaryDTO
from app.modules.identity.application.password_hasher import PasswordHasher
from app.modules.identity.domain.entities import ClinicMembership, LabMembership, RoleScope, User
from app.modules.identity.domain.errors import EmailAlreadyExistsError
from app.modules.identity.domain.repositories import (
    ClinicMembershipRepository,
    LabMembershipRepository,
    RoleRepository,
    UserRepository,
)
from app.modules.identity.domain.value_objects import Email
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError, ValidationError

_REQUIRED_PERMISSION = "users.create"
_TEMPORARY_PASSWORD_BYTES = 12


@dataclass(frozen=True, kw_only=True)
class CreateUserCommand:
    actor: ActorContext
    email: str
    full_name: str
    role_id: UUID
    clinic_ids: frozenset[UUID]


class CreateUserUseCase:
    def __init__(
        self,
        *,
        users: UserRepository,
        roles: RoleRepository,
        memberships: LabMembershipRepository,
        clinic_memberships: ClinicMembershipRepository,
        password_hasher: PasswordHasher,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._users = users
        self._roles = roles
        self._memberships = memberships
        self._clinic_memberships = clinic_memberships
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
        if role.scope is RoleScope.CLINIC and not command.clinic_ids:
            raise ValidationError("Papel de clínica exige ao menos uma clínica.")
        if not self._clinic_memberships.all_clinic_ids_exist(command.clinic_ids):
            raise NotFoundError("Clínica não encontrada.")
        if role.scope is not RoleScope.CLINIC and command.clinic_ids:
            raise ValidationError("Papel de laboratório/global não aceita clínicas específicas.")
        if command.actor.role_scope == "CLINIC" and (
            role.scope is not RoleScope.CLINIC or not command.clinic_ids <= command.actor.clinic_ids
        ):
            raise ForbiddenError("Não é permitido conceder acesso fora do próprio escopo.")

        now = self._clock.now()
        temporary_password = secrets.token_urlsafe(_TEMPORARY_PASSWORD_BYTES)
        user = User(
            id=uuid4(),
            email=email,
            full_name=command.full_name,
            password_hash=self._password_hasher.hash(temporary_password),
            is_active=True,
            role_id=role.id,
            created_by=command.actor.user_id,
            created_at=now,
            updated_at=now,
        )
        self._users.add(user)
        if role.scope is RoleScope.CLINIC:
            for clinic_id in command.clinic_ids:
                self._clinic_memberships.add(
                    ClinicMembership(
                        id=uuid4(),
                        user_id=user.id,
                        clinic_id=clinic_id,
                        granted_at=now,
                        granted_by=command.actor.user_id,
                    )
                )
        else:
            self._memberships.add(
                LabMembership(
                    id=uuid4(),
                    user_id=user.id,
                    granted_at=now,
                    granted_by=command.actor.user_id,
                )
            )
        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.user_id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="users.created",
                entity_type="user",
                entity_id=str(user.id),
                after_state={
                    "email": str(email),
                    "role_id": str(role.id),
                    "clinic_ids": sorted(map(str, command.clinic_ids)),
                },
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
                role_scope=role.scope.value,
                clinic_ids=command.clinic_ids,
                row_version=user.row_version,
                created_at=user.created_at,
            ),
            temporary_password=temporary_password,
        )
