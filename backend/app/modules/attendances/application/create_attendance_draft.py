"""Create an empty DRAFT AttendanceRecord.

Every referenced id is validated here — and must be revalidated again at
confirmation time (`.claude/rules/attendence.md`: "Todo ID é revalidado no
momento da confirmação, mesmo que já tenha sido validado ao selecionar").
This use case only covers the draft creation step.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

from app.modules.attendances.application.dtos import AttendanceDTO
from app.modules.attendances.application.mappers import attendance_to_dto
from app.modules.attendances.domain.entities import AttendanceRecord, AttendanceStatus
from app.modules.attendances.domain.repositories import AttendanceRepository
from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.clinics.domain.entities import ClinicStatus
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.domain.entities import PatientStatus
from app.modules.patients.domain.repositories import PatientRepository
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.entities import VeterinarianStatus
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError, ValidationError

_REQUIRED_PERMISSION = "attendances.create"


@dataclass(frozen=True, kw_only=True)
class CreateAttendanceDraftCommand:
    actor: AuthenticatedUserDTO
    clinic_id: UUID
    veterinarian_id: UUID
    patient_id: UUID
    service_date: date | None
    notes: str | None


class CreateAttendanceDraftUseCase:
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

    def execute(self, command: CreateAttendanceDraftCommand) -> AttendanceDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        clinic = self._clinics.get_by_id(command.clinic_id)
        if clinic is None:
            raise NotFoundError("Clínica não encontrada.")
        if clinic.status != ClinicStatus.ACTIVE:
            raise ValidationError("Clínica não está ativa.")

        veterinarian = self._veterinarians.get_by_id(command.veterinarian_id)
        if veterinarian is None:
            raise NotFoundError("Veterinário não encontrado.")
        if veterinarian.status != VeterinarianStatus.ACTIVE:
            raise ValidationError("Veterinário não está ativo.")
        if not veterinarian.is_autonomous:
            link = self._veterinarian_clinics.get(command.veterinarian_id, command.clinic_id)
            if link is None:
                raise ValidationError("Veterinário não está vinculado a esta clínica.")

        patient = self._patients.get_by_id(command.patient_id)
        if patient is None:
            raise NotFoundError("Paciente não encontrado.")
        if patient.status != PatientStatus.ACTIVE:
            raise ValidationError("Paciente não está ativo.")

        now = self._clock.now()
        attendance = AttendanceRecord(
            id=uuid4(),
            clinic_id=command.clinic_id,
            veterinarian_id=command.veterinarian_id,
            patient_id=command.patient_id,
            service_date=command.service_date,
            notes=command.notes,
            status=AttendanceStatus.DRAFT,
            created_by=command.actor.id,
            updated_by=command.actor.id,
            created_at=now,
            updated_at=now,
        )
        self._attendances.add(attendance)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="attendances.draft_created",
                entity_type="attendance",
                entity_id=str(attendance.id),
                after_state={
                    "clinic_id": str(attendance.clinic_id),
                    "veterinarian_id": str(attendance.veterinarian_id),
                    "patient_id": str(attendance.patient_id),
                    "status": attendance.status.value,
                },
            )
        )

        return attendance_to_dto(attendance)
