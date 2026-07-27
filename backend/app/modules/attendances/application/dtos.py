"""Application-layer DTOs — never ORM objects, never domain entities leaked
raw across the module boundary (rule: .claude/rules/backend.md)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class AttendanceDTO:
    id: UUID
    clinic_id: UUID
    veterinarian_id: UUID
    patient_id: UUID
    service_date: date | None
    notes: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    row_version: int
