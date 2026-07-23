"""Repository protocols for the identity module.

Interfaces live in `domain` (per .claude/rules/backend.md); implementations
live in `infrastructure`. Repositories never commit — the unit of work does.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.identity.domain.entities import LabMembership, Permission, Role, Session, User


class UserRepository(Protocol):
    def get_by_id(self, user_id: UUID) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def add(self, user: User) -> None: ...

    def save(self, user: User) -> None: ...

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        is_active: bool | None,
        search: str | None,
    ) -> tuple[list[User], int]: ...

    def count_active_users_with_permission(
        self, permission_code: str, *, exclude_user_id: UUID | None = None
    ) -> int: ...


class RoleRepository(Protocol):
    def get_by_id(self, role_id: UUID) -> Role | None: ...

    def get_by_name(self, name: str) -> Role | None: ...

    def add(self, role: Role) -> None: ...

    def replace_permissions(self, role_id: UUID, permission_codes: frozenset[str]) -> None: ...

    def list_page(self, *, page: int, page_size: int) -> tuple[list[Role], int]: ...


class PermissionRepository(Protocol):
    def list_all(self) -> list[Permission]: ...

    def all_codes_exist(self, codes: frozenset[str]) -> bool: ...


class SessionRepository(Protocol):
    def add(self, session: Session) -> None: ...

    def get_by_token_hash(self, token_hash: str) -> Session | None: ...

    def save(self, session: Session) -> None: ...

    def revoke_all_for_user(self, user_id: UUID, *, now: datetime) -> None: ...


class LabMembershipRepository(Protocol):
    def add(self, membership: LabMembership) -> None: ...
