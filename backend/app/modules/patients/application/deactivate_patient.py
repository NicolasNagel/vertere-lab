from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.patients.application.dtos import PatientDTO
from app.modules.patients.application.mappers import patient_to_dto
from app.modules.patients.domain.repositories import PatientRepository
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "patients.manage"


@dataclass(frozen=True, kw_only=True)
class DeactivatePatientCommand:
    actor: ActorContext
    patient_id: UUID


class DeactivatePatientUseCase:
    """Soft delete only — inactivating a patient must never erase protocol
    history (rule: .claude/rules/01-product-domain.md, "Inative em vez de
    apagar")."""

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

    def execute(self, command: DeactivatePatientCommand) -> PatientDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        patient = self._patients.get_by_id(command.patient_id)
        if patient is None or not command.actor.can_access_clinic(patient.clinic_id):
            raise NotFoundError("Paciente não encontrado.")

        before_status = patient.status.value
        patient.deactivate(updated_by=command.actor.id, now=self._clock.now())
        self._patients.save(patient)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="patients.deactivated",
                entity_type="patient",
                entity_id=str(patient.id),
                before_state={"status": before_status},
                after_state={"status": patient.status.value},
            )
        )

        return patient_to_dto(patient)
