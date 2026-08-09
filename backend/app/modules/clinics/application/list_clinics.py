from __future__ import annotations

from dataclasses import dataclass

from app.modules.clinics.application.dtos import ClinicDTO
from app.modules.clinics.application.mappers import clinic_to_dto
from app.modules.clinics.domain.entities import ClinicStatus
from app.modules.clinics.domain.repositories import ClinicRepository
from app.shared.application.authorization import ActorContext
from app.shared.application.dtos import PageDTO
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "clinics.read"


@dataclass(frozen=True, kw_only=True)
class ListClinicsQuery:
    actor: ActorContext
    page: int
    page_size: int
    status: ClinicStatus | None = None
    search: str | None = None


class ListClinicsUseCase:
    def __init__(self, *, clinics: ClinicRepository) -> None:
        self._clinics = clinics

    def execute(self, query: ListClinicsQuery) -> PageDTO[ClinicDTO]:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        clinics, total = self._clinics.list_page(
            page=query.page,
            page_size=query.page_size,
            status=query.status,
            search=query.search,
            clinic_ids=query.actor.clinic_filter,
        )
        return PageDTO(
            items=[clinic_to_dto(clinic) for clinic in clinics],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )
