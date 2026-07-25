from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.veterinarians.application.dtos import VeterinarianDTO
from app.modules.veterinarians.application.mappers import veterinarian_to_dto
from app.modules.veterinarians.domain.entities import Veterinarian, VeterinarianStatus
from app.modules.veterinarians.domain.errors import DuplicateCrmvError
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.modules.veterinarians.domain.value_objects import Crmv
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "veterinarians.manage"


@dataclass(frozen=True, kw_only=True)
class CreateVeterinarianCommand:
    actor: AuthenticatedUserDTO
    name: str
    crmv: str
    phone: str | None
    email: str | None
    is_autonomous: bool
    notes: str | None


class CreateVeterinarianUseCase:
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

    def execute(self, command: CreateVeterinarianCommand) -> VeterinarianDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        crmv = Crmv(command.crmv)
        if self._veterinarians.get_by_crmv(str(crmv)) is not None:
            raise DuplicateCrmvError("CRMV já cadastrado para outro veterinário.")

        now = self._clock.now()
        veterinarian = Veterinarian(
            id=uuid4(),
            name=command.name,
            crmv=crmv,
            phone=command.phone,
            email=command.email,
            is_autonomous=command.is_autonomous,
            status=VeterinarianStatus.ACTIVE,
            notes=command.notes,
            created_by=command.actor.id,
            updated_by=command.actor.id,
            created_at=now,
            updated_at=now,
        )
        self._veterinarians.add(veterinarian)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="veterinarians.created",
                entity_type="veterinarian",
                entity_id=str(veterinarian.id),
                after_state={"name": veterinarian.name, "status": veterinarian.status.value},
            )
        )

        return veterinarian_to_dto(veterinarian)
