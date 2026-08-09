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

from app.shared.domain.errors import InvalidStateTransitionError, ValidationError

_MAX_PERIOD_SPAN_DAYS = 366


@dataclass(frozen=True, kw_only=True)
class CompetencePeriod:
    """A closure period — any `[period_start, period_end]` range chosen at
    close time, not necessarily a full calendar month (some clinics close
    quinzenalmente). Membership is decided against `service_date`, never
    `billing_competence` (`eligibility.py`) — `billing_competence` stays
    immutable and is never the selection criterion
    (`.claude/rules/13-monthly-closure.md`: "Retroatividade — competência de
    um atendimento não muda sem um caso de uso específico e auditado").

    `year`/`month` below are *derived* from `period_start` — display/grouping
    metadata only (e.g. `MonthlyClosure.competence_year/month`), never used
    for eligibility or uniqueness."""

    period_start: date
    period_end: date

    def __post_init__(self) -> None:
        if self.period_end < self.period_start:
            raise ValidationError("Data final do período não pode ser anterior à inicial.")
        if self.period_start.year < 2000:
            raise ValidationError("Data inicial do período é inválida.")
        span_days = (self.period_end - self.period_start).days + 1
        if span_days > _MAX_PERIOD_SPAN_DAYS:
            raise ValidationError(
                f"Período de fechamento não pode exceder {_MAX_PERIOD_SPAN_DAYS} dias."
            )

    @classmethod
    def for_month(cls, *, year: int, month: int) -> CompetencePeriod:
        """Convenience factory for the common case — a full calendar month."""
        if not (1 <= month <= 12):
            raise ValidationError("Mês de competência deve estar entre 1 e 12.")
        period_start = date(year, month, 1)
        if month == 12:
            period_end = date(year, 12, 31)
        else:
            next_month_start = date(year, month + 1, 1)
            period_end = date.fromordinal(next_month_start.toordinal() - 1)
        return cls(period_start=period_start, period_end=period_end)

    @property
    def year(self) -> int:
        return self.period_start.year

    @property
    def month(self) -> int:
        return self.period_start.month


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
    service_date: date | None
    billing_competence: date | None
    monthly_closure_id: UUID | None
    protocol_number: str | None
    patient_name: str
    exam_name: str
    service_level: str
    exam_category: str
    price_base: Decimal
    quantity: int
    discount_amount: Decimal
    surcharge_amount: Decimal
    total_amount: Decimal
    # Flat per-attendance fee (`AttendanceRecord.on_call_fee`), repeated on
    # every item row of the same attendance because a candidate is per-item
    # — callers must sum it once per **distinct** `attendance_id` among the
    # items they include, never once per row, or a multi-exam attendance
    # double/triple-counts the fee.
    attendance_on_call_fee: Decimal = Decimal("0")


@dataclass(frozen=True, kw_only=True)
class ClosurePreviewItem:
    attendance_id: UUID
    attendance_exam_id: UUID
    protocol_number: str | None
    patient_name: str
    exam_name: str
    service_level: str
    exam_category: str
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
    on_call_fee_total: Decimal
    grand_total: Decimal
    eligible_items: list[ClosurePreviewItem] = field(default_factory=list)
    blocked_items: list[ClosurePreviewBlockedItem] = field(default_factory=list)
    generated_at: datetime


class ClosureStatus(StrEnum):
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"


class AdjustmentKind(StrEnum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


@dataclass(frozen=True, kw_only=True)
class FinancialAdjustment:
    id: UUID
    monthly_closure_id: UUID
    monthly_closure_item_id: UUID | None
    kind: AdjustmentKind
    amount: Decimal
    reason: str
    created_by: UUID | None
    created_at: datetime

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise ValidationError("O valor do ajuste deve ser maior que zero.")


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
    # `None` só em fechamentos criados antes da 0035 — nunca reconsultado do
    # atendimento vivo depois de fechado.
    service_level: str | None = None
    exam_category: str | None = None

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
    on_call_fee_total: Decimal = Decimal("0")
    reopened_at: datetime | None = None
    version: int = 1
    integrity_hash: str | None = None
    items: list[MonthlyClosureItem] = field(default_factory=list)
    adjustments: list[FinancialAdjustment] = field(default_factory=list)

    def __post_init__(self) -> None:
        if (
            self.subtotal < 0
            or self.discount_total < 0
            or self.surcharge_total < 0
            or self.on_call_fee_total < 0
        ):
            raise ValidationError("Totais do fechamento não podem ser negativos.")
        if self.grand_total < 0:
            raise ValidationError("Total do fechamento não pode ser negativo.")
        if self.item_count != len(self.items):
            raise ValidationError("Contagem de itens não confere com os itens do fechamento.")

    def reopen(self, *, reopened_at: datetime) -> None:
        if self.status is not ClosureStatus.CLOSED:
            raise InvalidStateTransitionError("Somente um fechamento fechado pode ser reaberto.")
        self.status = ClosureStatus.REOPENED
        self.reopened_at = reopened_at
