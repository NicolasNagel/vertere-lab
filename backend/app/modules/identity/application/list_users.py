from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.identity.application.dtos import AuthenticatedUserDTO, PageDTO, UserSummaryDTO
from app.modules.identity.domain.repositories import RoleRepository, UserRepository
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "users.read"


@dataclass(frozen=True, kw_only=True)
class ListUsersQuery:
    actor: AuthenticatedUserDTO
    page: int
    page_size: int
    is_active: bool | None = None
    search: str | None = None


class ListUsersUseCase:
    def __init__(self, *, users: UserRepository, roles: RoleRepository) -> None:
        self._users = users
        self._roles = roles

    def execute(self, query: ListUsersQuery) -> PageDTO[UserSummaryDTO]:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        users, total = self._users.list_page(
            page=query.page,
            page_size=query.page_size,
            is_active=query.is_active,
            search=query.search,
        )

        role_names: dict[UUID, str] = {}
        for user in users:
            if user.role_id not in role_names:
                role = self._roles.get_by_id(user.role_id)
                role_names[user.role_id] = role.name if role is not None else ""

        items = [
            UserSummaryDTO(
                id=user.id,
                email=str(user.email),
                full_name=user.full_name,
                is_active=user.is_active,
                role_id=user.role_id,
                role_name=role_names[user.role_id],
                created_at=user.created_at,
            )
            for user in users
        ]
        return PageDTO(items=items, total=total, page=query.page, page_size=query.page_size)
