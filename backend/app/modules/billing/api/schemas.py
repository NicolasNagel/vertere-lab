"""Pydantic schemas for the billing API — never the SQLAlchemy model
(rule: .claude/rules/backend.md)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


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
