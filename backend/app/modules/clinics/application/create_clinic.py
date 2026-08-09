from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.clinics.application.dtos import ClinicDTO
from app.modules.clinics.application.mappers import clinic_to_dto
from app.modules.clinics.domain.entities import Clinic, ClinicStatus
from app.modules.clinics.domain.errors import DuplicateTaxIdError
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.clinics.domain.value_objects import TaxId
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "clinics.manage"


@dataclass(frozen=True, kw_only=True)
class CreateClinicCommand:
    actor: ActorContext
    name: str
    tax_id: str | None
    phone: str | None
    email: str | None
    address_zip_code: str | None
    address_street: str | None
    address_number: str | None
    address_neighborhood: str | None
    address_city: str | None
    address_state: str | None
    address_complement: str | None
    notes: str | None


class CreateClinicUseCase:
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

    def execute(self, command: CreateClinicCommand) -> ClinicDTO:
        if command.actor.role_scope == "CLINIC":
            raise ForbiddenError("Usuário de clínica não pode criar outra clínica.")
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        tax_id = TaxId(command.tax_id) if command.tax_id else None
        if tax_id is not None and self._clinics.get_by_tax_id(str(tax_id)) is not None:
            raise DuplicateTaxIdError("CNPJ já cadastrado para outra clínica.")

        now = self._clock.now()
        clinic = Clinic(
            id=uuid4(),
            name=command.name,
            tax_id=tax_id,
            phone=command.phone,
            email=command.email,
            status=ClinicStatus.ACTIVE,
            address_zip_code=command.address_zip_code,
            address_street=command.address_street,
            address_number=command.address_number,
            address_neighborhood=command.address_neighborhood,
            address_city=command.address_city,
            address_state=command.address_state,
            address_complement=command.address_complement,
            notes=command.notes,
            created_by=command.actor.id,
            updated_by=command.actor.id,
            created_at=now,
            updated_at=now,
        )
        self._clinics.add(clinic)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="clinics.created",
                entity_type="clinic",
                entity_id=str(clinic.id),
                after_state={"name": clinic.name, "status": clinic.status.value},
            )
        )

        return clinic_to_dto(clinic)
