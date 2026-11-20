from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.patients.application.dtos import PatientDTO
from app.modules.patients.application.mappers import patient_to_dto
from app.modules.patients.domain.entities import Patient, PatientAge, PatientSex, PatientStatus
from app.modules.patients.domain.repositories import PatientRepository, SpeciesRepository
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError

_REQUIRED_PERMISSION = "patients.manage"


@dataclass(frozen=True, kw_only=True)
class UpdatePatientCommand:
    actor: ActorContext
    patient_id: UUID
    clinic_id: UUID | None = None
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
    age_value: int | None = None
    age_unit: str | None = None
    reason: str | None = None


# Contact and tax data of the tutor: the log says THAT it changed, never the value (PII).
_REDACTED_FIELDS = frozenset({"owner_phone", "owner_document"})
_REDACTED = "[alterado]"


def _audit_snapshot(patient: Patient) -> dict[str, object]:
    age = patient.age
    return {
        "name": patient.name,
        "species_id": str(patient.species_id),
        "sex": patient.sex.value,
        "breed": patient.breed,
        "age_description": patient.age_description,
        "age_value": age.value if age else None,
        "age_unit": age.unit.value if age else None,
        "owner_name": patient.owner_name,
        "owner_phone": patient.owner_phone,
        "owner_document": patient.owner_document,
        "status": patient.status.value,
        "notes": patient.notes,
        "clinic_id": str(patient.clinic_id) if patient.clinic_id else None,
    }


def _changed_fields(
    before: dict[str, object], after: dict[str, object]
) -> tuple[dict[str, object], dict[str, object]]:
    """Only the fields that changed, before and after, so the log answers "which data changed"."""
    changed = [field for field in after if before[field] != after[field]]

    def shown(state: dict[str, object], field: str) -> object:
        return _REDACTED if field in _REDACTED_FIELDS else state[field]

    return (
        {field: shown(before, field) for field in changed},
        {field: shown(after, field) for field in changed},
    )


class UpdatePatientUseCase:
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

    def execute(self, command: UpdatePatientCommand) -> PatientDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        patient = self._patients.get_by_id(command.patient_id, for_update=True)
        if patient is not None and not command.actor.can_access_clinic(patient.clinic_id):
            patient = None
        if patient is None:
            raise NotFoundError("Paciente não encontrado.")

        patient.ensure_editable()

        target_clinic_id = command.clinic_id or patient.clinic_id
        # Giving a clinic to a legacy patient that has none is not a clinic change: no reason needed.
        clinic_changed = patient.clinic_id is not None and target_clinic_id != patient.clinic_id
        reason = (command.reason or "").strip()
        # Existence and scope of the destination first (404 hides what the actor may not see),
        # then the missing reason (422).
        if not command.actor.can_access_clinic(target_clinic_id):
            raise NotFoundError("Clínica não encontrada.")
        if command.clinic_id is not None and (
            self._clinics is None or self._clinics.get_by_id(command.clinic_id) is None
        ):
            raise NotFoundError("Clínica não encontrada.")
        if clinic_changed and not reason:
            raise ValidationError("Informe o motivo da troca de clínica.")

        if patient.row_version != command.expected_row_version:
            raise ConflictError(
                "Este paciente foi alterado por outra pessoa. Recarregue e tente de novo."
            )

        known_species_ids = {species.id for species in self._species.list_all()}
        if command.species_id not in known_species_ids:
            raise NotFoundError("Espécie não encontrada.")

        before = _audit_snapshot(patient)

        patient.update_details(
            name=command.name,
            species_id=command.species_id,
            sex=PatientSex(command.sex),
            breed=command.breed,
            age_description=command.age_description,
            age=PatientAge.from_optional(command.age_value, command.age_unit),
            owner_name=command.owner_name,
            owner_phone=command.owner_phone,
            owner_document=command.owner_document,
            status=PatientStatus(command.status),
            notes=command.notes,
            clinic_id=target_clinic_id,
            updated_by=command.actor.id,
            now=self._clock.now(),
        )
        self._patients.save(patient)

        before_state, after_state = _changed_fields(before, _audit_snapshot(patient))
        if clinic_changed:
            after_state["reason"] = reason
        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="patients.updated",
                entity_type="patient",
                entity_id=str(patient.id),
                before_state=before_state,
                after_state=after_state,
            )
        )

        return patient_to_dto(patient)
