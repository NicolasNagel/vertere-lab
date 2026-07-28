"""Pydantic schemas for the attendances API — create/update/read kept
separate; never the SQLAlchemy model (rule: .claude/rules/backend.md)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

AttendanceStatusLiteral = Literal[
    "DRAFT", "CONFIRMED", "IN_PROGRESS", "COMPLETED", "CANCELLED", "ON_HOLD"
]
AttendanceExamStatusLiteral = Literal["ACTIVE", "CANCELLED"]


class AttendanceExamRead(BaseModel):
    id: UUID
    exam_id: UUID
    exam_code: str
    exam_name: str
    price_base: Decimal
    quantity: int
    discount_amount: Decimal
    surcharge_amount: Decimal
    total_amount: Decimal
    override_reason: str | None
    status: AttendanceExamStatusLiteral


class AttendanceRead(BaseModel):
    id: UUID
    clinic_id: UUID
    veterinarian_id: UUID
    patient_id: UUID
    service_date: date | None
    notes: str | None
    status: AttendanceStatusLiteral
    items: list[AttendanceExamRead]
    billing_competence: date | None
    subtotal: Decimal
    discount_total: Decimal
    surcharge_total: Decimal
    grand_total: Decimal
    protocol_number: str | None
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


class AttendanceConfirmItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam_id: UUID
    quantity: int = 1
    discount_amount: Decimal | None = None
    override_reason: str | None = None


class AttendanceConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AttendanceConfirmItemRequest]
