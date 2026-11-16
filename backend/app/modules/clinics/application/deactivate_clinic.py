from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.clinics.application.dtos import ClinicDTO
from app.modules.clinics.application.mappers import clinic_to_dto
from app.modules.clinics.domain.repositories import ClinicRepository
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "clinics.manage"


@dataclass(frozen=True, kw_only=True)
class DeactivateClinicCommand:
    actor: ActorContext
    clinic_id: UUID


class DeactivateClinicUseCase:
    """Soft delete only — inactivating a clinic must never erase protocol
    history (rule: .claude/rules/01-product-domain.md, "Inative em vez de
    apagar")."""

    def __init__(
        self,
        *,
        clinics: ClinicRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._clinics = clinics
        self._audit = audit
        self._clock = clock

    def execute(self, command: DeactivateClinicCommand) -> ClinicDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        if not command.actor.can_access_clinic(command.clinic_id):
            raise NotFoundError("Clínica não encontrada.")
        clinic = self._clinics.get_by_id(command.clinic_id)
        if clinic is None:
            raise NotFoundError("Clínica não encontrada.")

        before_status = clinic.status.value
        clinic.deactivate(updated_by=command.actor.id, now=self._clock.now())
        self._clinics.save(clinic)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="clinics.deactivated",
                entity_type="clinic",
                entity_id=str(clinic.id),
                before_state={"status": before_status},
                after_state={"status": clinic.status.value},
            )
        )

        return clinic_to_dto(clinic)
