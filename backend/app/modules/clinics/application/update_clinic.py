from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.clinics.application.dtos import ClinicDTO
from app.modules.clinics.application.mappers import clinic_to_dto
from app.modules.clinics.domain.entities import ClinicStatus
from app.modules.clinics.domain.errors import DuplicateTaxIdError
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.clinics.domain.value_objects import TaxId
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "clinics.manage"


@dataclass(frozen=True, kw_only=True)
class UpdateClinicCommand:
    actor: ActorContext
    clinic_id: UUID
    name: str
    tax_id: str | None
    phone: str | None
    email: str | None
    status: str
    address_zip_code: str | None
    address_street: str | None
    address_number: str | None
    address_neighborhood: str | None
    address_city: str | None
    address_state: str | None
    address_complement: str | None
    notes: str | None
    expected_row_version: int


class UpdateClinicUseCase:
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

    def execute(self, command: UpdateClinicCommand) -> ClinicDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        if not command.actor.can_access_clinic(command.clinic_id):
            raise NotFoundError("Clínica não encontrada.")
        clinic = self._clinics.get_by_id(command.clinic_id)
        if clinic is None:
            raise NotFoundError("Clínica não encontrada.")

        if clinic.row_version != command.expected_row_version:
            raise ConflictError(
                "Esta clínica foi alterada por outra pessoa. Recarregue e tente de novo."
            )

        tax_id = TaxId(command.tax_id) if command.tax_id else None
        if tax_id is not None:
            existing = self._clinics.get_by_tax_id(str(tax_id))
            if existing is not None and existing.id != clinic.id:
                raise DuplicateTaxIdError("CNPJ já cadastrado para outra clínica.")

        before_state = {"name": clinic.name, "status": clinic.status.value}

        clinic.update_details(
            name=command.name,
            tax_id=tax_id,
            phone=command.phone,
            email=command.email,
            status=ClinicStatus(command.status),
            address_zip_code=command.address_zip_code,
            address_street=command.address_street,
            address_number=command.address_number,
            address_neighborhood=command.address_neighborhood,
            address_city=command.address_city,
            address_state=command.address_state,
            address_complement=command.address_complement,
            notes=command.notes,
            updated_by=command.actor.id,
            now=self._clock.now(),
        )
        self._clinics.save(clinic)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="clinics.updated",
                entity_type="clinic",
                entity_id=str(clinic.id),
                before_state=before_state,
                after_state={"name": clinic.name, "status": clinic.status.value},
            )
        )

        return clinic_to_dto(clinic)
