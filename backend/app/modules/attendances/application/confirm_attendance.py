"""Confirm a DRAFT attendance: revalidate every referenced id, snapshot exam
pricing into items, derive protocol and billing competence, transition to
CONFIRMED.

Every id is revalidated here even though already checked at draft creation
(`.claude/rules/attendence.md`: "todo ID é revalidado no momento da
confirmação"). `Idempotency-Key` is intentionally out of scope for this
slice — this endpoint has no UI yet, it only exists to give the closure
preview real data; see the plan's checkpoint 1 for the explicit deviation
from `.claude/rules/attendence.md`'s "Idempotency-Key obrigatória".
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.attendances.application.dtos import AttendanceDTO
from app.modules.attendances.application.mappers import attendance_to_dto
from app.modules.attendances.domain.entities import (
    AttendanceExam,
    AttendanceStatus,
)
from app.modules.attendances.domain.repositories import (
    AttendanceRepository,
    AttendanceSequenceRepository,
)
from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.domain.entities import ExamStatus
from app.modules.catalog.domain.repositories import ExamRepository
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

_REQUIRED_PERMISSION = "attendances.update"
_OVERRIDE_PERMISSION = "attendances.override_price"


@dataclass(frozen=True, kw_only=True)
class ConfirmAttendanceItemInput:
    exam_id: UUID
    quantity: int = 1
    discount_amount: Decimal | None = None
    override_reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class ConfirmAttendanceCommand:
    actor: AuthenticatedUserDTO
    attendance_id: UUID
    items: list[ConfirmAttendanceItemInput]


class ConfirmAttendanceUseCase:
    def __init__(
        self,
        *,
        attendances: AttendanceRepository,
        attendance_sequences: AttendanceSequenceRepository,
        clinics: ClinicRepository,
        veterinarians: VeterinarianRepository,
        veterinarian_clinics: VeterinarianClinicLinkRepository,
        patients: PatientRepository,
        exams: ExamRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._attendances = attendances
        self._attendance_sequences = attendance_sequences
        self._clinics = clinics
        self._veterinarians = veterinarians
        self._veterinarian_clinics = veterinarian_clinics
        self._patients = patients
        self._exams = exams
        self._audit = audit
        self._clock = clock

    def execute(self, command: ConfirmAttendanceCommand) -> AttendanceDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        attendance = self._attendances.get_by_id(command.attendance_id)
        if attendance is None:
            raise NotFoundError("Atendimento não encontrado.")
        if attendance.status != AttendanceStatus.DRAFT:
            raise ValidationError("Atendimento não está em rascunho.")
        if not command.items:
            raise ValidationError("Confirmação exige ao menos um item de exame.")
        if attendance.service_date is None:
            raise ValidationError("Data do atendimento é obrigatória para confirmar.")

        clinic = self._clinics.get_by_id(attendance.clinic_id)
        if clinic is None:
            raise NotFoundError("Clínica não encontrada.")
        if clinic.status != ClinicStatus.ACTIVE:
            raise ValidationError("Clínica não está ativa.")

        veterinarian = self._veterinarians.get_by_id(attendance.veterinarian_id)
        if veterinarian is None:
            raise NotFoundError("Veterinário não encontrado.")
        if veterinarian.status != VeterinarianStatus.ACTIVE:
            raise ValidationError("Veterinário não está ativo.")
        if not veterinarian.is_autonomous:
            link = self._veterinarian_clinics.get(attendance.veterinarian_id, attendance.clinic_id)
            if link is None:
                raise ValidationError("Veterinário não está vinculado a esta clínica.")

        patient = self._patients.get_by_id(attendance.patient_id)
        if patient is None:
            raise NotFoundError("Paciente não encontrado.")
        if patient.status != PatientStatus.ACTIVE:
            raise ValidationError("Paciente não está ativo.")

        before_state = {"status": attendance.status.value}

        items: list[AttendanceExam] = []
        for item_input in command.items:
            exam = self._exams.get_by_id(item_input.exam_id)
            if exam is None:
                raise NotFoundError("Exame não encontrado.")
            if exam.status != ExamStatus.ACTIVE:
                raise ValidationError("Exame não está ativo.")

            discount_amount = item_input.discount_amount or Decimal("0")
            override_reason: str | None = None
            override_by: UUID | None = None
            if discount_amount > 0:
                if _OVERRIDE_PERMISSION not in command.actor.permissions:
                    raise ForbiddenError(f"Permissão ausente: {_OVERRIDE_PERMISSION}")
                if not item_input.override_reason:
                    raise ValidationError("Override de preço exige motivo.")
                override_reason = item_input.override_reason
                override_by = command.actor.id

            items.append(
                AttendanceExam(
                    id=uuid4(),
                    attendance_id=attendance.id,
                    exam_id=exam.id,
                    exam_code=str(exam.code),
                    exam_name=exam.name,
                    price_base=exam.price_base,
                    quantity=item_input.quantity,
                    discount_amount=discount_amount,
                    # Plantão surcharge stays 0 in this slice — there is no
                    # field on AttendanceRecord to signal an on-call
                    # attendance yet (assumption declared in the plan).
                    surcharge_amount=Decimal("0"),
                    override_reason=override_reason,
                    override_by=override_by,
                )
            )

        now = self._clock.now()
        protocol_year = attendance.service_date.year
        protocol_sequence = self._attendance_sequences.next_sequence(protocol_year)

        attendance.confirm(
            items=items,
            protocol_year=protocol_year,
            protocol_sequence=protocol_sequence,
            now=now,
            confirmed_by=command.actor.id,
        )
        self._attendances.update(attendance)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="attendances.confirmed",
                entity_type="attendance",
                entity_id=str(attendance.id),
                before_state=before_state,
                after_state={
                    "status": attendance.status.value,
                    "protocol_number": attendance.protocol_number,
                    "grand_total": str(attendance.grand_total),
                },
            )
        )

        return attendance_to_dto(attendance)
