"""Application-layer DTOs — never ORM objects, never domain entities leaked
raw across the module boundary (rule: .claude/rules/02-backend.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class AttendanceExamDTO:
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
    status: str


@dataclass(frozen=True, kw_only=True)
class AttendancePreviewDTO:
    """Dry-run projection — deliberately has no `id`/`protocol_number`/
    `row_version`: nothing is persisted, so there is no attendance-exam
    identity or protocol yet (`preview_attendance.py`)."""

    attendance_id: UUID
    clinic_id: UUID
    veterinarian_id: UUID
    patient_id: UUID
    collection_method: str
    service_level: str
    service_date: date
    items: list[AttendanceExamDTO]
    subtotal: Decimal
    discount_total: Decimal
    surcharge_total: Decimal
    on_call_fee: Decimal
    grand_total: Decimal


@dataclass(frozen=True, kw_only=True)
class AttendanceDTO:
    id: UUID
    clinic_id: UUID
    veterinarian_id: UUID
    patient_id: UUID
    collection_method: str
    service_level: str
    service_date: date | None
    notes: str | None
    status: str
    items: list[AttendanceExamDTO] = field(default_factory=list)
    billing_competence: date | None = None
    subtotal: Decimal = Decimal("0")
    discount_total: Decimal = Decimal("0")
    surcharge_total: Decimal = Decimal("0")
    on_call_fee: Decimal = Decimal("0")
    grand_total: Decimal = Decimal("0")
    protocol_number: str | None = None
    cancel_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    row_version: int
