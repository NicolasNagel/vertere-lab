"""Pydantic schemas for the veterinarians API — create/update/read/filter
kept separate; never the SQLAlchemy model (rule: .claude/rules/02-backend.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

VeterinarianStatusLiteral = Literal["ACTIVE", "INACTIVE"]


class VeterinarianRead(BaseModel):
    id: UUID
    name: str
    crmv: str
    phone: str | None
    email: str | None
    is_autonomous: bool
    status: VeterinarianStatusLiteral
    notes: str | None
    created_at: datetime
    updated_at: datetime
    row_version: int


class VeterinarianListResponse(BaseModel):
    items: list[VeterinarianRead]
    total: int
    page: int
    page_size: int


class VeterinarianLinkedClinic(BaseModel):
    clinic_id: UUID
    clinic_name: str
    primary_clinic: bool


class VeterinarianDetailRead(VeterinarianRead):
    clinics: list[VeterinarianLinkedClinic]


class VeterinarianLinkClinicRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinic_id: UUID
    primary: bool = False


class VeterinarianCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    crmv: str = Field(min_length=1)
    phone: str | None = None
    email: str | None = None
    is_autonomous: bool = False
    notes: str | None = None
    clinic_ids: list[UUID] = Field(default_factory=list)
    primary_clinic_id: UUID | None = None


class VeterinarianUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    crmv: str = Field(min_length=1)
    phone: str | None = None
    email: str | None = None
    is_autonomous: bool = False
    status: VeterinarianStatusLiteral
    notes: str | None = None
    expected_row_version: int
