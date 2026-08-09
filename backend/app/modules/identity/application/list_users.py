from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.identity.application.dtos import PageDTO, UserSummaryDTO
from app.modules.identity.domain.repositories import (
    ClinicMembershipRepository,
    RoleRepository,
    UserRepository,
)
from app.shared.application.authorization import ActorContext
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "users.read"


@dataclass(frozen=True, kw_only=True)
class ListUsersQuery:
    actor: ActorContext
    page: int
    page_size: int
    is_active: bool | None = None
    search: str | None = None


class ListUsersUseCase:
    def __init__(
        self,
        *,
        users: UserRepository,
        roles: RoleRepository,
        clinic_memberships: ClinicMembershipRepository,
    ) -> None:
        self._users = users
        self._roles = roles
        self._clinic_memberships = clinic_memberships

    def execute(self, query: ListUsersQuery) -> PageDTO[UserSummaryDTO]:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        users, total = self._users.list_page(
            page=query.page,
            page_size=query.page_size,
            is_active=query.is_active,
            search=query.search,
        )

        roles_by_id: dict[UUID, tuple[str, str]] = {}
        for user in users:
            if user.role_id not in roles_by_id:
                role = self._roles.get_by_id(user.role_id)
                roles_by_id[user.role_id] = (
                    (role.name, role.scope.value) if role is not None else ("", "LAB")
                )

        items = [
            UserSummaryDTO(
                id=user.id,
                email=str(user.email),
                full_name=user.full_name,
                is_active=user.is_active,
                role_id=user.role_id,
                role_name=roles_by_id[user.role_id][0],
                role_scope=roles_by_id[user.role_id][1],
                clinic_ids=self._clinic_memberships.list_active_clinic_ids_for_user(user.id),
                row_version=user.row_version,
                created_at=user.created_at,
            )
            for user in users
        ]
        return PageDTO(items=items, total=total, page=query.page, page_size=query.page_size)
