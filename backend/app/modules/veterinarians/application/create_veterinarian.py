"""Create a Veterinarian, optionally linking it to clinics in the same
transaction.

Closes the gap documented in `docs/adr/003-veterinarios-crmv-e-layout.md`
("Onde a regra... é aplicada"): creating a non-autonomous veterinarian via
the API without any `clinic_ids` used to succeed silently, and the
"needs ≥1 clinic" rule was only enforced on unlink. Now it is enforced here
too, and the links are created atomically with the veterinarian (single
payload, single `uow`/transaction) instead of requiring a second API call
per clinic — see the ADR-003 addendum for the alternatives considered.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.veterinarian_clinics.domain.entities import VeterinarianClinicLink
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.application.dtos import VeterinarianDTO
from app.modules.veterinarians.application.mappers import veterinarian_to_dto
from app.modules.veterinarians.domain.entities import Veterinarian, VeterinarianStatus
from app.modules.veterinarians.domain.errors import DuplicateCrmvError
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.modules.veterinarians.domain.value_objects import Crmv
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError, ValidationError

_REQUIRED_PERMISSION = "veterinarians.manage"


@dataclass(frozen=True, kw_only=True)
class CreateVeterinarianCommand:
    actor: ActorContext
    name: str
    crmv: str
    phone: str | None
    email: str | None
    is_autonomous: bool
    notes: str | None
    clinic_ids: tuple[UUID, ...] = ()
    primary_clinic_id: UUID | None = None


class CreateVeterinarianUseCase:
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

    def execute(self, command: CreateVeterinarianCommand) -> VeterinarianDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        if command.is_autonomous and command.actor.clinic_filter is not None:
            raise ForbiddenError("Apenas o laboratório cadastra veterinário autônomo.")

        if not command.is_autonomous and not command.clinic_ids:
            raise ValidationError(
                "Veterinário não autônomo precisa de ao menos uma clínica vinculada."
            )

        if command.primary_clinic_id is not None and (
            command.primary_clinic_id not in command.clinic_ids
        ):
            raise ValidationError("A clínica principal precisa estar entre as clínicas vinculadas.")

        for clinic_id in command.clinic_ids:
            # A clinic-scope actor links only to its own clinics (404 hides the others).
            if not command.actor.can_access_clinic(clinic_id):
                raise NotFoundError("Clínica não encontrada.")
            if self._clinics.get_by_id(clinic_id) is None:
                raise NotFoundError("Clínica não encontrada.")

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
                actor_scope=ActorScope(command.actor.role_scope),
                action="veterinarians.created",
                entity_type="veterinarian",
                entity_id=str(veterinarian.id),
                after_state={"name": veterinarian.name, "status": veterinarian.status.value},
            )
        )

        primary_clinic_id = command.primary_clinic_id or (
            command.clinic_ids[0] if command.clinic_ids else None
        )
        for clinic_id in command.clinic_ids:
            link = VeterinarianClinicLink(
                id=uuid4(),
                veterinarian_id=veterinarian.id,
                clinic_id=clinic_id,
                primary_clinic=clinic_id == primary_clinic_id,
                created_by=command.actor.id,
                created_at=now,
            )
            self._links.add(link)
            self._audit.record(
                AuditEntry(
                    actor_user_id=command.actor.id,
                    actor_scope=ActorScope(command.actor.role_scope),
                    action="veterinarian_clinics.linked",
                    entity_type="veterinarian_clinic_link",
                    entity_id=str(link.id),
                    after_state={
                        "veterinarian_id": str(veterinarian.id),
                        "clinic_id": str(clinic_id),
                        "primary_clinic": str(link.primary_clinic),
                    },
                )
            )

        return veterinarian_to_dto(veterinarian)
