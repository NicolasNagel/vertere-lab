"""Billing domain entities — Incremento 4.1 (Prévia de Fechamento) only.

No FastAPI/SQLAlchemy import here (rule: .claude/rules/globals.md — domain
layer).

The preview is derived in memory, never persisted
(`.claude/rules/monthly-closure.md`: "não fecha nem bloqueia nada — é só
leitura"). `MonthlyClosure`/`MonthlyClosureItem` as persistent tables only
arrive with Incremento 4.2 — these `ClosurePreview*` names are deliberately
distinct so they don't collide with the persistent entities reserved for
that increment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
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
