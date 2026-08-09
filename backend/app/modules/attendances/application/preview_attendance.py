"""Preview (dry-run) pricing for a DRAFT attendance — Fatia 2 of the
attendance plan checkpoint.

Reuses the exact same validation + snapshot logic as confirm
(`attendance_items.py`) and the exact same totals math
(`domain.entities.compute_attendance_totals`), so the number shown here can
never drift from what `/confirm` would actually charge
(`.claude/rules/05-frontend-web-mobile.md`: "tela de confirmação mostra... o total antes
do commit"; `.claude/rules/00-global.md`: "total sempre calculado no
backend"). Nothing is persisted: no `attendances.update`, no protocol
sequence consumed, no audit entry — a preview is not a commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.attendances.application.attendance_items import (
    AttendanceItemInput,
    resolve_on_call_fee,
    validate_and_snapshot_items,
)
from app.modules.attendances.application.dtos import AttendancePreviewDTO
from app.modules.attendances.application.mappers import attendance_exam_to_dto
from app.modules.attendances.domain.entities import AttendanceStatus, compute_attendance_totals
from app.modules.attendances.domain.repositories import (
    AttendanceRepository,
    OnCallFeeSettingRepository,
)
from app.modules.catalog.domain.repositories import ExamRepository
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.patients.domain.repositories import PatientRepository
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.application.authorization import ActorContext
from app.shared.domain.errors import ForbiddenError, NotFoundError, ValidationError

_REQUIRED_PERMISSION = "attendances.update"


@dataclass(frozen=True, kw_only=True)
class PreviewAttendanceCommand:
    actor: ActorContext
    attendance_id: UUID
    items: list[AttendanceItemInput]


class PreviewAttendanceUseCase:
    def __init__(
        self,
        *,
        attendances: AttendanceRepository,
        clinics: ClinicRepository,
        veterinarians: VeterinarianRepository,
        veterinarian_clinics: VeterinarianClinicLinkRepository,
        patients: PatientRepository,
        exams: ExamRepository,
        on_call_fees: OnCallFeeSettingRepository,
    ) -> None:
        self._attendances = attendances
        self._clinics = clinics
        self._veterinarians = veterinarians
        self._veterinarian_clinics = veterinarian_clinics
        self._patients = patients
        self._exams = exams
        self._on_call_fees = on_call_fees

    def execute(self, command: PreviewAttendanceCommand) -> AttendancePreviewDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        attendance = self._attendances.get_by_id(command.attendance_id)
        if attendance is None:
            raise NotFoundError("Atendimento não encontrado.")
        if attendance.status != AttendanceStatus.DRAFT:
            raise ValidationError("Atendimento não está em rascunho.")

        items = validate_and_snapshot_items(
            attendance=attendance,
            items=command.items,
            actor=command.actor,
            clinics=self._clinics,
            veterinarians=self._veterinarians,
            veterinarian_clinics=self._veterinarian_clinics,
            patients=self._patients,
            exams=self._exams,
        )
        on_call_fee = resolve_on_call_fee(
            service_level=attendance.service_level, on_call_fees=self._on_call_fees
        )
        totals = compute_attendance_totals(items, on_call_fee=on_call_fee)
        assert attendance.service_date is not None  # enforced by validate_and_snapshot_items

        return AttendancePreviewDTO(
            attendance_id=attendance.id,
            clinic_id=attendance.clinic_id,
            veterinarian_id=attendance.veterinarian_id,
            patient_id=attendance.patient_id,
            collection_method=attendance.collection_method.value,
            service_level=attendance.service_level.value,
            service_date=attendance.service_date,
            items=[attendance_exam_to_dto(item) for item in items],
            subtotal=totals.subtotal,
            discount_total=totals.discount_total,
            surcharge_total=totals.surcharge_total,
            on_call_fee=totals.on_call_fee,
            grand_total=totals.grand_total,
        )
