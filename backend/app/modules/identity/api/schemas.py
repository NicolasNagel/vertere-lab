"""Pydantic schemas for the identity API — create/update/read/filter kept
separate; never the SQLAlchemy model (rule: .claude/rules/02-backend.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Sem limite superior, um payload arbitrariamente grande vira trabalho de
    # hash Argon2 sobre lixo antes mesmo de rejeitar a credencial — DoS
    # barato (rule: .claude/rules/06-auth-security-lgpd.md, "limite de tamanho
    # de payload"). 254 é o teto de e-mail do RFC 5321; 200 já é generoso
    # para qualquer senha real.
    login: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=200)
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
    full_name: str = Field(min_length=1, max_length=200)
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

    name: str = Field(min_length=1, max_length=100)
    scope: Literal["GLOBAL", "LAB", "CLINIC"]
    description: str = Field(default="", max_length=1000)
    # max_length no limite da lista, não só no texto de cada item: sem isso,
    # um array com milhões de códigos-lixo ainda chega inteiro até a query
    # `all_codes_exist` (rule: .claude/rules/06-auth-security-lgpd.md, "limite
    # de tamanho de payload"). O catálogo real tem ~30 códigos; 200 sobra
    # margem sem ser ilimitado.
    permissions: list[str] = Field(default_factory=list, max_length=200)


class RoleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permissions: list[str] = Field(max_length=200)
    expected_row_version: int


class PermissionRead(BaseModel):
    id: UUID
    code: str
    description: str
    master_only: bool
