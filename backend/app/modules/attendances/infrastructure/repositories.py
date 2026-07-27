"""SQLAlchemy implementation of the attendances repository protocol.

Domain entities are the only thing that crosses back out of this module;
ORM models never leak past this file (rule: .claude/rules/database.md).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session as SqlAlchemySession

from app.modules.attendances.domain.entities import AttendanceRecord, AttendanceStatus
from app.modules.attendances.infrastructure.models import AttendanceModel


def _to_domain(model: AttendanceModel) -> AttendanceRecord:
    return AttendanceRecord(
        id=model.id,
        clinic_id=model.clinic_id,
        veterinarian_id=model.veterinarian_id,
        patient_id=model.patient_id,
        service_date=model.service_date,
        notes=model.notes,
        status=AttendanceStatus(model.status),
        created_by=model.created_by,
        updated_by=model.updated_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
        row_version=model.row_version,
    )


class SqlAlchemyAttendanceRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def get_by_id(self, attendance_id: UUID) -> AttendanceRecord | None:
        model = self._session.get(AttendanceModel, attendance_id)
        return _to_domain(model) if model is not None else None

    def add(self, attendance: AttendanceRecord) -> None:
        self._session.add(
            AttendanceModel(
                id=attendance.id,
                clinic_id=attendance.clinic_id,
                veterinarian_id=attendance.veterinarian_id,
                patient_id=attendance.patient_id,
                service_date=attendance.service_date,
                notes=attendance.notes,
                status=attendance.status.value,
                created_by=attendance.created_by,
                updated_by=attendance.updated_by,
                created_at=attendance.created_at,
                updated_at=attendance.updated_at,
                row_version=attendance.row_version,
            )
        )

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        clinic_id: UUID | None,
        veterinarian_id: UUID | None,
        patient_id: UUID | None,
        status: AttendanceStatus | None,
    ) -> tuple[list[AttendanceRecord], int]:
        conditions: list[ColumnElement[bool]] = []
        if clinic_id is not None:
            conditions.append(AttendanceModel.clinic_id == clinic_id)
        if veterinarian_id is not None:
            conditions.append(AttendanceModel.veterinarian_id == veterinarian_id)
        if patient_id is not None:
            conditions.append(AttendanceModel.patient_id == patient_id)
        if status is not None:
            conditions.append(AttendanceModel.status == status.value)

        count_stmt = select(func.count()).select_from(AttendanceModel)
        list_stmt = select(AttendanceModel).order_by(AttendanceModel.created_at.desc())
        for condition in conditions:
            count_stmt = count_stmt.where(condition)
            list_stmt = list_stmt.where(condition)

        total = self._session.execute(count_stmt).scalar_one()
        list_stmt = list_stmt.offset((page - 1) * page_size).limit(page_size)
        models = self._session.execute(list_stmt).scalars().all()
        return [_to_domain(model) for model in models], total
