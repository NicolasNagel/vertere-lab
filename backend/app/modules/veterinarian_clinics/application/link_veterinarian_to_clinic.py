from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.veterinarian_clinics.domain.entities import VeterinarianClinicLink
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "veterinarians.manage"


@dataclass(frozen=True, kw_only=True)
class LinkVeterinarianToClinicCommand:
    actor: AuthenticatedUserDTO
    veterinarian_id: UUID
    clinic_id: UUID
    primary_clinic: bool


class LinkVeterinarianToClinicUseCase:
    """Idempotent: linking an already-linked (veterinarian, clinic) pair is a
    no-op, not an error — the caller only cares about the end state."""

    def __init__(
        self,
        *,
        veterinarians: VeterinarianRepository,
        clinics: ClinicRepository,
        links: VeterinarianClinicLinkRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._veterinarians = veterinarians
        self._clinics = clinics
        self._links = links
        self._audit = audit
        self._clock = clock

    def execute(self, command: LinkVeterinarianToClinicCommand) -> None:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        if self._veterinarians.get_by_id(command.veterinarian_id) is None:
            raise NotFoundError("Veterinário não encontrado.")
        if self._clinics.get_by_id(command.clinic_id) is None:
            raise NotFoundError("Clínica não encontrada.")

        existing = self._links.get(command.veterinarian_id, command.clinic_id)
        if existing is not None:
            return

        if command.primary_clinic:
            self._links.clear_primary_for_veterinarian(command.veterinarian_id)

        link = VeterinarianClinicLink(
            id=uuid4(),
            veterinarian_id=command.veterinarian_id,
            clinic_id=command.clinic_id,
            primary_clinic=command.primary_clinic,
            created_by=command.actor.id,
            created_at=self._clock.now(),
        )
        self._links.add(link)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="veterinarian_clinics.linked",
                entity_type="veterinarian_clinic_link",
                entity_id=str(link.id),
                after_state={
                    "veterinarian_id": str(command.veterinarian_id),
                    "clinic_id": str(command.clinic_id),
                    "primary_clinic": str(command.primary_clinic),
                },
            )
        )
