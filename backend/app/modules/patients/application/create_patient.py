"""Create a Patient.

Owner data (`owner_name`/`owner_phone`/`owner_document`) is captured as
plain fields here, not looked up/created against a separate Owner
aggregate — see `app/modules/patients/domain/entities.py` for why. No
duplicate check on owner or patient name: the Patient form warns about
likely duplicates client-side via `GET /patients?search=`, it does not
block creation server-side.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.application.dtos import PatientDTO
from app.modules.patients.application.mappers import patient_to_dto
from app.modules.patients.domain.entities import Patient, PatientSex, PatientStatus
from app.modules.patients.domain.repositories import PatientRepository
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "patients.manage"


@dataclass(frozen=True, kw_only=True)
class CreatePatientCommand:
    actor: AuthenticatedUserDTO
    name: str
    species_id: UUID
    sex: str
    breed: str | None
    age_description: str | None
    owner_name: str
    owner_phone: str | None
    owner_document: str | None
    notes: str | None


class CreatePatientUseCase:
    def __init__(
        self,
        *,
        patients: PatientRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._patients = patients
        self._audit = audit
        self._clock = clock

    def execute(self, command: CreatePatientCommand) -> PatientDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        now = self._clock.now()
        patient = Patient(
            id=uuid4(),
            name=command.name,
            species_id=command.species_id,
            sex=PatientSex(command.sex),
            breed=command.breed,
            age_description=command.age_description,
            owner_name=command.owner_name,
            owner_phone=command.owner_phone,
            owner_document=command.owner_document,
            status=PatientStatus.ACTIVE,
            notes=command.notes,
            created_by=command.actor.id,
            updated_by=command.actor.id,
            created_at=now,
            updated_at=now,
        )
        self._patients.add(patient)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="patients.created",
                entity_type="patient",
                entity_id=str(patient.id),
                after_state={"name": patient.name, "status": patient.status.value},
            )
        )

        return patient_to_dto(patient)
