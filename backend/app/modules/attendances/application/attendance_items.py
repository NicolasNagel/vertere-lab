"""Shared item validation + pricing snapshot for `AttendanceRecord` —
used by both `confirm_attendance.py` and `preview_attendance.py` (Fatia 2)
so a preview total can never drift from what `/confirm` would actually
charge (rule: .claude/rules/12-attendance.md, "moeda e arredondamento
centralizados em um único ponto do domínio").

Every id is revalidated here even though already checked at draft creation
(`.claude/rules/12-attendance.md`: "todo ID é revalidado no momento da
confirmação") — a preview call revalidates for the same reason: another
user may have inactivated a referenced record since the draft was created.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.attendances.application.party_validation import (
    validate_clinic_veterinarian_patient,
)
from app.modules.attendances.domain.entities import AttendanceExam, AttendanceRecord
from app.modules.catalog.domain.entities import ExamStatus
from app.modules.catalog.domain.repositories import ExamRepository
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.domain.repositories import PatientRepository
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.domain.errors import ForbiddenError, NotFoundError, ValidationError

_OVERRIDE_PERMISSION = "attendances.override_price"


@dataclass(frozen=True, kw_only=True)
class AttendanceItemInput:
    exam_id: UUID
    quantity: int = 1
    discount_amount: Decimal | None = None
    override_reason: str | None = None


def validate_and_snapshot_items(
    *,
    attendance: AttendanceRecord,
    items: list[AttendanceItemInput],
    actor: AuthenticatedUserDTO,
    clinics: ClinicRepository,
    veterinarians: VeterinarianRepository,
    veterinarian_clinics: VeterinarianClinicLinkRepository,
    patients: PatientRepository,
    exams: ExamRepository,
) -> list[AttendanceExam]:
    if not items:
        raise ValidationError("Confirmação exige ao menos um item de exame.")
    if attendance.service_date is None:
        raise ValidationError("Data do atendimento é obrigatória para confirmar.")

    validate_clinic_veterinarian_patient(
        clinic_id=attendance.clinic_id,
        veterinarian_id=attendance.veterinarian_id,
        patient_id=attendance.patient_id,
        clinics=clinics,
        veterinarians=veterinarians,
        veterinarian_clinics=veterinarian_clinics,
        patients=patients,
    )

    built: list[AttendanceExam] = []
    for item_input in items:
        exam = exams.get_by_id(item_input.exam_id)
        if exam is None:
            raise NotFoundError("Exame não encontrado.")
        if exam.status != ExamStatus.ACTIVE:
            raise ValidationError("Exame não está ativo.")

        discount_amount = item_input.discount_amount or Decimal("0")
        override_reason: str | None = None
        override_by: UUID | None = None
        if discount_amount > 0:
            if _OVERRIDE_PERMISSION not in actor.permissions:
                raise ForbiddenError(f"Permissão ausente: {_OVERRIDE_PERMISSION}")
            if not item_input.override_reason:
                raise ValidationError("Override de preço exige motivo.")
            override_reason = item_input.override_reason
            override_by = actor.id

        built.append(
            AttendanceExam(
                id=uuid4(),
                attendance_id=attendance.id,
                exam_id=exam.id,
                exam_code=str(exam.code),
                exam_name=exam.name,
                price_base=exam.price_base,
                quantity=item_input.quantity,
                discount_amount=discount_amount,
                # Plantão surcharge stays 0 — there is no field on
                # AttendanceRecord to signal an on-call attendance yet
                # (same deviation already declared in the confirmation
                # slice).
                surcharge_amount=Decimal("0"),
                override_reason=override_reason,
                override_by=override_by,
            )
        )
    return built
