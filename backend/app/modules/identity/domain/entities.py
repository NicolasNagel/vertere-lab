"""Identity domain entities.

No FastAPI/SQLAlchemy import here (rule: .claude/rules/globals.md — domain
layer). Mutation happens through named methods, never by callers poking at
fields directly, so invariants stay enforced in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from app.modules.identity.domain.value_objects import Email


class RoleScope(StrEnum):
    GLOBAL = "GLOBAL"
    LAB = "LAB"
    CLINIC = "CLINIC"


@dataclass(frozen=True, kw_only=True)
class Permission:
    id: UUID
    code: str
    description: str = ""


@dataclass(frozen=True, kw_only=True)
class Role:
    id: UUID
    name: str
    scope: RoleScope
    description: str = ""
    is_system: bool = False
    permission_codes: frozenset[str] = field(default_factory=frozenset)
    row_version: int = 1

    def has_permission(self, code: str) -> bool:
        return code in self.permission_codes


@dataclass(kw_only=True)
class User:
    id: UUID
    email: Email
    full_name: str
    password_hash: str
    is_active: bool = True
    role_id: UUID
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    row_version: int = 1

    def deactivate(self, *, now: datetime) -> None:
        if not self.is_active:
            return
        self.is_active = False
        self.updated_at = now

    def change_role(self, new_role_id: UUID, *, now: datetime) -> None:
        self.role_id = new_role_id
        self.updated_at = now


@dataclass(kw_only=True)
class LabMembership:
    id: UUID
    user_id: UUID
    is_active: bool = True
    granted_at: datetime
    granted_by: UUID | None = None
    revoked_at: datetime | None = None


@dataclass(kw_only=True)
class Session:
    id: UUID
    user_id: UUID
    token_hash: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    remember_me: bool = False
    ip_address: str | None = None
    user_agent: str | None = None

    def is_valid(self, *, now: datetime) -> bool:
        return self.revoked_at is None and self.expires_at > now

    def revoke(self, *, now: datetime) -> None:
        if self.revoked_at is not None:
            return
        self.revoked_at = now

    def renew(self, *, now: datetime, ttl: timedelta) -> None:
        self.last_seen_at = now
        self.expires_at = now + ttl
