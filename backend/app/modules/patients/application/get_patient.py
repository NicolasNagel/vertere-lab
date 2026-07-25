from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.application.dtos import PatientDTO
from app.modules.patients.application.mappers import patient_to_dto
from app.modules.patients.domain.repositories import PatientRepository
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "patients.read"


@dataclass(frozen=True, kw_only=True)
class GetPatientQuery:
    actor: AuthenticatedUserDTO
    patient_id: UUID


class GetPatientUseCase:
    def __init__(self, *, patients: PatientRepository) -> None:
        self._patients = patients

    def execute(self, query: GetPatientQuery) -> PatientDTO:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        patient = self._patients.get_by_id(query.patient_id)
        if patient is None:
            raise NotFoundError("Paciente não encontrado.")

        return patient_to_dto(patient)
