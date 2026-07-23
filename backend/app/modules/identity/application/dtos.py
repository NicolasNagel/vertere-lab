"""Application-layer DTOs — never ORM objects, never domain entities leaked
raw across the module boundary (rule: .claude/rules/backend.md)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class AuthenticatedUserDTO:
    id: UUID
    email: str
    full_name: str
    role_id: UUID
    role_name: str
    permissions: frozenset[str]


@dataclass(frozen=True, kw_only=True)
class SessionIssuedDTO:
    token: str
    expires_at: datetime
    user: AuthenticatedUserDTO


@dataclass(frozen=True, kw_only=True)
class UserSummaryDTO:
    id: UUID
    email: str
    full_name: str
    is_active: bool
    role_id: UUID
    role_name: str
    created_at: datetime


@dataclass(frozen=True, kw_only=True)
class UserCreatedDTO:
    user: UserSummaryDTO
    temporary_password: str


@dataclass(frozen=True, kw_only=True)
class RoleDTO:
    id: UUID
    name: str
    scope: str
    description: str
    is_system: bool
    permissions: frozenset[str]
    row_version: int


@dataclass(frozen=True, kw_only=True)
class PermissionDTO:
    id: UUID
    code: str
    description: str


@dataclass(frozen=True, kw_only=True)
class PageDTO[T]:
    items: list[T]
    total: int
    page: int
    page_size: int
