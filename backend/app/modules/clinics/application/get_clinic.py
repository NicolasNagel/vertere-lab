from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.clinics.application.dtos import ClinicDTO
from app.modules.clinics.application.mappers import clinic_to_dto
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "clinics.read"


@dataclass(frozen=True, kw_only=True)
class GetClinicQuery:
    actor: AuthenticatedUserDTO
    clinic_id: UUID


class GetClinicUseCase:
    def __init__(self, *, clinics: ClinicRepository) -> None:
        self._clinics = clinics

    def execute(self, query: GetClinicQuery) -> ClinicDTO:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        clinic = self._clinics.get_by_id(query.clinic_id)
        if clinic is None:
            raise NotFoundError("Clínica não encontrada.")

        return clinic_to_dto(clinic)
