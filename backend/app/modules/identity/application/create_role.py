from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.identity.application.dtos import RoleDTO
from app.modules.identity.domain.constants import MASTER_ONLY_PERMISSIONS
from app.modules.identity.domain.entities import Role, RoleScope
from app.modules.identity.domain.errors import RoleNameAlreadyExistsError
from app.modules.identity.domain.repositories import PermissionRepository, RoleRepository
from app.shared.application.authorization import ActorContext
from app.shared.domain.errors import ForbiddenError, ValidationError

_REQUIRED_PERMISSION = "roles.manage"


@dataclass(frozen=True, kw_only=True)
class CreateRoleCommand:
    actor: ActorContext
    name: str
    scope: RoleScope
    description: str
    permission_codes: frozenset[str]


class CreateRoleUseCase:
    def __init__(
        self,
        *,
        roles: RoleRepository,
        permissions: PermissionRepository,
        audit: AuditLogWriter,
    ) -> None:
        self._roles = roles
        self._permissions = permissions
        self._audit = audit

    def execute(self, command: CreateRoleCommand) -> RoleDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")
        if command.actor.clinic_filter is not None:
            raise ForbiddenError("Perfis de acesso são geridos apenas pelo laboratório.")

        if self._roles.get_by_name(command.name) is not None:
            raise RoleNameAlreadyExistsError("Nome de perfil já existe.")

        if not self._permissions.all_codes_exist(command.permission_codes):
            raise ValidationError("Uma ou mais permissões informadas não existem.")

        if command.scope != RoleScope.GLOBAL and command.permission_codes & MASTER_ONLY_PERMISSIONS:
            raise ValidationError(
                "Uma ou mais permissões informadas são exclusivas do perfil Master."
            )

        role = Role(
            id=uuid4(),
            name=command.name,
            scope=command.scope,
            description=command.description,
            is_system=False,
            permission_codes=command.permission_codes,
        )
        self._roles.add(role)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="roles.created",
                entity_type="role",
                entity_id=str(role.id),
                after_state={"name": role.name, "permissions": sorted(role.permission_codes)},
            )
        )

        return RoleDTO(
            id=role.id,
            name=role.name,
            scope=role.scope.value,
            description=role.description,
            is_system=role.is_system,
            permissions=role.permission_codes,
            row_version=role.row_version,
        )
