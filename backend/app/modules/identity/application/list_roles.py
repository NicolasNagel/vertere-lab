from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.identity.application.dtos import PageDTO, RoleDTO
from app.modules.identity.domain.entities import Role, RoleScope
from app.modules.identity.domain.repositories import RoleRepository
from app.shared.application.authorization import ActorContext
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "roles.read"


def _to_dto(role: Role) -> RoleDTO:
    return RoleDTO(
        id=role.id,
        name=role.name,
        scope=role.scope.value,
        description=role.description,
        is_system=role.is_system,
        permissions=role.permission_codes,
        row_version=role.row_version,
    )


@dataclass(frozen=True, kw_only=True)
class ListRolesQuery:
    actor: ActorContext
    page: int
    page_size: int


class ListRolesUseCase:
    def __init__(self, *, roles: RoleRepository) -> None:
        self._roles = roles

    def execute(self, query: ListRolesQuery) -> PageDTO[RoleDTO]:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        roles, total = self._roles.list_page(page=query.page, page_size=query.page_size)
        if query.actor.clinic_filter is not None:
            roles = [role for role in roles if role.scope is RoleScope.CLINIC]
            total = len(roles)
        items = [_to_dto(role) for role in roles]
        return PageDTO(items=items, total=total, page=query.page, page_size=query.page_size)


@dataclass(frozen=True, kw_only=True)
class GetRoleQuery:
    actor: ActorContext
    role_id: UUID


class GetRoleUseCase:
    def __init__(self, *, roles: RoleRepository) -> None:
        self._roles = roles

    def execute(self, query: GetRoleQuery) -> RoleDTO:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        role = self._roles.get_by_id(query.role_id)
        if role is None or (
            query.actor.clinic_filter is not None and role.scope is not RoleScope.CLINIC
        ):
            raise NotFoundError("Papel não encontrado.")
        return _to_dto(role)
