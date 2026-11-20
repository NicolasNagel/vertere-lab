from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.veterinarians.application.dtos import VeterinarianDTO
from app.modules.veterinarians.application.mappers import veterinarian_to_dto
from app.modules.veterinarians.application.visibility import (
    ensure_veterinarian_mutable,
    ensure_veterinarian_visible,
)
from app.modules.veterinarians.domain.entities import Veterinarian, VeterinarianStatus
from app.modules.veterinarians.domain.errors import DuplicateCrmvError
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.modules.veterinarians.domain.value_objects import Crmv
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError

_REQUIRED_PERMISSION = "veterinarians.manage"


@dataclass(frozen=True, kw_only=True)
class UpdateVeterinarianCommand:
    actor: ActorContext
    veterinarian_id: UUID
    name: str
    crmv: str
    phone: str | None
    email: str | None
    is_autonomous: bool
    status: str
    notes: str | None
    expected_row_version: int
    reason: str


def _audit_state(veterinarian: Veterinarian) -> dict[str, str | bool | None]:
    """Before/after of a correction. Phone and e-mail are PII: only whether they are set is kept."""
    return {
        "name": veterinarian.name,
        "crmv": str(veterinarian.crmv),
        "is_autonomous": veterinarian.is_autonomous,
        "status": veterinarian.status.value,
        "notes": veterinarian.notes,
        "has_phone": veterinarian.phone is not None,
        "has_email": veterinarian.email is not None,
    }


class UpdateVeterinarianUseCase:
    def __init__(
        self,
        *,
        veterinarians: VeterinarianRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._veterinarians = veterinarians
        self._audit = audit
        self._clock = clock

    def execute(self, command: UpdateVeterinarianCommand) -> VeterinarianDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        reason = command.reason.strip()
        if not reason:
            raise ValidationError("Informe o motivo da alteração.")

        veterinarian = self._veterinarians.get_by_id(command.veterinarian_id)
        if veterinarian is None:
            raise NotFoundError("Veterinário não encontrado.")
        ensure_veterinarian_visible(command.actor, veterinarian, self._veterinarians)
        ensure_veterinarian_mutable(command.actor, veterinarian, self._veterinarians)
        if (
            command.actor.clinic_filter is not None
            and command.is_autonomous != veterinarian.is_autonomous
        ):
            raise ForbiddenError("Apenas o laboratório altera a condição de autônomo.")

        if veterinarian.row_version != command.expected_row_version:
            raise ConflictError(
                "Este veterinário foi alterado por outra pessoa. Recarregue e tente de novo."
            )

        crmv = Crmv(command.crmv)
        existing = self._veterinarians.get_by_crmv(str(crmv))
        if existing is not None and existing.id != veterinarian.id:
            raise DuplicateCrmvError("CRMV já cadastrado para outro veterinário.")

        before_state = _audit_state(veterinarian)

        veterinarian.update_details(
            name=command.name,
            crmv=crmv,
            phone=command.phone,
            email=command.email,
            is_autonomous=command.is_autonomous,
            status=VeterinarianStatus(command.status),
            notes=command.notes,
            updated_by=command.actor.id,
            now=self._clock.now(),
        )
        self._veterinarians.save(veterinarian)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="veterinarians.updated",
                entity_type="veterinarian",
                entity_id=str(veterinarian.id),
                before_state=before_state,
                after_state=_audit_state(veterinarian),
                reason=reason,
            )
        )

        return veterinarian_to_dto(veterinarian)
