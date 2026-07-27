from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.identity.application.dtos import AuthenticatedUserDTO, RoleDTO
from app.modules.identity.domain.constants import CONTROL_PERMISSIONS
from app.modules.identity.domain.errors import SelfLockoutError
from app.modules.identity.domain.repositories import (
    PermissionRepository,
    RoleRepository,
    UserRepository,
)
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError

_REQUIRED_PERMISSION = "roles.manage"


@dataclass(frozen=True, kw_only=True)
class UpdateRolePermissionsCommand:
    actor: AuthenticatedUserDTO
    role_id: UUID
    permission_codes: frozenset[str]
    expected_row_version: int


class UpdateRolePermissionsUseCase:
    def __init__(
        self,
        *,
        roles: RoleRepository,
        permissions: PermissionRepository,
        users: UserRepository,
        audit: AuditLogWriter,
    ) -> None:
        self._roles = roles
        self._permissions = permissions
        self._users = users
        self._audit = audit

    def execute(self, command: UpdateRolePermissionsCommand) -> RoleDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        role = self._roles.get_by_id(command.role_id)
        if role is None:
            raise NotFoundError("Papel não encontrado.")

        if not self._permissions.all_codes_exist(command.permission_codes):
            raise ValidationError("Uma ou mais permissões informadas não existem.")

        # Editar um papel afeta *todo mundo* que o tem, não só quem está
        # editando — ao contrário de `assign_role`/`deactivate_user`
        # (autoexclusão individual), aqui a checagem é organizacional: essa
        # mudança pode deixar zero pessoas ativas com a permissão, mesmo que
        # o ator não seja dono do papel. Achado em teste manual adversarial
        # (ADR-007): remover `roles.manage` do próprio papel do único admin
        # sucedia sem aviso e travava o sistema sem caminho de volta pela UI.
        removed_control_permissions = CONTROL_PERMISSIONS & (
            role.permission_codes - command.permission_codes
        )
        for permission_code in removed_control_permissions:
            remaining = self._users.count_active_users_with_permission(
                permission_code, exclude_role_id=role.id
            )
            if remaining == 0:
                raise SelfLockoutError(
                    "Esta alteração removeria o último usuário capaz de gerenciar "
                    "usuários ou permissões."
                )

        before_permissions = sorted(role.permission_codes)
        updated = self._roles.replace_permissions(
            role.id, command.permission_codes, expected_row_version=command.expected_row_version
        )
        if not updated:
            raise ConflictError(
                "Este perfil foi alterado por outra pessoa. Recarregue e tente de novo."
            )

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="roles.permissions_updated",
                entity_type="role",
                entity_id=str(role.id),
                before_state={"permissions": before_permissions},
                after_state={"permissions": sorted(command.permission_codes)},
            )
        )

        updated_role = self._roles.get_by_id(role.id)
        if updated_role is None:
            raise RuntimeError(f"Papel {role.id} desapareceu durante a atualização.")

        return RoleDTO(
            id=updated_role.id,
            name=updated_role.name,
            scope=updated_role.scope.value,
            description=updated_role.description,
            is_system=updated_role.is_system,
            permissions=updated_role.permission_codes,
            row_version=updated_role.row_version,
        )
