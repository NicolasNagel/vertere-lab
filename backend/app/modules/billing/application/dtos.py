"""Application-layer DTOs — never ORM objects, never domain entities leaked
raw across the module boundary (rule: .claude/rules/02-backend.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class ClosurePreviewItemDTO:
    attendance_id: UUID
    attendance_exam_id: UUID
    protocol_number: str | None
    patient_name: str
    exam_name: str
    total_amount: Decimal


@dataclass(frozen=True, kw_only=True)
class ClosurePreviewBlockedItemDTO:
    attendance_id: UUID
    attendance_exam_id: UUID
    protocol_number: str | None
    patient_name: str
    exam_name: str
    total_amount: Decimal
    reason: str


@dataclass(frozen=True, kw_only=True)
class ClosurePreviewDTO:
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
    eligible_items: list[ClosurePreviewItemDTO] = field(default_factory=list)
    blocked_items: list[ClosurePreviewBlockedItemDTO] = field(default_factory=list)
    generated_at: datetime


@dataclass(frozen=True, kw_only=True)
class MonthlyClosureItemDTO:
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


@dataclass(frozen=True, kw_only=True)
class MonthlyClosureDTO:
    id: UUID
    clinic_id: UUID
    competence_year: int
    competence_month: int
    period_start: date
    period_end: date
    status: str
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
    items: list[MonthlyClosureItemDTO] = field(default_factory=list)
