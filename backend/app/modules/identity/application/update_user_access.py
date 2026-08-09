from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.identity.application.dtos import UserSummaryDTO
from app.modules.identity.domain.entities import RoleScope
from app.modules.identity.domain.repositories import (
    ClinicMembershipRepository,
    LabMembershipRepository,
    RoleRepository,
    SessionRepository,
    UserRepository,
)
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError

_REQUIRED_PERMISSION = "roles.assign"


@dataclass(frozen=True, kw_only=True)
class UpdateUserAccessCommand:
    actor: ActorContext
    user_id: UUID
    role_id: UUID
    clinic_ids: frozenset[UUID]
    expected_row_version: int


class UpdateUserAccessUseCase:
    def __init__(
        self,
        *,
        users: UserRepository,
        roles: RoleRepository,
        lab_memberships: LabMembershipRepository,
        clinic_memberships: ClinicMembershipRepository,
        sessions: SessionRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._users = users
        self._roles = roles
        self._lab_memberships = lab_memberships
        self._clinic_memberships = clinic_memberships
        self._sessions = sessions
        self._audit = audit
        self._clock = clock

    def execute(self, command: UpdateUserAccessCommand) -> UserSummaryDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        user = self._users.get_by_id(command.user_id)
        if user is None:
            raise NotFoundError("Usuário não encontrado.")
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

        old_clinic_ids = self._clinic_memberships.list_active_clinic_ids_for_user(user.id)
        now = self._clock.now()
        if not self._users.change_role_if_version(
            user.id, role.id, expected_row_version=command.expected_row_version, now=now
        ):
            raise ConflictError("O acesso do usuário foi alterado por outra operação.")

        clinic_scope = role.scope is RoleScope.CLINIC
        self._lab_memberships.set_active(
            user.id, active=not clinic_scope, now=now, granted_by=command.actor.user_id
        )
        self._clinic_memberships.replace_active_clinic_ids(
            user.id,
            command.clinic_ids if clinic_scope else frozenset(),
            now=now,
            granted_by=command.actor.user_id,
        )
        self._sessions.revoke_all_for_user(user.id, now=now)
        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.user_id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="users.access_changed",
                entity_type="user",
                entity_id=str(user.id),
                before_state={
                    "role_id": str(user.role_id),
                    "clinic_ids": sorted(map(str, old_clinic_ids)),
                },
                after_state={
                    "role_id": str(role.id),
                    "clinic_ids": sorted(map(str, command.clinic_ids)),
                },
            )
        )
        return UserSummaryDTO(
            id=user.id,
            email=str(user.email),
            full_name=user.full_name,
            is_active=user.is_active,
            role_id=role.id,
            role_name=role.name,
            role_scope=role.scope.value,
            clinic_ids=command.clinic_ids,
            row_version=command.expected_row_version + 1,
            created_at=user.created_at,
        )
