from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.application.dtos import PatientDTO
from app.modules.patients.application.mappers import patient_to_dto
from app.modules.patients.domain.entities import PatientSex, PatientStatus
from app.modules.patients.domain.repositories import PatientRepository, SpeciesRepository
from app.shared.application.clock import Clock
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "patients.manage"


@dataclass(frozen=True, kw_only=True)
class UpdatePatientCommand:
    actor: AuthenticatedUserDTO
    patient_id: UUID
    name: str
    species_id: UUID
    sex: str
    breed: str | None
    age_description: str | None
    owner_name: str
    owner_phone: str | None
    owner_document: str | None
    status: str
    notes: str | None
    expected_row_version: int


class UpdatePatientUseCase:
    def __init__(
        self,
        *,
        patients: PatientRepository,
        species: SpeciesRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._patients = patients
        self._species = species
        self._audit = audit
        self._clock = clock

    def execute(self, command: UpdatePatientCommand) -> PatientDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        patient = self._patients.get_by_id(command.patient_id)
        if patient is None:
            raise NotFoundError("Paciente não encontrado.")

        if patient.row_version != command.expected_row_version:
            raise ConflictError(
                "Este paciente foi alterado por outra pessoa. Recarregue e tente de novo."
            )

        known_species_ids = {species.id for species in self._species.list_all()}
        if command.species_id not in known_species_ids:
            raise NotFoundError("Espécie não encontrada.")

        before_state = {"name": patient.name, "status": patient.status.value}

        patient.update_details(
            name=command.name,
            species_id=command.species_id,
            sex=PatientSex(command.sex),
            breed=command.breed,
            age_description=command.age_description,
            owner_name=command.owner_name,
            owner_phone=command.owner_phone,
            owner_document=command.owner_document,
            status=PatientStatus(command.status),
            notes=command.notes,
            updated_by=command.actor.id,
            now=self._clock.now(),
        )
        self._patients.save(patient)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="patients.updated",
                entity_type="patient",
                entity_id=str(patient.id),
                before_state=before_state,
                after_state={"name": patient.name, "status": patient.status.value},
            )
        )

        return patient_to_dto(patient)
