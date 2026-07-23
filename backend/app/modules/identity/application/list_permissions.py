from __future__ import annotations

from dataclasses import dataclass

from app.modules.identity.application.dtos import AuthenticatedUserDTO, PermissionDTO
from app.modules.identity.domain.repositories import PermissionRepository
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "permissions.read"


@dataclass(frozen=True, kw_only=True)
class ListPermissionsQuery:
    actor: AuthenticatedUserDTO


class ListPermissionsUseCase:
    def __init__(self, *, permissions: PermissionRepository) -> None:
        self._permissions = permissions

    def execute(self, query: ListPermissionsQuery) -> list[PermissionDTO]:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        return [
            PermissionDTO(
                id=permission.id, code=permission.code, description=permission.description
            )
            for permission in self._permissions.list_all()
        ]
