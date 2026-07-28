"""Attendances domain entities.

No FastAPI/SQLAlchemy import here (rule: .claude/rules/globals.md — domain
layer). Mutation happens through named methods, never by callers poking at
fields directly, so invariants stay enforced in one place.

This module now covers the confirmation slice
(`docs/03-modelo-de-dominio.md` §3): `AttendanceExam` items with a snapshot
of catalog price/name, financial header totals, `billing_competence` and a
transactional protocol (`protocol_year`/`protocol_sequence`). `Idempotency-
Key` on `/confirm` is deliberately absent from this slice — see the plan
checkpoint (backend-only prerequisite for the closure preview, no UI yet).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.shared.domain.errors import InvalidStateTransitionError, ValidationError
from app.shared.domain.money import round_currency


class AttendanceStatus(StrEnum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ON_HOLD = "ON_HOLD"


class AttendanceExamStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


@dataclass(kw_only=True)
class AttendanceExam:
    """An exam item snapshotted onto a confirmed attendance.

    `exam_code`/`exam_name`/`price_base` are a snapshot taken at
    confirmation time — never re-read from the catalog afterwards
    (`.claude/rules/attendence.md`: "atualização da tabela de preço vigente
    nunca altera um snapshot já persistido"). `total_amount` is always
    derived here, never accepted from a caller (rule: "total sempre
    calculado no backend").
    """

    id: UUID
    attendance_id: UUID
    exam_id: UUID
    exam_code: str
    exam_name: str
    price_base: Decimal
    quantity: int = 1
    discount_amount: Decimal = Decimal("0")
    surcharge_amount: Decimal = Decimal("0")
    total_amount: Decimal = Decimal("0")
    override_reason: str | None = None
    override_by: UUID | None = None
    status: AttendanceExamStatus = AttendanceExamStatus.ACTIVE

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValidationError("Quantidade do item deve ser maior que zero.")
        if self.discount_amount < 0 or self.surcharge_amount < 0:
            raise ValidationError("Desconto e adicional do item não podem ser negativos.")
        self.total_amount = round_currency(
            self.price_base * self.quantity - self.discount_amount + self.surcharge_amount
        )
        if self.total_amount < 0:
            raise ValidationError("Total do item não pode ser negativo.")


@dataclass(kw_only=True)
class AttendanceRecord:
    id: UUID
    clinic_id: UUID
    veterinarian_id: UUID
    patient_id: UUID
    service_date: date | None = None
    notes: str | None = None
    status: AttendanceStatus = AttendanceStatus.DRAFT
    items: list[AttendanceExam] = field(default_factory=list)
    billing_competence: date | None = None
    subtotal: Decimal = Decimal("0")
    discount_total: Decimal = Decimal("0")
    surcharge_total: Decimal = Decimal("0")
    grand_total: Decimal = Decimal("0")
    protocol_year: int | None = None
    protocol_sequence: int | None = None
    protocol_number: str | None = None
    # None until Incremento 4.2 associates this attendance with a real
    # closure — the field exists from this slice on because "item já em
    # fechamento é imutável" is a structural invariant the confirmation
    # slice must already respect (docs/03-modelo-de-dominio.md §6).
    monthly_closure_id: UUID | None = None
    created_by: UUID | None = None
    updated_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    row_version: int = 1

    def confirm(
        self,
        *,
        items: list[AttendanceExam],
        protocol_year: int,
        protocol_sequence: int,
        now: datetime,
        confirmed_by: UUID | None,
    ) -> None:
        if self.status != AttendanceStatus.DRAFT:
            raise InvalidStateTransitionError("Atendimento não está em rascunho.")
        if self.service_date is None:
            raise ValidationError("Data do atendimento é obrigatória para confirmar.")
        if not items:
            raise ValidationError("Confirmação exige ao menos um item de exame.")

        self.items = items
        self.subtotal = round_currency(
            sum((i.price_base * i.quantity for i in items), Decimal("0"))
        )
        self.discount_total = round_currency(sum((i.discount_amount for i in items), Decimal("0")))
        self.surcharge_total = round_currency(
            sum((i.surcharge_amount for i in items), Decimal("0"))
        )
        self.grand_total = round_currency(sum((i.total_amount for i in items), Decimal("0")))
        self.protocol_year = protocol_year
        self.protocol_sequence = protocol_sequence
        self.protocol_number = f"{protocol_year}/{protocol_sequence:06d}"
        self.billing_competence = self.service_date.replace(day=1)
        self.status = AttendanceStatus.CONFIRMED
        self.updated_by = confirmed_by
        self.updated_at = now
