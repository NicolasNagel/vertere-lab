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
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "veterinarians.manage"


@dataclass(frozen=True, kw_only=True)
class DeactivateVeterinarianCommand:
    actor: ActorContext
    veterinarian_id: UUID


class DeactivateVeterinarianUseCase:
    """Soft delete only — inactivating a veterinarian must never erase
    protocol history (rule: .claude/rules/01-product-domain.md, "Inative em vez
    de apagar")."""

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

    def execute(self, command: DeactivateVeterinarianCommand) -> VeterinarianDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        veterinarian = self._veterinarians.get_by_id(command.veterinarian_id)
        if veterinarian is None:
            raise NotFoundError("Veterinário não encontrado.")
        ensure_veterinarian_visible(command.actor, veterinarian, self._veterinarians)
        ensure_veterinarian_mutable(command.actor, veterinarian, self._veterinarians)

        before_status = veterinarian.status.value
        veterinarian.deactivate(updated_by=command.actor.id, now=self._clock.now())
        self._veterinarians.save(veterinarian)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="veterinarians.deactivated",
                entity_type="veterinarian",
                entity_id=str(veterinarian.id),
                before_state={"status": before_status},
                after_state={"status": veterinarian.status.value},
            )
        )

        return veterinarian_to_dto(veterinarian)
