from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.veterinarian_clinics.application.dtos import LinkedClinicDTO
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.shared.application.authorization import ActorContext
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "veterinarians.read"


@dataclass(frozen=True, kw_only=True)
class ListClinicsForVeterinarianQuery:
    actor: ActorContext
    veterinarian_id: UUID


class ListClinicsForVeterinarianUseCase:
    def __init__(
        self, *, links: VeterinarianClinicLinkRepository, clinics: ClinicRepository
    ) -> None:
        self._links = links
        self._clinics = clinics

    def execute(self, query: ListClinicsForVeterinarianQuery) -> list[LinkedClinicDTO]:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        result: list[LinkedClinicDTO] = []
        for link in self._links.list_by_veterinarian(query.veterinarian_id):
            clinic = self._clinics.get_by_id(link.clinic_id)
            if clinic is None:
                continue
            result.append(
                LinkedClinicDTO(
                    clinic_id=clinic.id,
                    clinic_name=clinic.name,
                    primary_clinic=link.primary_clinic,
                )
            )
        return result
