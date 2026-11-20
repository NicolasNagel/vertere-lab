"""Application-layer DTOs — never ORM objects, never domain entities leaked
raw across the module boundary (rule: .claude/rules/02-backend.md)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class SpeciesDTO:
    id: UUID
    name: str
    created_at: datetime


@dataclass(frozen=True, kw_only=True)
class PatientsSummaryDTO:
    total: int
    active: int
    inactive: int


@dataclass(frozen=True, kw_only=True)
class PatientDTO:
    id: UUID
    clinic_id: UUID | None
    name: str
    species_id: UUID
    sex: str
    breed: str | None
    age_description: str | None
    owner_name: str
    owner_phone: str | None
    owner_document: str | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
    row_version: int
    age_value: int | None = None
    age_unit: str | None = None
    age_recorded_on: date | None = None
