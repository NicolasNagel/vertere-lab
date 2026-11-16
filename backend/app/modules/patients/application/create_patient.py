"""Create a Patient.

Owner data (`owner_name`/`owner_phone`/`owner_document`) is captured as
plain fields here, not looked up/created against a separate Owner
aggregate — see `app/modules/patients/domain/entities.py` for why. No
duplicate check on owner or patient name: the Patient form warns about
likely duplicates client-side via `GET /patients?search=`, it does not
block creation server-side.

`species_id` is validated against `SpeciesRepository` before persisting —
same pattern as `category_id`/`species_ids` in
`app/modules/catalog/application/create_exam.py` — so an unknown id raises
`NotFoundError` instead of surfacing as a raw `IntegrityError`.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.patients.application.dtos import PatientDTO
from app.modules.patients.application.mappers import patient_to_dto
from app.modules.patients.domain.entities import Patient, PatientAge, PatientSex, PatientStatus
from app.modules.patients.domain.repositories import PatientRepository, SpeciesRepository
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "patients.manage"


@dataclass(frozen=True, kw_only=True)
class CreatePatientCommand:
    actor: ActorContext
    clinic_id: UUID | None = None
    name: str
    species_id: UUID
    sex: str
    breed: str | None
    age_description: str | None
    owner_name: str
    owner_phone: str | None
    owner_document: str | None
    notes: str | None
    age_value: int | None = None
    age_unit: str | None = None


class CreatePatientUseCase:
    def __init__(
        self,
        *,
        patients: PatientRepository,
        species: SpeciesRepository,
        clinics: ClinicRepository | None = None,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._patients = patients
        self._species = species
        self._clinics = clinics
        self._audit = audit
        self._clock = clock

    def execute(self, command: CreatePatientCommand) -> PatientDTO:
        if command.clinic_id is not None:
            if not command.actor.can_access_clinic(command.clinic_id):
                raise NotFoundError("Clínica não encontrada.")
            if self._clinics is None or self._clinics.get_by_id(command.clinic_id) is None:
                raise NotFoundError("Clínica não encontrada.")
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        known_species_ids = {species.id for species in self._species.list_all()}
        if command.species_id not in known_species_ids:
            raise NotFoundError("Espécie não encontrada.")

        age = PatientAge.from_optional(command.age_value, command.age_unit)
        now = self._clock.now()
        patient = Patient(
            id=uuid4(),
            clinic_id=command.clinic_id,
            name=command.name,
            species_id=command.species_id,
            sex=PatientSex(command.sex),
            breed=command.breed,
            age_description=age.describe() if age else command.age_description,
            age=age,
            age_recorded_on=now.date() if age else None,
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
                actor_scope=ActorScope(command.actor.role_scope),
                action="patients.created",
                entity_type="patient",
                entity_id=str(patient.id),
                after_state={
                    "name": patient.name,
                    "status": patient.status.value,
                    "clinic_id": str(patient.clinic_id) if patient.clinic_id else None,
                },
            )
        )

        return patient_to_dto(patient)
