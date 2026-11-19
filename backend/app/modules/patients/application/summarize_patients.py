from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.patients.application.dtos import PatientsSummaryDTO
from app.modules.patients.domain.repositories import PatientRepository
from app.shared.application.authorization import ActorContext
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "patients.read"


@dataclass(frozen=True, kw_only=True)
class SummarizePatientsQuery:
    actor: ActorContext
    search: str | None = None
    clinic_id: UUID | None = None
    species_id: UUID | None = None


class SummarizePatientsUseCase:
    """Counts for the summary cards: same scope and filters as the list, split by status."""

    def __init__(self, *, patients: PatientRepository) -> None:
        self._patients = patients

    def execute(self, query: SummarizePatientsQuery) -> PatientsSummaryDTO:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        if query.clinic_id is not None and not query.actor.can_access_clinic(query.clinic_id):
            return PatientsSummaryDTO(total=0, active=0, inactive=0)
        active, inactive = self._patients.count_by_status(
            search=query.search,
            clinic_ids=query.actor.clinic_filter,
            clinic_id=query.clinic_id,
            species_id=query.species_id,
        )
        return PatientsSummaryDTO(total=active + inactive, active=active, inactive=inactive)
