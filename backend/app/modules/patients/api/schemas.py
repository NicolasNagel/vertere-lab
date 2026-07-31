"""Pydantic schemas for the patients API — create/update/read/filter kept
separate; never the SQLAlchemy model (rule: .claude/rules/02-backend.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PatientSexLiteral = Literal["MALE", "FEMALE"]
PatientStatusLiteral = Literal["ACTIVE", "INACTIVE"]


class SpeciesRead(BaseModel):
    id: UUID
    name: str
    created_at: datetime


class SpeciesListResponse(BaseModel):
    items: list[SpeciesRead]


class PatientRead(BaseModel):
    id: UUID
    name: str
    species_id: UUID
    sex: PatientSexLiteral
    breed: str | None
    age_description: str | None
    owner_name: str
    owner_phone: str | None
    owner_document: str | None
    status: PatientStatusLiteral
    notes: str | None
    created_at: datetime
    updated_at: datetime
    row_version: int


class PatientListResponse(BaseModel):
    items: list[PatientRead]
    total: int
    page: int
    page_size: int


class PatientCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    species_id: UUID
    sex: PatientSexLiteral
    breed: str | None = None
    age_description: str | None = None
    owner_name: str = Field(min_length=1)
    owner_phone: str | None = None
    owner_document: str | None = None
    notes: str | None = None


class PatientUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    species_id: UUID
    sex: PatientSexLiteral
    breed: str | None = None
    age_description: str | None = None
    owner_name: str = Field(min_length=1)
    owner_phone: str | None = None
    owner_document: str | None = None
    status: PatientStatusLiteral
    notes: str | None = None
    expected_row_version: int
