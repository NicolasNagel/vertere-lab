from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.veterinarians.application.dtos import VeterinarianDTO
from app.modules.veterinarians.application.mappers import veterinarian_to_dto
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "veterinarians.read"


@dataclass(frozen=True, kw_only=True)
class GetVeterinarianQuery:
    actor: AuthenticatedUserDTO
    veterinarian_id: UUID


class GetVeterinarianUseCase:
    def __init__(self, *, veterinarians: VeterinarianRepository) -> None:
        self._veterinarians = veterinarians

    def execute(self, query: GetVeterinarianQuery) -> VeterinarianDTO:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        veterinarian = self._veterinarians.get_by_id(query.veterinarian_id)
        if veterinarian is None:
            raise NotFoundError("Veterinário não encontrado.")

        return veterinarian_to_dto(veterinarian)
