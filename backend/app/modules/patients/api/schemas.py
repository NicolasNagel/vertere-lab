"""Pydantic schemas for the patients API — create/update/read/filter kept
separate; never the SQLAlchemy model (rule: .claude/rules/02-backend.md)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

PatientSexLiteral = Literal["MALE", "FEMALE"]
PatientStatusLiteral = Literal["ACTIVE", "INACTIVE"]
AgeUnitLiteral = Literal["YEARS", "MONTHS"]

# Same convention as the clinics API: trim, reject whitespace-only, and bound every free-text field.
PatientName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
OwnerName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
PatientShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
PatientContact = Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)]
PatientNotes = Annotated[str, StringConstraints(max_length=2000)]
ChangeReason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


def _require_age_pair(age_value: int | None, age_unit: str | None) -> None:
    if (age_value is None) != (age_unit is None):
        raise ValueError("Informe o valor e a unidade da idade juntos (anos ou meses).")


class SpeciesRead(BaseModel):
    id: UUID
    name: str
    created_at: datetime


class SpeciesListResponse(BaseModel):
    items: list[SpeciesRead]


class PatientRead(BaseModel):
    id: UUID
    clinic_id: UUID | None
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
    age_value: int | None
    age_unit: AgeUnitLiteral | None
    age_recorded_on: date | None


class PatientsSummaryRead(BaseModel):
    total: int
    active: int
    inactive: int


class PatientListResponse(BaseModel):
    items: list[PatientRead]
    total: int
    page: int
    page_size: int


class PatientCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinic_id: UUID
    name: PatientName
    species_id: UUID
    sex: PatientSexLiteral
    breed: PatientShortText | None = None
    age_description: PatientShortText | None = None
    owner_name: OwnerName
    owner_phone: PatientContact | None = None
    owner_document: PatientContact | None = None
    notes: PatientNotes | None = None
    age_value: int | None = Field(default=None, ge=0)
    age_unit: AgeUnitLiteral | None = None

    @model_validator(mode="after")
    def _age_pair(self) -> Self:
        _require_age_pair(self.age_value, self.age_unit)
        return self


class PatientUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: PatientName
    species_id: UUID
    sex: PatientSexLiteral
    breed: PatientShortText | None = None
    age_description: PatientShortText | None = None
    owner_name: OwnerName
    owner_phone: PatientContact | None = None
    owner_document: PatientContact | None = None
    status: PatientStatusLiteral
    notes: PatientNotes | None = None
    expected_row_version: int
    clinic_id: UUID | None = None
    age_value: int | None = Field(default=None, ge=0)
    age_unit: AgeUnitLiteral | None = None
    # Required when `clinic_id` moves the patient to another clinic (checked in the use case).
    reason: ChangeReason | None = None

    @model_validator(mode="after")
    def _age_pair(self) -> Self:
        _require_age_pair(self.age_value, self.age_unit)
        return self
