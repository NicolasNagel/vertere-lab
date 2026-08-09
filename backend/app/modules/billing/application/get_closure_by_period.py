"""Read the closure for a clinic+period without knowing its id —
`GET /closures/by-period`. Powers the unified fechamento screen (Tela 15):
given clinic+period, decide "mostrar prévia" vs "mostrar fechamento
existente" (`.claude/rules/13-monthly-closure.md`).

Uses `get_latest_for_clinic_and_period` (highest `version`), not
`get_active_for_clinic_and_period`, so a `REOPENED` closure still resolves
here instead of silently falling back to the prévia. Lookup is by period
*overlap*, not exact match — periods are free-form since Fatia 2/3
(quinzenal closures), so "the closure for this period" means "the closure
whose stored range touches the range the screen asked about".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.modules.billing.application.dtos import MonthlyClosureDTO
from app.modules.billing.application.mappers import monthly_closure_to_dto
from app.modules.billing.domain.entities import CompetencePeriod
from app.modules.billing.domain.repositories import MonthlyClosureRepository
from app.shared.application.authorization import ActorContext
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "closures.read"


@dataclass(frozen=True, kw_only=True)
class GetClosureByPeriodQuery:
    actor: ActorContext
    clinic_id: UUID
    period_start: date
    period_end: date


class GetClosureByPeriodUseCase:
    def __init__(self, *, closures: MonthlyClosureRepository) -> None:
        self._closures = closures

    def execute(self, query: GetClosureByPeriodQuery) -> MonthlyClosureDTO:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        if not query.actor.can_access_clinic(query.clinic_id):
            raise NotFoundError("Fechamento não encontrado.")

        period = CompetencePeriod(period_start=query.period_start, period_end=query.period_end)
        closure = self._closures.get_latest_for_clinic_and_period(
            clinic_id=query.clinic_id,
            period_start=period.period_start,
            period_end=period.period_end,
        )
        if closure is None:
            raise NotFoundError("Nenhum fechamento encontrado para este período.")

        return monthly_closure_to_dto(closure)
