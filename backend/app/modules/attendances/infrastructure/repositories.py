"""SQLAlchemy implementation of the attendances repository protocols.

Domain entities are the only thing that crosses back out of this module;
ORM models never leak past this file (rule: .claude/rules/03-database.md).
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session as SqlAlchemySession
from sqlalchemy.orm import selectinload

from app.modules.attendances.domain.entities import (
    AttendanceExam,
    AttendanceExamStatus,
    AttendanceRecord,
    AttendanceStatus,
    CollectionMethod,
    ServiceLevel,
)
from app.modules.attendances.infrastructure.models import (
    AttendanceExamModel,
    AttendanceModel,
    AttendanceSequenceModel,
)
from app.modules.patients.infrastructure.models import PatientModel


def _item_to_domain(model: AttendanceExamModel) -> AttendanceExam:
    return AttendanceExam(
        id=model.id,
        attendance_id=model.attendance_id,
        exam_id=model.exam_id,
        exam_code=model.exam_code,
        exam_name=model.exam_name,
        price_base=model.price_base,
        quantity=model.quantity,
        discount_amount=model.discount_amount,
        surcharge_amount=model.surcharge_amount,
        override_reason=model.override_reason,
        override_by=model.override_by,
        status=AttendanceExamStatus(model.status),
    )


def _to_domain(model: AttendanceModel) -> AttendanceRecord:
    return AttendanceRecord(
        id=model.id,
        clinic_id=model.clinic_id,
        veterinarian_id=model.veterinarian_id,
        patient_id=model.patient_id,
        collection_method=CollectionMethod(model.collection_method),
        service_level=ServiceLevel(model.service_level),
        service_date=model.service_date,
        notes=model.notes,
        status=AttendanceStatus(model.status),
        items=[_item_to_domain(item) for item in model.items],
        billing_competence=model.billing_competence,
        subtotal=model.subtotal,
        discount_total=model.discount_total,
        surcharge_total=model.surcharge_total,
        grand_total=model.grand_total,
        protocol_year=model.protocol_year,
        protocol_sequence=model.protocol_sequence,
        protocol_number=model.protocol_number,
        monthly_closure_id=model.monthly_closure_id,
        cancel_reason=model.cancel_reason,
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
        model = self._session.execute(
            select(AttendanceModel)
            .where(AttendanceModel.id == attendance_id)
            .options(selectinload(AttendanceModel.items))
        ).scalar_one_or_none()
        return _to_domain(model) if model is not None else None

    def add(self, attendance: AttendanceRecord) -> None:
        self._session.add(
            AttendanceModel(
                id=attendance.id,
                clinic_id=attendance.clinic_id,
                veterinarian_id=attendance.veterinarian_id,
                patient_id=attendance.patient_id,
                collection_method=attendance.collection_method.value,
                service_level=attendance.service_level.value,
                service_date=attendance.service_date,
                notes=attendance.notes,
                status=attendance.status.value,
                billing_competence=attendance.billing_competence,
                subtotal=attendance.subtotal,
                discount_total=attendance.discount_total,
                surcharge_total=attendance.surcharge_total,
                grand_total=attendance.grand_total,
                protocol_year=attendance.protocol_year,
                protocol_sequence=attendance.protocol_sequence,
                protocol_number=attendance.protocol_number,
                monthly_closure_id=attendance.monthly_closure_id,
                cancel_reason=attendance.cancel_reason,
                created_by=attendance.created_by,
                updated_by=attendance.updated_by,
                created_at=attendance.created_at,
                updated_at=attendance.updated_at,
                row_version=attendance.row_version,
            )
        )

    def update(self, attendance: AttendanceRecord) -> None:
        model = self._session.execute(
            select(AttendanceModel)
            .where(AttendanceModel.id == attendance.id)
            .options(selectinload(AttendanceModel.items))
        ).scalar_one_or_none()
        if model is None:
            raise LookupError(f"Atendimento {attendance.id} não encontrado para atualização.")

        model.clinic_id = attendance.clinic_id
        model.veterinarian_id = attendance.veterinarian_id
        model.patient_id = attendance.patient_id
        model.collection_method = attendance.collection_method.value
        model.service_level = attendance.service_level.value
        model.service_date = attendance.service_date
        model.notes = attendance.notes
        model.status = attendance.status.value
        model.billing_competence = attendance.billing_competence
        model.subtotal = attendance.subtotal
        model.discount_total = attendance.discount_total
        model.surcharge_total = attendance.surcharge_total
        model.grand_total = attendance.grand_total
        model.protocol_year = attendance.protocol_year
        model.protocol_sequence = attendance.protocol_sequence
        model.protocol_number = attendance.protocol_number
        model.monthly_closure_id = attendance.monthly_closure_id
        model.cancel_reason = attendance.cancel_reason
        model.updated_by = attendance.updated_by
        model.updated_at = attendance.updated_at
        # `row_version` is NOT set here on purpose — `version_id_col` on
        # `AttendanceModel` (models.py) owns it: it compares the value this
        # `select()` just loaded against the DB at UPDATE time and bumps it
        # by one atomically. Assigning it manually would fight that check.

        # `update()` is called both right after items were freshly built
        # (confirm — `model.items` still empty) and when nothing about the
        # items changed at all (cancel — `attendance.items` is just what
        # was already loaded from the DB). Only append ids not already
        # persisted, or a cancel would re-insert the same rows and collide
        # on the primary key.
        existing_item_ids = {item.id for item in model.items}
        for item in attendance.items:
            if item.id in existing_item_ids:
                continue
            model.items.append(
                AttendanceExamModel(
                    id=item.id,
                    attendance_id=attendance.id,
                    exam_id=item.exam_id,
                    exam_code=item.exam_code,
                    exam_name=item.exam_name,
                    price_base=item.price_base,
                    quantity=item.quantity,
                    discount_amount=item.discount_amount,
                    surcharge_amount=item.surcharge_amount,
                    total_amount=item.total_amount,
                    override_reason=item.override_reason,
                    override_by=item.override_by,
                    status=item.status.value,
                )
            )

        # Force the UPDATE (and `version_id_col`'s bump) to run now, then
        # read the real post-write version back onto the domain object.
        # Without this, `attendance.row_version` stays whatever `get_by_id`
        # loaded before this write — the caller would hand a stale version
        # back to the client, who would then fail every subsequent edit
        # with a false `409` (`.claude/rules/05-frontend-web-mobile.md`: the version a
        # response carries must be the version that response actually
        # produced, not the one the request started from).
        self._session.flush()
        attendance.row_version = model.row_version

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        clinic_id: UUID | None,
        veterinarian_id: UUID | None,
        patient_id: UUID | None,
        status: AttendanceStatus | None,
        protocol_number: str | None,
        owner_name: str | None,
        service_date_from: date | None,
        service_date_to: date | None,
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
        if protocol_number:
            conditions.append(AttendanceModel.protocol_number.ilike(f"%{protocol_number.strip()}%"))
        if service_date_from is not None:
            conditions.append(AttendanceModel.service_date >= service_date_from)
        if service_date_to is not None:
            conditions.append(AttendanceModel.service_date <= service_date_to)

        count_stmt = select(func.count()).select_from(AttendanceModel)
        list_stmt = (
            select(AttendanceModel)
            .options(selectinload(AttendanceModel.items))
            .order_by(AttendanceModel.created_at.desc())
        )
        if owner_name:
            owner_condition = PatientModel.owner_name.ilike(f"%{owner_name.strip()}%")
            count_stmt = count_stmt.join(
                PatientModel, PatientModel.id == AttendanceModel.patient_id
            )
            list_stmt = list_stmt.join(PatientModel, PatientModel.id == AttendanceModel.patient_id)
            conditions.append(owner_condition)
        for condition in conditions:
            count_stmt = count_stmt.where(condition)
            list_stmt = list_stmt.where(condition)

        total = self._session.execute(count_stmt).scalar_one()
        list_stmt = list_stmt.offset((page - 1) * page_size).limit(page_size)
        models = self._session.execute(list_stmt).scalars().all()
        return [_to_domain(model) for model in models], total


class SqlAlchemyAttendanceSequenceRepository:
    """`SELECT ... FOR UPDATE` on the counter row for the year, inside the
    caller's transaction — never `MAX + 1` (`.claude/rules/03-database.md`).
    """

    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def next_sequence(self, year: int) -> int:
        model = self._session.execute(
            select(AttendanceSequenceModel)
            .where(AttendanceSequenceModel.year == year)
            .with_for_update()
        ).scalar_one_or_none()

        if model is None:
            model = AttendanceSequenceModel(year=year, last_sequence=0)
            self._session.add(model)
            self._session.flush()
            self._session.refresh(model, with_for_update=True)

        model.last_sequence += 1
        return model.last_sequence
