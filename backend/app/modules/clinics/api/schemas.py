"""Pydantic schemas for the clinics API — create/update/read/filter kept
separate; never the SQLAlchemy model (rule: .claude/rules/backend.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ClinicStatusLiteral = Literal["ACTIVE", "INACTIVE", "DELINQUENT", "SPECIAL"]


class ClinicRead(BaseModel):
    id: UUID
    name: str
    tax_id: str | None
    phone: str | None
    email: str | None
    status: ClinicStatusLiteral
    address_zip_code: str | None
    address_street: str | None
    address_number: str | None
    address_neighborhood: str | None
    address_city: str | None
    address_state: str | None
    address_complement: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    row_version: int


class ClinicListResponse(BaseModel):
    items: list[ClinicRead]
    total: int
    page: int
    page_size: int


class ClinicCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    tax_id: str | None = None
    phone: str | None = None
    email: str | None = None
    address_zip_code: str | None = None
    address_street: str | None = None
    address_number: str | None = None
    address_neighborhood: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_complement: str | None = None
    notes: str | None = None


class ClinicUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    tax_id: str | None = None
    phone: str | None = None
    email: str | None = None
    status: ClinicStatusLiteral
    address_zip_code: str | None = None
    address_street: str | None = None
    address_number: str | None = None
    address_neighborhood: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_complement: str | None = None
    notes: str | None = None
    expected_row_version: int
