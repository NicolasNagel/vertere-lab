"""Read a single closed competence — Incremento 4.2, `GET /closures/{id}`.

Pure read from the persisted snapshot, never recomputed from the live
attendances (`.claude/rules/13-monthly-closure.md`: "exportação sempre parte
do snapshot + ajustes, nunca recalcula do atendimento vivo" — the same
principle applies to any read of a closed competence, not just export).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.billing.application.dtos import MonthlyClosureDTO
from app.modules.billing.application.mappers import monthly_closure_to_dto
from app.modules.billing.domain.repositories import MonthlyClosureRepository
from app.shared.application.authorization import ActorContext
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "closures.read"


@dataclass(frozen=True, kw_only=True)
class GetMonthlyClosureQuery:
    actor: ActorContext
    closure_id: UUID


class GetMonthlyClosureUseCase:
    def __init__(self, *, closures: MonthlyClosureRepository) -> None:
        self._closures = closures

    def execute(self, query: GetMonthlyClosureQuery) -> MonthlyClosureDTO:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        closure = self._closures.get_by_id(query.closure_id)
        if closure is None or not query.actor.can_access_clinic(closure.clinic_id):
            raise NotFoundError("Fechamento não encontrado.")

        return monthly_closure_to_dto(closure)
