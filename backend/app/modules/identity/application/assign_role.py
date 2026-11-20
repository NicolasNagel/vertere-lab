from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.identity.application.dtos import UserSummaryDTO
from app.modules.identity.application.user_scope import ensure_user_in_actor_scope
from app.modules.identity.domain.constants import CONTROL_PERMISSIONS
from app.modules.identity.domain.entities import RoleScope
from app.modules.identity.domain.errors import SelfLockoutError
from app.modules.identity.domain.repositories import (
    ClinicMembershipRepository,
    RoleRepository,
    SessionRepository,
    UserRepository,
)
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError, ValidationError

_REQUIRED_PERMISSION = "roles.assign"


@dataclass(frozen=True, kw_only=True)
class AssignRoleCommand:
    actor: ActorContext
    user_id: UUID
    new_role_id: UUID


class AssignRoleUseCase:
    def __init__(
        self,
        *,
        users: UserRepository,
        roles: RoleRepository,
        clinic_memberships: ClinicMembershipRepository,
        sessions: SessionRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._users = users
        self._roles = roles
        self._clinic_memberships = clinic_memberships
        self._sessions = sessions
        self._audit = audit
        self._clock = clock

    def execute(self, command: AssignRoleCommand) -> UserSummaryDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        if command.actor.clinic_filter is not None:
            raise ForbiddenError("Usuário de clínica não atribui papéis do laboratório.")

        user = self._users.get_by_id(command.user_id)
        if user is None:
            raise NotFoundError("Usuário não encontrado.")
        ensure_user_in_actor_scope(command.actor, user.id, self._clinic_memberships)

        new_role = self._roles.get_by_id(command.new_role_id)
        if new_role is None:
            raise NotFoundError("Papel não encontrado.")
        if new_role.scope is RoleScope.CLINIC:
            raise ValidationError("Use o endpoint de acesso para atribuir papel de clínica.")

        if user.id == command.actor.id:
            lost_control_permissions = CONTROL_PERMISSIONS - new_role.permission_codes
            for permission_code in lost_control_permissions:
                remaining = self._users.count_active_users_with_permission(
                    permission_code, exclude_user_id=user.id
                )
                if remaining == 0:
                    raise SelfLockoutError(
                        "Esta troca removeria o último usuário capaz de gerenciar usuários."
                    )

        old_role_id = user.role_id
        now = self._clock.now()
        user.change_role(new_role.id, now=now)
        self._users.save(user)
        self._sessions.revoke_all_for_user(user.id, now=now)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="users.role_changed",
                entity_type="user",
                entity_id=str(user.id),
                before_state={"role_id": str(old_role_id)},
                after_state={"role_id": str(new_role.id)},
            )
        )

        return UserSummaryDTO(
            id=user.id,
            email=str(user.email),
            full_name=user.full_name,
            is_active=user.is_active,
            role_id=new_role.id,
            role_name=new_role.name,
            role_scope=new_role.scope.value,
            clinic_ids=frozenset(),
            row_version=user.row_version,
            created_at=user.created_at,
        )
