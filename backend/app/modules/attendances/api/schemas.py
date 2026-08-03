"""Pydantic schemas for the attendances API — create/update/read kept
separate; never the SQLAlchemy model (rule: .claude/rules/02-backend.md)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AttendanceStatusLiteral = Literal[
    "DRAFT", "CONFIRMED", "IN_PROGRESS", "COMPLETED", "CANCELLED", "ON_HOLD"
]
AttendanceExamStatusLiteral = Literal["ACTIVE", "CANCELLED"]
CollectionMethodLiteral = Literal["HELITO_NICOLAS", "INTERNAL", "MARLI", "COURIER", "UBER"]
ServiceLevelLiteral = Literal["NORMAL", "PLANTAO_NORMAL", "PLANTAO_ESPECIAL"]


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
    collection_method: CollectionMethodLiteral
    service_level: ServiceLevelLiteral
    service_date: date | None
    notes: str | None
    status: AttendanceStatusLiteral
    items: list[AttendanceExamRead]
    billing_competence: date | None
    subtotal: Decimal
    discount_total: Decimal
    surcharge_total: Decimal
    on_call_fee: Decimal
    grand_total: Decimal
    protocol_number: str | None
    cancel_reason: str | None
    created_at: datetime
    updated_at: datetime
    row_version: int


class AttendanceListResponse(BaseModel):
    items: list[AttendanceRead]
    total: int
    page: int
    page_size: int


class AttendanceStatusCountsResponse(BaseModel):
    total: int
    by_status: dict[str, int]


class AttendanceDraftCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinic_id: UUID
    veterinarian_id: UUID
    patient_id: UUID
    collection_method: CollectionMethodLiteral = "INTERNAL"
    service_level: ServiceLevelLiteral = "NORMAL"
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


class AttendanceCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class AttendanceUpdateRequest(BaseModel):
    """`row_version` is required — the client must say which version it is
    editing, so a stale edit gets a clean `409` instead of silently
    overwriting a change it never saw (`.claude/rules/05-frontend-web-mobile.md`).

    Every other field is optional and `None` means "not provided, leave
    unchanged" — including `notes`, which this slice has no way to clear
    back to empty via PATCH (send a non-null replacement instead); a
    deliberate simplification, documented in
    `application/update_attendance.py`.
    """

    model_config = ConfigDict(extra="forbid")

    row_version: int = Field(ge=1)
    clinic_id: UUID | None = None
    veterinarian_id: UUID | None = None
    patient_id: UUID | None = None
    collection_method: CollectionMethodLiteral | None = None
    service_level: ServiceLevelLiteral | None = None
    service_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class AttendanceTimelineEntryRead(BaseModel):
    """`before_state`/`after_state` are a generic diff — their keys vary by
    `action` (`attendances.confirmed`, `attendances.cancelled`,
    `attendances.updated`, ...), so `dict[str, Any]` here is the contract
    itself, not a shortcut around one (rule: .claude/rules/00-global.md —
    "dict[str, Any] como contrato sem necessidade" is about avoiding a
    generic escape hatch where a concrete shape exists; there isn't one
    here, by design, across heterogeneous audit actions)."""

    id: UUID
    occurred_at: datetime
    actor_user_id: UUID | None
    action: str
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    reason: str | None


class AttendanceTimelineResponse(BaseModel):
    items: list[AttendanceTimelineEntryRead]
    total: int
    page: int
    page_size: int


OnCallServiceLevelLiteral = Literal["PLANTAO_NORMAL", "PLANTAO_ESPECIAL"]


class OnCallFeeSettingRead(BaseModel):
    id: UUID
    service_level: OnCallServiceLevelLiteral
    fee_amount: Decimal
    schedule_label: str
    updated_at: datetime
    row_version: int


class OnCallFeeSettingListResponse(BaseModel):
    items: list[OnCallFeeSettingRead]


class OnCallFeeSettingUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fee_amount: Decimal = Field(ge=0)
    schedule_label: str = Field(default="", max_length=200)
    expected_row_version: int = Field(ge=1)


class AttendancePreviewResponse(BaseModel):
    """Dry-run projection — no `id`/`protocol_number`/`row_version`:
    nothing is persisted (`.claude/rules/02-backend.md`: schemas de
    create/update/read/filter separados)."""

    attendance_id: UUID
    clinic_id: UUID
    veterinarian_id: UUID
    patient_id: UUID
    collection_method: CollectionMethodLiteral
    service_level: ServiceLevelLiteral
    service_date: date
    items: list[AttendanceExamRead]
    subtotal: Decimal
    discount_total: Decimal
    surcharge_total: Decimal
    on_call_fee: Decimal
    grand_total: Decimal
