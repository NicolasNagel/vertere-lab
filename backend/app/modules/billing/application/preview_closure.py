"""Closure preview — read-only, never persists, never blocks anything
(`.claude/rules/13-monthly-closure.md`). Uses the exact same eligibility rule
Incremento 4.2 will reuse (`domain/eligibility.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.modules.billing.application.dtos import ClosurePreviewDTO
from app.modules.billing.application.mappers import closure_preview_to_dto
from app.modules.billing.domain.eligibility import is_eligible
from app.modules.billing.domain.entities import (
    ClosurePreview,
    ClosurePreviewBlockedItem,
    ClosurePreviewItem,
    CompetencePeriod,
)
from app.modules.billing.domain.repositories import ClosurePreviewRepository
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError
from app.shared.domain.money import round_currency

_REQUIRED_PERMISSION = "closures.preview"
_CANCELLED = "CANCELLED"


@dataclass(frozen=True, kw_only=True)
class PreviewClosureQuery:
    actor: AuthenticatedUserDTO
    clinic_id: UUID
    year: int
    month: int


class PreviewClosureUseCase:
    def __init__(
        self,
        *,
        clinics: ClinicRepository,
        candidates: ClosurePreviewRepository,
        clock: Clock,
    ) -> None:
        self._clinics = clinics
        self._candidates = candidates
        self._clock = clock

    def execute(self, query: PreviewClosureQuery) -> ClosurePreviewDTO:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        clinic = self._clinics.get_by_id(query.clinic_id)
        if clinic is None:
            raise NotFoundError("Clínica não encontrada.")

        period = CompetencePeriod(year=query.year, month=query.month)
        candidates = self._candidates.list_candidates(clinic_id=query.clinic_id, period=period)

        eligible_items: list[ClosurePreviewItem] = []
        blocked_items: list[ClosurePreviewBlockedItem] = []
        subtotal = Decimal("0")
        discount_total = Decimal("0")
        surcharge_total = Decimal("0")
        grand_total = Decimal("0")
        attendance_ids: set[UUID] = set()
        cancelled_attendance_ids: set[UUID] = set()

        for candidate in candidates:
            attendance_ids.add(candidate.attendance_id)
            if candidate.attendance_status == _CANCELLED:
                cancelled_attendance_ids.add(candidate.attendance_id)

            eligible, reason = is_eligible(candidate, period)
            if eligible:
                eligible_items.append(
                    ClosurePreviewItem(
                        attendance_id=candidate.attendance_id,
                        attendance_exam_id=candidate.attendance_exam_id,
                        protocol_number=candidate.protocol_number,
                        patient_name=candidate.patient_name,
                        exam_name=candidate.exam_name,
                        total_amount=candidate.total_amount,
                    )
                )
                subtotal += candidate.price_base * candidate.quantity
                discount_total += candidate.discount_amount
                surcharge_total += candidate.surcharge_amount
                grand_total += candidate.total_amount
            else:
                assert reason is not None
                blocked_items.append(
                    ClosurePreviewBlockedItem(
                        attendance_id=candidate.attendance_id,
                        attendance_exam_id=candidate.attendance_exam_id,
                        protocol_number=candidate.protocol_number,
                        patient_name=candidate.patient_name,
                        exam_name=candidate.exam_name,
                        total_amount=candidate.total_amount,
                        reason=reason,
                    )
                )

        preview = ClosurePreview(
            clinic_id=query.clinic_id,
            competence_year=period.year,
            competence_month=period.month,
            period_start=period.period_start,
            period_end=period.period_end,
            attendance_count=len(attendance_ids),
            cancelled_attendance_count=len(cancelled_attendance_ids),
            item_count=len(eligible_items),
            subtotal=round_currency(subtotal),
            discount_total=round_currency(discount_total),
            surcharge_total=round_currency(surcharge_total),
            grand_total=round_currency(grand_total),
            eligible_items=eligible_items,
            blocked_items=blocked_items,
            generated_at=self._clock.now(),
        )
        return closure_preview_to_dto(preview)
