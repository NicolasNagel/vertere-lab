from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.identity.application.dtos import UserSummaryDTO
from app.modules.identity.application.user_scope import ensure_user_in_actor_scope
from app.modules.identity.domain.constants import CONTROL_PERMISSIONS
from app.modules.identity.domain.errors import SelfLockoutError
from app.modules.identity.domain.repositories import (
    ClinicMembershipRepository,
    RoleRepository,
    SessionRepository,
    UserRepository,
)
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "users.deactivate"


@dataclass(frozen=True, kw_only=True)
class DeactivateUserCommand:
    actor: ActorContext
    user_id: UUID


class DeactivateUserUseCase:
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

    def execute(self, command: DeactivateUserCommand) -> UserSummaryDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        user = self._users.get_by_id(command.user_id)
        if user is None:
            raise NotFoundError("Usuário não encontrado.")
        ensure_user_in_actor_scope(command.actor, user.id, self._clinic_memberships)

        if user.id == command.actor.id:
            role = self._roles.get_by_id(user.role_id)
            held_control_permissions = CONTROL_PERMISSIONS & (
                role.permission_codes if role is not None else frozenset()
            )
            for permission_code in held_control_permissions:
                remaining = self._users.count_active_users_with_permission(
                    permission_code, exclude_user_id=user.id
                )
                if remaining == 0:
                    raise SelfLockoutError(
                        "Esta ação removeria o último usuário capaz de gerenciar usuários."
                    )

        now = self._clock.now()
        user.deactivate(now=now)
        self._users.save(user)
        self._sessions.revoke_all_for_user(user.id, now=now)

        role = self._roles.get_by_id(user.role_id)
        role_name = role.name if role is not None else ""

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="users.deactivated",
                entity_type="user",
                entity_id=str(user.id),
                before_state={"is_active": True},
                after_state={"is_active": False},
            )
        )

        return UserSummaryDTO(
            id=user.id,
            email=str(user.email),
            full_name=user.full_name,
            is_active=user.is_active,
            role_id=user.role_id,
            role_name=role_name,
            row_version=user.row_version,
            created_at=user.created_at,
        )
