"""Read-only cross-module query: billing depends on attendances
conceptually (`docs/03-modelo-de-dominio.md` dependency graph, ATT -> CLOSE),
so reading `AttendanceModel`/`AttendanceExamModel` directly here is
acceptable for this derived, non-persisted preview. No write ever happens
from this module in this slice.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as SqlAlchemySession

from app.modules.attendances.infrastructure.models import AttendanceExamModel, AttendanceModel
from app.modules.billing.domain.entities import ClosureCandidateItem, CompetencePeriod
from app.modules.patients.infrastructure.models import PatientModel


class SqlAlchemyClosurePreviewRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def list_candidates(
        self, *, clinic_id: UUID, period: CompetencePeriod
    ) -> list[ClosureCandidateItem]:
        stmt = (
            select(AttendanceModel, AttendanceExamModel, PatientModel.name)
            .join(AttendanceExamModel, AttendanceExamModel.attendance_id == AttendanceModel.id)
            .join(PatientModel, PatientModel.id == AttendanceModel.patient_id)
            .where(
                AttendanceModel.clinic_id == clinic_id,
                AttendanceModel.billing_competence >= period.period_start,
                AttendanceModel.billing_competence <= period.period_end,
            )
        )
        rows = self._session.execute(stmt).all()
        return [
            ClosureCandidateItem(
                attendance_id=attendance.id,
                attendance_exam_id=exam_item.id,
                attendance_status=attendance.status,
                item_status=exam_item.status,
                billing_competence=attendance.billing_competence,
                monthly_closure_id=attendance.monthly_closure_id,
                protocol_number=attendance.protocol_number,
                patient_name=patient_name,
                exam_name=exam_item.exam_name,
                price_base=exam_item.price_base,
                quantity=exam_item.quantity,
                discount_amount=exam_item.discount_amount,
                surcharge_amount=exam_item.surcharge_amount,
                total_amount=exam_item.total_amount,
            )
            for attendance, exam_item, patient_name in rows
        ]
