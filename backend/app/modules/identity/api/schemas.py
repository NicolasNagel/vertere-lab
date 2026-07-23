"""Pydantic schemas for the identity API — create/update/read/filter kept
separate; never the SQLAlchemy model (rule: .claude/rules/backend.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login: str = Field(min_length=1)
    password: str = Field(min_length=1)
    remember_me: bool = False


class UserPublicRead(BaseModel):
    id: UUID
    email: str
    full_name: str
    role_id: UUID
    role_name: str


class AuthResponse(BaseModel):
    user: UserPublicRead
    permissions: list[str]


class UserListItemRead(BaseModel):
    id: UUID
    email: str
    full_name: str
    is_active: bool
    role_id: UUID
    role_name: str
    created_at: datetime


class UserListResponse(BaseModel):
    items: list[UserListItemRead]
    total: int
    page: int
    page_size: int


class UserCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    full_name: str = Field(min_length=1)
    role_id: UUID


class UserCreateResponse(BaseModel):
    user: UserListItemRead
    temporary_password: str


class AssignRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_id: UUID


class RoleRead(BaseModel):
    id: UUID
    name: str
    scope: Literal["GLOBAL", "LAB", "CLINIC"]
    description: str
    is_system: bool
    permissions: list[str]
    row_version: int


class RoleListResponse(BaseModel):
    items: list[RoleRead]
    total: int
    page: int
    page_size: int


class RoleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    scope: Literal["GLOBAL", "LAB", "CLINIC"]
    description: str = ""
    permissions: list[str] = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permissions: list[str]
    expected_row_version: int


class PermissionRead(BaseModel):
    id: UUID
    code: str
    description: str
