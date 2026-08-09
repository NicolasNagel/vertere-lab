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
    service_level: str
    exam_category: str
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
    on_call_fee_total: Decimal
    grand_total: Decimal
    eligible_items: list[ClosurePreviewItemRead]
    blocked_items: list[ClosurePreviewBlockedItemRead]
    generated_at: datetime


class CloseMonthlyPeriodRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinic_id: UUID
    period_start: date
    period_end: date


class ReopenMonthlyClosureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=10, max_length=1000)


class FinancialAdjustmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monthly_closure_item_id: UUID | None = None
    kind: str = Field(pattern="^(CREDIT|DEBIT)$")
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    reason: str = Field(min_length=10, max_length=1000)


class FinancialAdjustmentRead(BaseModel):
    id: UUID
    monthly_closure_id: UUID
    monthly_closure_item_id: UUID | None
    kind: str
    amount: Decimal
    reason: str
    created_by: UUID | None
    created_at: datetime


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
    service_level: str | None = None
    exam_category: str | None = None


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
    on_call_fee_total: Decimal
    grand_total: Decimal
    generated_by: UUID | None
    closed_by: UUID | None
    generated_at: datetime
    closed_at: datetime
    reopened_at: datetime | None
    version: int
    items: list[MonthlyClosureItemRead]
    adjustments: list[FinancialAdjustmentRead] = Field(default_factory=list)


class MonthlyClosureSummaryRead(BaseModel):
    """List view — no `items` — response contém só o campo que a tela usa
    (`.claude/rules/12-attendance.md`, mesmo princípio aplicado aqui)."""

    id: UUID
    clinic_id: UUID
    competence_year: int
    competence_month: int
    period_start: date
    period_end: date
    status: Literal["CLOSED", "REOPENED"]
    item_count: int
    grand_total: Decimal
    closed_by: UUID | None
    closed_at: datetime
    version: int


class MonthlyClosureListResponse(BaseModel):
    items: list[MonthlyClosureSummaryRead]
    total: int
    page: int
    page_size: int
