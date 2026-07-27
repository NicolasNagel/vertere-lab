"""In-memory fakes for the identity repository protocols — used by unit
tests for use cases (rule: mock only at an external boundary; a fake
repository backing a pure use-case test is not the repository-under-test,
so this is fine per .claude/rules/testing.md)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.audit.domain.entities import AuditEntry
from app.modules.identity.domain.entities import LabMembership, Permission, Role, Session, User


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: object) -> None:  # pragma: no cover - convenience only
        self._now = self._now + delta  # type: ignore[operator]


class FakePasswordHasher:
    """Not real hashing — deterministic prefix, fine for unit tests only."""

    def hash(self, plain_password: str) -> str:
        return f"hashed::{plain_password}"

    def verify(self, plain_password: str, password_hash: str) -> bool:
        return password_hash == f"hashed::{plain_password}"


class FakeSessionTokens:
    def __init__(self) -> None:
        self._counter = 0

    def generate(self) -> str:
        self._counter += 1
        return f"token-{self._counter}"

    def hash(self, token: str) -> str:
        return f"hash::{token}"


class FakeAuditLogWriter:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def record(self, entry: AuditEntry) -> None:
        self.entries.append(entry)


class FakeUserRepository:
    def __init__(self, *, roles: FakeRoleRepository | None = None) -> None:
        self._users: dict[UUID, User] = {}
        self._roles = roles

    def add(self, user: User) -> None:
        self._users[user.id] = user

    def save(self, user: User) -> None:
        self._users[user.id] = user

    def get_by_id(self, user_id: UUID) -> User | None:
        return self._users.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        for user in self._users.values():
            if str(user.email) == email:
                return user
        return None

    def list_page(
        self, *, page: int, page_size: int, is_active: bool | None, search: str | None
    ) -> tuple[list[User], int]:
        users = list(self._users.values())
        if is_active is not None:
            users = [u for u in users if u.is_active == is_active]
        return users, len(users)

    def count_active_users_with_permission(
        self,
        permission_code: str,
        *,
        exclude_user_id: UUID | None = None,
        exclude_role_id: UUID | None = None,
    ) -> int:
        if self._roles is None:
            raise RuntimeError("FakeUserRepository needs `roles` wired to resolve permissions.")
        count = 0
        for user in self._users.values():
            if exclude_user_id is not None and user.id == exclude_user_id:
                continue
            if exclude_role_id is not None and user.role_id == exclude_role_id:
                continue
            if not user.is_active:
                continue
            role = self._roles.get_by_id(user.role_id)
            if role is not None and permission_code in role.permission_codes:
                count += 1
        return count


class FakeRoleRepository:
    def __init__(self) -> None:
        self._roles: dict[UUID, Role] = {}

    def add(self, role: Role) -> None:
        self._roles[role.id] = role

    def get_by_id(self, role_id: UUID) -> Role | None:
        return self._roles.get(role_id)

    def get_by_name(self, name: str) -> Role | None:
        for role in self._roles.values():
            if role.name == name:
                return role
        return None

    def replace_permissions(
        self, role_id: UUID, permission_codes: frozenset[str], *, expected_row_version: int
    ) -> bool:
        role = self._roles[role_id]
        if role.row_version != expected_row_version:
            return False
        self._roles[role_id] = Role(
            id=role.id,
            name=role.name,
            scope=role.scope,
            description=role.description,
            is_system=role.is_system,
            permission_codes=permission_codes,
            row_version=role.row_version + 1,
        )
        return True

    def list_page(self, *, page: int, page_size: int) -> tuple[list[Role], int]:
        roles = list(self._roles.values())
        return roles, len(roles)


class FakePermissionRepository:
    def __init__(self, codes: frozenset[str] = frozenset()) -> None:
        self._codes = codes

    def list_all(self) -> list[Permission]:
        return [Permission(id=UUID(int=i), code=code) for i, code in enumerate(sorted(self._codes))]

    def all_codes_exist(self, codes: frozenset[str]) -> bool:
        return codes <= self._codes


class FakeSessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[UUID, Session] = {}

    def add(self, session: Session) -> None:
        self._sessions[session.id] = session

    def save(self, session: Session) -> None:
        self._sessions[session.id] = session

    def get_by_token_hash(self, token_hash: str) -> Session | None:
        for session in self._sessions.values():
            if session.token_hash == token_hash:
                return session
        return None

    def revoke_all_for_user(self, user_id: UUID, *, now: datetime) -> None:
        for session in self._sessions.values():
            if session.user_id == user_id and session.revoked_at is None:
                session.revoked_at = now


class FakeLabMembershipRepository:
    def __init__(self) -> None:
        self.memberships: list[LabMembership] = []

    def add(self, membership: LabMembership) -> None:
        self.memberships.append(membership)


class FakeLoginFailureRepository:
    def __init__(self) -> None:
        self._failures: list[tuple[str, datetime]] = []

    def record_failure(self, login: str, *, occurred_at: datetime) -> None:
        self._failures.append((login, occurred_at))

    def count_recent_failures(self, login: str, *, since: datetime) -> int:
        return sum(1 for stored_login, when in self._failures if stored_login == login and when >= since)

    def clear(self, login: str) -> None:
        self._failures = [item for item in self._failures if item[0] != login]
