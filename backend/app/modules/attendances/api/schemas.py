"""Pydantic schemas for the attendances API — create/update/read kept
separate; never the SQLAlchemy model (rule: .claude/rules/02-backend.md)."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AttendanceStatusLiteral = Literal[
    "DRAFT", "CONFIRMED", "IN_PROGRESS", "COMPLETED", "CANCELLED", "ON_HOLD"
]
AttendanceExamStatusLiteral = Literal["ACTIVE", "CANCELLED"]
CollectionMethodLiteral = Literal["HELITO_NICOLAS", "INTERNAL", "MARLI", "COURIER", "UBER"]
ServiceLevelLiteral = Literal["NORMAL", "PLANTAO_NORMAL", "PLANTAO_ESPECIAL"]


class ExamComponentRead(BaseModel):
    code: str
    name: str


class AttendanceExamRead(BaseModel):
    id: UUID
    exam_id: UUID
    exam_code: str
    exam_name: str
    price_base: Decimal | None
    components: list[ExamComponentRead]
    quantity: int
    discount_amount: Decimal | None
    surcharge_amount: Decimal | None
    total_amount: Decimal | None
    override_reason: str | None
    status: AttendanceExamStatusLiteral


FeeKindLiteral = Literal["PLANTAO", "URGENCIA", "CLINICA"]


class FeeLineRead(BaseModel):
    kind: FeeKindLiteral
    label: str
    amount: Decimal | None
    rule_id: UUID | None = None


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
    subtotal: Decimal | None
    discount_total: Decimal | None
    surcharge_total: Decimal | None
    on_call_fee: Decimal | None
    is_urgent: bool
    urgency_fee: Decimal | None
    clinic_fee: Decimal | None
    fee_lines: list[FeeLineRead]
    grand_total: Decimal | None
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
    billed_total: Decimal | None


class AttendanceDraftCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinic_id: UUID
    veterinarian_id: UUID
    patient_id: UUID
    collection_method: CollectionMethodLiteral = "INTERNAL"
    service_level: ServiceLevelLiteral = "NORMAL"
    is_urgent: bool = False
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


class AttendanceItemEditRequest(BaseModel):
    """One line of the desired item set. `item_id` keeps an existing line (its price
    snapshot stays); `exam_id` adds a new one, priced on the attendance's service date."""

    model_config = ConfigDict(extra="forbid")

    item_id: UUID | None = None
    exam_id: UUID | None = None
    quantity: int = Field(default=1, ge=1)
    discount_amount: Decimal | None = Field(default=None, ge=0)
    override_reason: str | None = Field(default=None, max_length=500)


class AttendanceItemsUpdateRequest(BaseModel):
    """The complete desired set: existing lines left out are removed (kept as
    `CANCELLED` in history). `reason` is mandatory — it goes to the audit trail."""

    model_config = ConfigDict(extra="forbid")

    row_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)
    items: list[AttendanceItemEditRequest]


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
    is_urgent: bool | None = None
    service_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    # Obrigatório fora do rascunho (validado no caso de uso): vai para a auditoria.
    reason: str | None = Field(default=None, max_length=500)


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
    actor_name: str | None = None
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
    weekdays: list[int]
    start_time: time | None
    end_time: time | None
    updated_at: datetime
    row_version: int


class OnCallFeeSettingListResponse(BaseModel):
    items: list[OnCallFeeSettingRead]


class OnCallFeeSettingUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fee_amount: Decimal = Field(ge=0)
    weekdays: list[Annotated[int, Field(ge=0, le=6)]] = Field(default_factory=list, max_length=7)
    start_time: time | None = None
    end_time: time | None = None
    reason: str = Field(min_length=1, max_length=500)
    expected_row_version: int = Field(ge=1)


class UrgencyFeeSettingRead(BaseModel):
    id: UUID
    fee_amount: Decimal
    schedule_label: str
    weekdays: list[int]
    start_time: time | None
    end_time: time | None
    updated_at: datetime
    row_version: int


class UrgencyFeeSettingUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fee_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    weekdays: list[Annotated[int, Field(ge=0, le=6)]] = Field(default_factory=list, max_length=7)
    start_time: time | None = None
    end_time: time | None = None
    reason: str = Field(min_length=1, max_length=500)
    expected_row_version: int = Field(ge=1)


class ClinicFeeRuleRead(BaseModel):
    id: UUID
    clinic_id: UUID
    name: str
    fee_amount: Decimal
    valid_from: date
    valid_to: date | None
    is_active: bool
    updated_at: datetime
    row_version: int


class ClinicFeeRuleListResponse(BaseModel):
    items: list[ClinicFeeRuleRead]


class ClinicFeeRuleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinic_id: UUID
    name: str = Field(min_length=1, max_length=120)
    fee_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    valid_from: date
    valid_to: date | None = None
    reason: str = Field(min_length=1, max_length=500)


class ClinicFeeRuleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    fee_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    valid_from: date
    valid_to: date | None = None
    is_active: bool
    reason: str = Field(min_length=1, max_length=500)
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
    subtotal: Decimal | None
    discount_total: Decimal | None
    surcharge_total: Decimal | None
    on_call_fee: Decimal | None
    is_urgent: bool
    urgency_fee: Decimal | None
    clinic_fee: Decimal | None
    fee_lines: list[FeeLineRead]
    grand_total: Decimal | None
