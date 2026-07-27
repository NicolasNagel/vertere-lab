from __future__ import annotations

from app.modules.attendances.application.dtos import AttendanceDTO
from app.modules.attendances.domain.entities import AttendanceRecord


def attendance_to_dto(attendance: AttendanceRecord) -> AttendanceDTO:
    return AttendanceDTO(
        id=attendance.id,
        clinic_id=attendance.clinic_id,
        veterinarian_id=attendance.veterinarian_id,
        patient_id=attendance.patient_id,
        service_date=attendance.service_date,
        notes=attendance.notes,
        status=attendance.status.value,
        created_at=attendance.created_at,
        updated_at=attendance.updated_at,
        row_version=attendance.row_version,
    )
