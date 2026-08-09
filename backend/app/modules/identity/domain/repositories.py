"""Repository protocols for the identity module.

Interfaces live in `domain` (per .claude/rules/02-backend.md); implementations
live in `infrastructure`. Repositories never commit — the unit of work does.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.identity.domain.entities import (
    ClinicMembership,
    LabMembership,
    Permission,
    Role,
    Session,
    User,
)


class UserRepository(Protocol):
    def get_by_id(self, user_id: UUID) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def add(self, user: User) -> None: ...

    def save(self, user: User) -> None: ...

    def change_role_if_version(
        self, user_id: UUID, role_id: UUID, *, expected_row_version: int, now: datetime
    ) -> bool: ...

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        is_active: bool | None,
        search: str | None,
    ) -> tuple[list[User], int]: ...

    def count_active_users_with_permission(
        self,
        permission_code: str,
        *,
        exclude_user_id: UUID | None = None,
        exclude_role_id: UUID | None = None,
    ) -> int: ...


class RoleRepository(Protocol):
    def get_by_id(self, role_id: UUID) -> Role | None: ...

    def get_by_name(self, name: str) -> Role | None: ...

    def add(self, role: Role) -> None: ...

    def replace_permissions(
        self, role_id: UUID, permission_codes: frozenset[str], *, expected_row_version: int
    ) -> bool:
        """Atomically swaps the permission set and bumps `row_version`, but
        only if the stored `row_version` still equals `expected_row_version`.
        Returns False (no write happened) on mismatch — the caller raises
        `ConflictError`. Must be a single conditional UPDATE, not a
        read-then-write pair: two concurrent calls reading the same version
        first would otherwise both pass and silently drop one edit (rule:
        .claude/rules/03-database.md — "edição crítica usa versão... conflito
        retorna 409")."""
        ...

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

    def get_active_by_user_id(self, user_id: UUID) -> LabMembership | None: ...

    def set_active(
        self, user_id: UUID, *, active: bool, now: datetime, granted_by: UUID
    ) -> None: ...


class ClinicMembershipRepository(Protocol):
    def add(self, membership: ClinicMembership) -> None: ...

    def all_clinic_ids_exist(self, clinic_ids: frozenset[UUID]) -> bool: ...

    def list_active_clinic_ids_for_user(self, user_id: UUID) -> frozenset[UUID]: ...

    def get_active_by_user_and_clinic(
        self, user_id: UUID, clinic_id: UUID
    ) -> ClinicMembership | None: ...

    def replace_active_clinic_ids(
        self, user_id: UUID, clinic_ids: frozenset[UUID], *, now: datetime, granted_by: UUID
    ) -> None: ...


class LoginFailureRepository(Protocol):
    """Backs login rate limiting — deliberately PostgreSQL, not an in-memory
    counter or Redis: the app runs as stateless Vercel Functions with no
    process-local memory shared across invocations, and this project's
    default is "PostgreSQL é a única fonte de verdade" unless a measured
    case justifies Redis (rule: AGENTS.md)."""

    def record_failure(self, login: str, *, occurred_at: datetime) -> None: ...

    def count_recent_failures(self, login: str, *, since: datetime) -> int: ...

    def clear(self, login: str) -> None: ...
