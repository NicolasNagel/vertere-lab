from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.veterinarian_clinics.application.dtos import LinkedVeterinarianDTO
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "clinics.read"


@dataclass(frozen=True, kw_only=True)
class ListVeterinariansForClinicQuery:
    actor: AuthenticatedUserDTO
    clinic_id: UUID


class ListVeterinariansForClinicUseCase:
    def __init__(
        self, *, links: VeterinarianClinicLinkRepository, veterinarians: VeterinarianRepository
    ) -> None:
        self._links = links
        self._veterinarians = veterinarians

    def execute(self, query: ListVeterinariansForClinicQuery) -> list[LinkedVeterinarianDTO]:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        result: list[LinkedVeterinarianDTO] = []
        for link in self._links.list_by_clinic(query.clinic_id):
            veterinarian = self._veterinarians.get_by_id(link.veterinarian_id)
            if veterinarian is None:
                continue
            result.append(
                LinkedVeterinarianDTO(
                    veterinarian_id=veterinarian.id,
                    veterinarian_name=veterinarian.name,
                    crmv=str(veterinarian.crmv),
                    primary_clinic=link.primary_clinic,
                )
            )
        return result
