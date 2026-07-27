"""Pydantic schemas for the attendances API — create/read/filter kept
separate; never the SQLAlchemy model (rule: .claude/rules/backend.md)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

AttendanceStatusLiteral = Literal[
    "DRAFT", "CONFIRMED", "IN_PROGRESS", "COMPLETED", "CANCELLED", "ON_HOLD"
]


class AttendanceRead(BaseModel):
    id: UUID
    clinic_id: UUID
    veterinarian_id: UUID
    patient_id: UUID
    service_date: date | None
    notes: str | None
    status: AttendanceStatusLiteral
    created_at: datetime
    updated_at: datetime
    row_version: int


class AttendanceListResponse(BaseModel):
    items: list[AttendanceRead]
    total: int
    page: int
    page_size: int


class AttendanceDraftCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinic_id: UUID
    veterinarian_id: UUID
    patient_id: UUID
    service_date: date | None = None
    notes: str | None = None
