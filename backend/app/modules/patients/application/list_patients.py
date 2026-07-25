from __future__ import annotations

from dataclasses import dataclass

from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.application.dtos import PatientDTO
from app.modules.patients.application.mappers import patient_to_dto
from app.modules.patients.domain.entities import PatientStatus
from app.modules.patients.domain.repositories import PatientRepository
from app.shared.application.dtos import PageDTO
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "patients.read"


@dataclass(frozen=True, kw_only=True)
class ListPatientsQuery:
    actor: AuthenticatedUserDTO
    page: int
    page_size: int
    status: PatientStatus | None = None
    search: str | None = None


class ListPatientsUseCase:
    def __init__(self, *, patients: PatientRepository) -> None:
        self._patients = patients

    def execute(self, query: ListPatientsQuery) -> PageDTO[PatientDTO]:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        patients, total = self._patients.list_page(
            page=query.page,
            page_size=query.page_size,
            status=query.status,
            search=query.search,
        )
        return PageDTO(
            items=[patient_to_dto(patient) for patient in patients],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )
