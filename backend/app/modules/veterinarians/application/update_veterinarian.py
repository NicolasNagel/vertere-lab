from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.veterinarians.application.dtos import VeterinarianDTO
from app.modules.veterinarians.application.mappers import veterinarian_to_dto
from app.modules.veterinarians.domain.entities import VeterinarianStatus
from app.modules.veterinarians.domain.errors import DuplicateCrmvError
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.modules.veterinarians.domain.value_objects import Crmv
from app.shared.application.clock import Clock
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "veterinarians.manage"


@dataclass(frozen=True, kw_only=True)
class UpdateVeterinarianCommand:
    actor: AuthenticatedUserDTO
    veterinarian_id: UUID
    name: str
    crmv: str
    phone: str | None
    email: str | None
    is_autonomous: bool
    status: str
    notes: str | None
    expected_row_version: int


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

        veterinarian = self._veterinarians.get_by_id(command.veterinarian_id)
        if veterinarian is None:
            raise NotFoundError("Veterinário não encontrado.")

        if veterinarian.row_version != command.expected_row_version:
            raise ConflictError(
                "Este veterinário foi alterado por outra pessoa. Recarregue e tente de novo."
            )

        crmv = Crmv(command.crmv)
        existing = self._veterinarians.get_by_crmv(str(crmv))
        if existing is not None and existing.id != veterinarian.id:
            raise DuplicateCrmvError("CRMV já cadastrado para outro veterinário.")

        before_state = {"name": veterinarian.name, "status": veterinarian.status.value}

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
                actor_scope=ActorScope.LAB,
                action="veterinarians.updated",
                entity_type="veterinarian",
                entity_id=str(veterinarian.id),
                before_state=before_state,
                after_state={"name": veterinarian.name, "status": veterinarian.status.value},
            )
        )

        return veterinarian_to_dto(veterinarian)
