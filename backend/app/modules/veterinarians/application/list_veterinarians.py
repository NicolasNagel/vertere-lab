from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.veterinarians.application.dtos import VeterinarianDTO
from app.modules.veterinarians.application.mappers import veterinarian_to_dto
from app.modules.veterinarians.domain.entities import VeterinarianStatus
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.application.dtos import PageDTO
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "veterinarians.read"


@dataclass(frozen=True, kw_only=True)
class ListVeterinariansQuery:
    actor: AuthenticatedUserDTO
    page: int
    page_size: int
    status: VeterinarianStatus | None = None
    is_autonomous: bool | None = None
    search: str | None = None
    available_for_clinic_id: UUID | None = None


class ListVeterinariansUseCase:
    def __init__(self, *, veterinarians: VeterinarianRepository) -> None:
        self._veterinarians = veterinarians

    def execute(self, query: ListVeterinariansQuery) -> PageDTO[VeterinarianDTO]:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        veterinarians, total = self._veterinarians.list_page(
            page=query.page,
            page_size=query.page_size,
            status=query.status,
            is_autonomous=query.is_autonomous,
            search=query.search,
            available_for_clinic_id=query.available_for_clinic_id,
        )
        return PageDTO(
            items=[veterinarian_to_dto(veterinarian) for veterinarian in veterinarians],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )
