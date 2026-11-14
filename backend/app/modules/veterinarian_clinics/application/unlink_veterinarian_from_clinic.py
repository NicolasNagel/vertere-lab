from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.veterinarian_clinics.domain.errors import LastClinicLinkRequiredError
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.application.authorization import ActorContext
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "veterinarians.manage"


@dataclass(frozen=True, kw_only=True)
class UnlinkVeterinarianFromClinicCommand:
    actor: ActorContext
    veterinarian_id: UUID
    clinic_id: UUID


class UnlinkVeterinarianFromClinicUseCase:
    """Idempotent when the link doesn't exist — the desired end state (no
    link) is already true, so this is a no-op rather than a 404.

    Blocks removing the last remaining clinic of a non-autonomous
    veterinarian (assets/features/screens/spec-pages.md acceptance
    criterion: "veterinário não autônomo exige ao menos uma [clínica]").
    """

    def __init__(
        self,
        *,
        veterinarians: VeterinarianRepository,
        links: VeterinarianClinicLinkRepository,
        audit: AuditLogWriter,
    ) -> None:
        self._veterinarians = veterinarians
        self._links = links
        self._audit = audit

    def execute(self, command: UnlinkVeterinarianFromClinicCommand) -> None:
        if not command.actor.can_access_clinic(command.clinic_id):
            raise NotFoundError("Clínica não encontrada.")
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        veterinarian = self._veterinarians.get_by_id(command.veterinarian_id)
        if veterinarian is None:
            raise NotFoundError("Veterinário não encontrado.")

        link = self._links.get(command.veterinarian_id, command.clinic_id)
        if link is None:
            return

        if (
            not veterinarian.is_autonomous
            and self._links.count_by_veterinarian(command.veterinarian_id) <= 1
        ):
            raise LastClinicLinkRequiredError(
                "Veterinário não autônomo precisa de ao menos uma clínica vinculada."
            )

        self._links.delete(link)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="veterinarian_clinics.unlinked",
                entity_type="veterinarian_clinic_link",
                entity_id=str(link.id),
                before_state={
                    "veterinarian_id": str(command.veterinarian_id),
                    "clinic_id": str(command.clinic_id),
                },
            )
        )
