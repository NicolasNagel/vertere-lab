"""SQLAlchemy implementation of the attendances repository protocols.

Domain entities are the only thing that crosses back out of this module;
ORM models never leak past this file (rule: .claude/rules/03-database.md).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
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
    ExamComponentSnapshot,
    OnCallFeeSetting,
    ServiceLevel,
)
from app.modules.attendances.infrastructure.models import (
    AttendanceExamModel,
    AttendanceModel,
    AttendanceSequenceModel,
    OnCallFeeSettingModel,
)
from app.modules.patients.infrastructure.models import PatientModel
from app.shared.infrastructure.sql import LIKE_ESCAPE, contains_pattern


def _components_to_json(item: AttendanceExam) -> list[dict[str, str]]:
    return [{"code": component.code, "name": component.name} for component in item.components]


def _item_to_domain(model: AttendanceExamModel) -> AttendanceExam:
    return AttendanceExam(
        id=model.id,
        attendance_id=model.attendance_id,
        exam_id=model.exam_id,
        exam_code=model.exam_code,
        exam_name=model.exam_name,
        price_base=model.price_base,
        components=tuple(
            ExamComponentSnapshot(code=component["code"], name=component["name"])
            for component in model.components_snapshot
        ),
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
        on_call_fee=model.on_call_fee,
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
        legacy_source_row_number=model.legacy_source_row_number,
        legacy_protocol_reference=model.legacy_protocol_reference,
        import_batch_id=model.import_batch_id,
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

    def get_by_legacy_source(
        self, *, import_batch_id: UUID, source_row_number: int
    ) -> AttendanceRecord | None:
        model = self._session.execute(
            select(AttendanceModel)
            .where(
                AttendanceModel.import_batch_id == import_batch_id,
                AttendanceModel.legacy_source_row_number == source_row_number,
            )
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
                on_call_fee=attendance.on_call_fee,
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
                legacy_source_row_number=attendance.legacy_source_row_number,
                legacy_protocol_reference=attendance.legacy_protocol_reference,
                import_batch_id=attendance.import_batch_id,
                # Only ever non-empty for a migrated record
                # (`AttendanceRecord.create_from_legacy_import`) — the live
                # draft→confirm flow always calls `add()` with `items=[]`
                # (drafting has none yet) and appends them later via
                # `update()`, so this has no effect there.
                items=[
                    AttendanceExamModel(
                        id=item.id,
                        attendance_id=attendance.id,
                        exam_id=item.exam_id,
                        exam_code=item.exam_code,
                        exam_name=item.exam_name,
                        price_base=item.price_base,
                        components_snapshot=_components_to_json(item),
                        quantity=item.quantity,
                        discount_amount=item.discount_amount,
                        surcharge_amount=item.surcharge_amount,
                        total_amount=item.total_amount,
                        override_reason=item.override_reason,
                        override_by=item.override_by,
                        status=item.status.value,
                    )
                    for item in attendance.items
                ],
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
        model.on_call_fee = attendance.on_call_fee
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
        existing_models = {item.id: item for item in model.items}
        for item in attendance.items:
            persisted = existing_models.get(item.id)
            if persisted is not None:
                # Corrected after confirmation: price/name snapshot stays, the rest follows.
                persisted.quantity = item.quantity
                persisted.discount_amount = item.discount_amount
                persisted.total_amount = item.total_amount
                persisted.override_reason = item.override_reason
                persisted.override_by = item.override_by
                persisted.status = item.status.value
                continue
            model.items.append(
                AttendanceExamModel(
                    id=item.id,
                    attendance_id=attendance.id,
                    exam_id=item.exam_id,
                    exam_code=item.exam_code,
                    exam_name=item.exam_name,
                    price_base=item.price_base,
                    components_snapshot=_components_to_json(item),
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

    def _filter_conditions(
        self,
        *,
        clinic_id: UUID | None,
        veterinarian_id: UUID | None,
        patient_id: UUID | None = None,
        status: AttendanceStatus | None = None,
        service_level: ServiceLevel | None,
        protocol_number: str | None,
        owner_name: str | None,
        service_date_from: date | None,
        service_date_to: date | None,
        clinic_ids: frozenset[UUID] | None = None,
    ) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if clinic_ids is not None:
            conditions.append(AttendanceModel.clinic_id.in_(clinic_ids))
        if clinic_id is not None:
            conditions.append(AttendanceModel.clinic_id == clinic_id)
        if veterinarian_id is not None:
            conditions.append(AttendanceModel.veterinarian_id == veterinarian_id)
        if patient_id is not None:
            conditions.append(AttendanceModel.patient_id == patient_id)
        if status is not None:
            conditions.append(AttendanceModel.status == status.value)
        if service_level is not None:
            conditions.append(AttendanceModel.service_level == service_level.value)
        if protocol_number:
            conditions.append(
                AttendanceModel.protocol_number.ilike(
                    contains_pattern(protocol_number.strip()), escape=LIKE_ESCAPE
                )
            )
        if service_date_from is not None:
            conditions.append(AttendanceModel.service_date >= service_date_from)
        if service_date_to is not None:
            conditions.append(AttendanceModel.service_date <= service_date_to)
        if owner_name:
            conditions.append(
                PatientModel.owner_name.ilike(
                    contains_pattern(owner_name.strip()), escape=LIKE_ESCAPE
                )
            )
        return conditions

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        clinic_id: UUID | None,
        veterinarian_id: UUID | None,
        patient_id: UUID | None,
        status: AttendanceStatus | None,
        service_level: ServiceLevel | None,
        protocol_number: str | None,
        owner_name: str | None,
        service_date_from: date | None,
        service_date_to: date | None,
        clinic_ids: frozenset[UUID] | None = None,
    ) -> tuple[list[AttendanceRecord], int]:
        conditions = self._filter_conditions(
            clinic_id=clinic_id,
            veterinarian_id=veterinarian_id,
            patient_id=patient_id,
            status=status,
            service_level=service_level,
            protocol_number=protocol_number,
            owner_name=owner_name,
            service_date_from=service_date_from,
            service_date_to=service_date_to,
            clinic_ids=clinic_ids,
        )

        count_stmt = select(func.count()).select_from(AttendanceModel)
        list_stmt = (
            select(AttendanceModel)
            .options(selectinload(AttendanceModel.items))
            .order_by(AttendanceModel.created_at.desc())
        )
        if owner_name:
            count_stmt = count_stmt.join(
                PatientModel, PatientModel.id == AttendanceModel.patient_id
            )
            list_stmt = list_stmt.join(PatientModel, PatientModel.id == AttendanceModel.patient_id)
        for condition in conditions:
            count_stmt = count_stmt.where(condition)
            list_stmt = list_stmt.where(condition)

        total = self._session.execute(count_stmt).scalar_one()
        list_stmt = list_stmt.offset((page - 1) * page_size).limit(page_size)
        models = self._session.execute(list_stmt).scalars().all()
        return [_to_domain(model) for model in models], total

    def count_by_status(
        self,
        *,
        clinic_id: UUID | None,
        veterinarian_id: UUID | None,
        service_level: ServiceLevel | None,
        protocol_number: str | None,
        owner_name: str | None,
        service_date_from: date | None,
        service_date_to: date | None,
        clinic_ids: frozenset[UUID] | None = None,
    ) -> dict[AttendanceStatus, int]:
        conditions = self._filter_conditions(
            clinic_id=clinic_id,
            veterinarian_id=veterinarian_id,
            service_level=service_level,
            protocol_number=protocol_number,
            owner_name=owner_name,
            service_date_from=service_date_from,
            service_date_to=service_date_to,
            clinic_ids=clinic_ids,
        )
        stmt = select(AttendanceModel.status, func.count()).group_by(AttendanceModel.status)
        if owner_name:
            stmt = stmt.join(PatientModel, PatientModel.id == AttendanceModel.patient_id)
        for condition in conditions:
            stmt = stmt.where(condition)
        rows = self._session.execute(stmt).all()
        return {AttendanceStatus(status): count for status, count in rows}

    def sum_billed_total(
        self,
        *,
        clinic_id: UUID | None,
        veterinarian_id: UUID | None,
        service_level: ServiceLevel | None,
        protocol_number: str | None,
        owner_name: str | None,
        service_date_from: date | None,
        service_date_to: date | None,
        clinic_ids: frozenset[UUID] | None = None,
    ) -> Decimal:
        conditions = self._filter_conditions(
            clinic_id=clinic_id,
            veterinarian_id=veterinarian_id,
            service_level=service_level,
            protocol_number=protocol_number,
            owner_name=owner_name,
            service_date_from=service_date_from,
            service_date_to=service_date_to,
            clinic_ids=clinic_ids,
        )
        stmt = select(func.coalesce(func.sum(AttendanceModel.grand_total), 0)).where(
            AttendanceModel.status.not_in(
                [AttendanceStatus.DRAFT.value, AttendanceStatus.CANCELLED.value]
            )
        )
        if owner_name:
            stmt = stmt.join(PatientModel, PatientModel.id == AttendanceModel.patient_id)
        for condition in conditions:
            stmt = stmt.where(condition)
        return Decimal(self._session.execute(stmt).scalar_one())


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


def _on_call_fee_setting_to_domain(model: OnCallFeeSettingModel) -> OnCallFeeSetting:
    return OnCallFeeSetting(
        id=model.id,
        service_level=ServiceLevel(model.service_level),
        fee_amount=model.fee_amount,
        schedule_label=model.schedule_label,
        updated_by=model.updated_by,
        updated_at=model.updated_at,
        row_version=model.row_version,
    )


class SqlAlchemyOnCallFeeSettingRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def get_by_service_level(self, service_level: ServiceLevel) -> OnCallFeeSetting | None:
        model = self._session.execute(
            select(OnCallFeeSettingModel).where(
                OnCallFeeSettingModel.service_level == service_level.value
            )
        ).scalar_one_or_none()
        return _on_call_fee_setting_to_domain(model) if model is not None else None

    def list_all(self) -> list[OnCallFeeSetting]:
        models = (
            self._session.execute(
                select(OnCallFeeSettingModel).order_by(OnCallFeeSettingModel.service_level)
            )
            .scalars()
            .all()
        )
        return [_on_call_fee_setting_to_domain(model) for model in models]

    def update(self, setting: OnCallFeeSetting) -> None:
        model = self._session.execute(
            select(OnCallFeeSettingModel).where(OnCallFeeSettingModel.id == setting.id)
        ).scalar_one_or_none()
        if model is None:
            raise LookupError(
                f"Configuração de taxa de plantão {setting.id} não encontrada para atualização."
            )
        model.fee_amount = setting.fee_amount
        model.schedule_label = setting.schedule_label
        model.updated_by = setting.updated_by

        # Same reasoning as SqlAlchemyAttendanceRepository.update() above:
        # force the UPDATE now so `version_id_col`'s bump is reflected back
        # onto the domain object the caller will hand to the API response.
        self._session.flush()
        setting.row_version = model.row_version
