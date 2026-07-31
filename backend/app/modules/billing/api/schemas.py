"""Pydantic schemas for the billing API — never the SQLAlchemy model
(rule: .claude/rules/02-backend.md)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClosurePreviewItemRead(BaseModel):
    attendance_id: UUID
    attendance_exam_id: UUID
    protocol_number: str | None
    patient_name: str
    exam_name: str
    total_amount: Decimal


class ClosurePreviewBlockedItemRead(BaseModel):
    attendance_id: UUID
    attendance_exam_id: UUID
    protocol_number: str | None
    patient_name: str
    exam_name: str
    total_amount: Decimal
    reason: str


class ClosurePreviewResponse(BaseModel):
    clinic_id: UUID
    competence_year: int
    competence_month: int
    period_start: date
    period_end: date
    attendance_count: int
    cancelled_attendance_count: int
    item_count: int
    subtotal: Decimal
    discount_total: Decimal
    surcharge_total: Decimal
    grand_total: Decimal
    eligible_items: list[ClosurePreviewItemRead]
    blocked_items: list[ClosurePreviewBlockedItemRead]
    generated_at: datetime


class CloseMonthlyPeriodRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinic_id: UUID
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


class MonthlyClosureItemRead(BaseModel):
    id: UUID
    attendance_id: UUID
    attendance_exam_id: UUID
    protocol_number: str | None
    patient_name: str
    exam_name: str
    price_base: Decimal
    quantity: int
    discount_amount: Decimal
    surcharge_amount: Decimal
    total_amount: Decimal


class MonthlyClosureRead(BaseModel):
    id: UUID
    clinic_id: UUID
    competence_year: int
    competence_month: int
    period_start: date
    period_end: date
    status: Literal["CLOSED", "REOPENED"]
    item_count: int
    subtotal: Decimal
    discount_total: Decimal
    surcharge_total: Decimal
    grand_total: Decimal
    generated_by: UUID | None
    closed_by: UUID | None
    generated_at: datetime
    closed_at: datetime
    reopened_at: datetime | None
    version: int
    items: list[MonthlyClosureItemRead]
