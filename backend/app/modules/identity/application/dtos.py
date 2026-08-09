"""Application-layer DTOs — never ORM objects, never domain entities leaked
raw across the module boundary (rule: .claude/rules/02-backend.md)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.shared.application.authorization import ActorContext
from app.shared.application.dtos import PageDTO

__all__ = [
    "ActorContext",
    "AuthenticatedUserDTO",
    "PageDTO",
    "PermissionDTO",
    "RoleDTO",
    "SessionIssuedDTO",
    "UserCreatedDTO",
    "UserSummaryDTO",
]

AuthenticatedUserDTO = ActorContext


@dataclass(frozen=True, kw_only=True)
class SessionIssuedDTO:
    token: str
    expires_at: datetime
    user: ActorContext


@dataclass(frozen=True, kw_only=True)
class UserSummaryDTO:
    id: UUID
    email: str
    full_name: str
    is_active: bool
    role_id: UUID
    role_name: str
    role_scope: str = "LAB"
    clinic_ids: frozenset[UUID] = frozenset()
    row_version: int = 1
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
    master_only: bool
