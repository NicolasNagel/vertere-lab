from __future__ import annotations

from app.modules.attendances.application.dtos import AttendanceDTO, AttendanceExamDTO
from app.modules.attendances.domain.entities import AttendanceExam, AttendanceRecord


def attendance_exam_to_dto(item: AttendanceExam) -> AttendanceExamDTO:
    return AttendanceExamDTO(
        id=item.id,
        exam_id=item.exam_id,
        exam_code=item.exam_code,
        exam_name=item.exam_name,
        price_base=item.price_base,
        quantity=item.quantity,
        discount_amount=item.discount_amount,
        surcharge_amount=item.surcharge_amount,
        total_amount=item.total_amount,
        override_reason=item.override_reason,
        status=item.status.value,
    )


def attendance_to_dto(attendance: AttendanceRecord) -> AttendanceDTO:
    return AttendanceDTO(
        id=attendance.id,
        clinic_id=attendance.clinic_id,
        veterinarian_id=attendance.veterinarian_id,
        patient_id=attendance.patient_id,
        service_date=attendance.service_date,
        notes=attendance.notes,
        status=attendance.status.value,
        items=[attendance_exam_to_dto(item) for item in attendance.items],
        billing_competence=attendance.billing_competence,
        subtotal=attendance.subtotal,
        discount_total=attendance.discount_total,
        surcharge_total=attendance.surcharge_total,
        grand_total=attendance.grand_total,
        protocol_number=attendance.protocol_number,
        cancel_reason=attendance.cancel_reason,
        created_at=attendance.created_at,
        updated_at=attendance.updated_at,
        row_version=attendance.row_version,
    )
