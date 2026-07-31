"""Controlled edit of a DRAFT or CONFIRMED attendance — Fatia 4 of the
attendance plan checkpoint (`PATCH /attendances/{id}`).

Two independent version checks exist on purpose:
1. `expected_row_version` here — compares what the *client* last saw
   against the current value, so a client editing a stale copy gets a
   clean, friendly `409 CONFLICT` (`.claude/rules/05-frontend-web-mobile.md`: "conflito
   de versão oferece recarregar, nunca sobrescreve silenciosamente"), even
   with no true concurrent request in flight.
2. `version_id_col` on `AttendanceModel` (infrastructure) — the low-level
   guard against two transactions racing on the *same* stale read, raised
   as `StaleDataError` and mapped to `409` in `api/error_handlers.py`
   (added in the cancel slice after a real race was found there).
Neither replaces the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.modules.attendances.application.dtos import AttendanceDTO
from app.modules.attendances.application.mappers import attendance_to_dto
from app.modules.attendances.application.party_validation import (
    validate_clinic_veterinarian_patient,
)
from app.modules.attendances.domain.entities import AttendanceStatus
from app.modules.attendances.domain.repositories import AttendanceRepository
from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.domain.repositories import PatientRepository
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.application.clock import Clock
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "attendances.update"


@dataclass(frozen=True, kw_only=True)
class UpdateAttendanceCommand:
    actor: AuthenticatedUserDTO
    attendance_id: UUID
    expected_row_version: int
    clinic_id: UUID | None = None
    veterinarian_id: UUID | None = None
    patient_id: UUID | None = None
    service_date: date | None = None
    notes: str | None = None


class UpdateAttendanceUseCase:
    def __init__(
        self,
        *,
        attendances: AttendanceRepository,
        clinics: ClinicRepository,
        veterinarians: VeterinarianRepository,
        veterinarian_clinics: VeterinarianClinicLinkRepository,
        patients: PatientRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._attendances = attendances
        self._clinics = clinics
        self._veterinarians = veterinarians
        self._veterinarian_clinics = veterinarian_clinics
        self._patients = patients
        self._audit = audit
        self._clock = clock

    def execute(self, command: UpdateAttendanceCommand) -> AttendanceDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        attendance = self._attendances.get_by_id(command.attendance_id)
        if attendance is None:
            raise NotFoundError("Atendimento não encontrado.")

        if command.expected_row_version != attendance.row_version:
            raise ConflictError(
                "O atendimento foi alterado por outra operação. Recarregue e tente novamente."
            )

        if attendance.status == AttendanceStatus.DRAFT and (
            command.clinic_id is not None
            or command.veterinarian_id is not None
            or command.patient_id is not None
        ):
            validate_clinic_veterinarian_patient(
                clinic_id=command.clinic_id or attendance.clinic_id,
                veterinarian_id=command.veterinarian_id or attendance.veterinarian_id,
                patient_id=command.patient_id or attendance.patient_id,
                clinics=self._clinics,
                veterinarians=self._veterinarians,
                veterinarian_clinics=self._veterinarian_clinics,
                patients=self._patients,
            )

        changes = attendance.update_fields(
            clinic_id=command.clinic_id,
            veterinarian_id=command.veterinarian_id,
            patient_id=command.patient_id,
            service_date=command.service_date,
            notes=command.notes,
            now=self._clock.now(),
            updated_by=command.actor.id,
        )

        if not changes:
            return attendance_to_dto(attendance)

        self._attendances.update(attendance)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="attendances.updated",
                entity_type="attendance",
                entity_id=str(attendance.id),
                before_state={field: before for field, (before, _after) in changes.items()},
                after_state={field: after for field, (_before, after) in changes.items()},
            )
        )

        return attendance_to_dto(attendance)
