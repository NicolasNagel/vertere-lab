"""Billing domain entities.

No FastAPI/SQLAlchemy import here (rule: .claude/rules/00-global.md — domain
layer).

`ClosurePreview*` (Incremento 4.1): derived in memory, never persisted
(`.claude/rules/13-monthly-closure.md`: "não fecha nem bloqueia nada — é só
leitura"). Deliberately named apart from `MonthlyClosure`/`MonthlyClosureItem`
below so the two never collide.

`MonthlyClosure`/`MonthlyClosureItem` (Incremento 4.2): persistent snapshot
created by `POST /closures`. This slice only ever creates them with
`status=CLOSED` directly — there is no persisted "draft closure" step (the
preview above stays in-memory-only), so `DRAFT`/`CANCELLED` from the abstract
state diagram in `docs/03-modelo-de-dominio.md` §6 are not reachable here.
`REOPENED` is reserved for Incremento 4.3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.shared.domain.errors import ValidationError


@dataclass(frozen=True, kw_only=True)
class CompetencePeriod:
    """Calendar-month competence (`docs/07-nucleo-v1.md` §4.1: competência é
    gravada como `billing_competence` na confirmação, nunca derivada
    depois)."""

    year: int
    month: int

    def __post_init__(self) -> None:
        if not (1 <= self.month <= 12):
            raise ValidationError("Mês de competência deve estar entre 1 e 12.")
        if self.year < 2000:
            raise ValidationError("Ano de competência inválido.")

    @property
    def period_start(self) -> date:
        return date(self.year, self.month, 1)

    @property
    def period_end(self) -> date:
        if self.month == 12:
            return date(self.year, 12, 31)
        next_month_start = date(self.year, self.month + 1, 1)
        return date.fromordinal(next_month_start.toordinal() - 1)


@dataclass(frozen=True, kw_only=True)
class ClosureCandidateItem:
    """Raw shape read from `attendances`/`attendance_exams` for a clinic +
    competence — the repository's output, before eligibility is applied.
    Carries per-item money fields (not just `total_amount`) so the preview
    can report subtotal/discount/surcharge breakdown, not just a single
    number (rule: totais calculados no backend a partir do item, nunca de
    um valor pré-agregado sem revalidar)."""

    attendance_id: UUID
    attendance_exam_id: UUID
    attendance_status: str
    item_status: str
    billing_competence: date | None
    monthly_closure_id: UUID | None
    protocol_number: str | None
    patient_name: str
    exam_name: str
    price_base: Decimal
    quantity: int
    discount_amount: Decimal
    surcharge_amount: Decimal
    total_amount: Decimal


@dataclass(frozen=True, kw_only=True)
class ClosurePreviewItem:
    attendance_id: UUID
    attendance_exam_id: UUID
    protocol_number: str | None
    patient_name: str
    exam_name: str
    total_amount: Decimal


@dataclass(frozen=True, kw_only=True)
class ClosurePreviewBlockedItem:
    attendance_id: UUID
    attendance_exam_id: UUID
    protocol_number: str | None
    patient_name: str
    exam_name: str
    total_amount: Decimal
    reason: str


@dataclass(frozen=True, kw_only=True)
class ClosurePreview:
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
    eligible_items: list[ClosurePreviewItem] = field(default_factory=list)
    blocked_items: list[ClosurePreviewBlockedItem] = field(default_factory=list)
    generated_at: datetime


class ClosureStatus(StrEnum):
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"


@dataclass(kw_only=True)
class MonthlyClosureItem:
    """One snapshotted `AttendanceExam` inside a closure — carries the full
    money breakdown, not just `total_amount`, so exportação and a future
    ajuste (Incremento 4.3) never need to re-read the live attendance
    (`.claude/rules/03-database.md`: "snapshot contém valor suficiente para
    reprodução total sem consultar o atendimento original")."""

    id: UUID
    monthly_closure_id: UUID
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

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValidationError("Quantidade do item de fechamento deve ser maior que zero.")
        if self.discount_amount < 0 or self.surcharge_amount < 0 or self.total_amount < 0:
            raise ValidationError(
                "Valores financeiros do item de fechamento não podem ser negativos."
            )


@dataclass(kw_only=True)
class MonthlyClosure:
    """Persistent, immutable-once-created record of a closed competence
    (`.claude/rules/13-monthly-closure.md`: "fechamento fechado é imutável").
    Construction here mirrors exactly what the close use case just computed
    — this class does not recompute anything, it only enforces that the
    header totals agree with what was passed in (defense in depth on top of
    the use case's own pre-commit check)."""

    id: UUID
    clinic_id: UUID
    competence_year: int
    competence_month: int
    period_start: date
    period_end: date
    status: ClosureStatus
    item_count: int
    subtotal: Decimal
    discount_total: Decimal
    surcharge_total: Decimal
    grand_total: Decimal
    generated_by: UUID | None
    closed_by: UUID | None
    generated_at: datetime
    closed_at: datetime
    reopened_at: datetime | None = None
    version: int = 1
    integrity_hash: str | None = None
    items: list[MonthlyClosureItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.subtotal < 0 or self.discount_total < 0 or self.surcharge_total < 0:
            raise ValidationError("Totais do fechamento não podem ser negativos.")
        if self.grand_total < 0:
            raise ValidationError("Total do fechamento não pode ser negativo.")
        if self.item_count != len(self.items):
            raise ValidationError("Contagem de itens não confere com os itens do fechamento.")
