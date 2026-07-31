"""Repositories for the billing module.

`SqlAlchemyClosurePreviewRepository` reads `AttendanceModel`/`AttendanceExamModel`
directly — billing depends on attendances conceptually
(`docs/03-modelo-de-dominio.md` dependency graph, ATT -> CLOSE), and the
preview is derived, never persisted, so this is acceptable for that one
read. `SqlAlchemyMonthlyClosureRepository` (Incremento 4.2) is the first
writer in this module.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Row, Select, func, select, text, update
from sqlalchemy.orm import Session as SqlAlchemySession
from sqlalchemy.orm import selectinload

from app.modules.attendances.infrastructure.models import AttendanceExamModel, AttendanceModel
from app.modules.billing.domain.entities import (
    AdjustmentKind,
    ClosureCandidateItem,
    ClosureStatus,
    CompetencePeriod,
    FinancialAdjustment,
    MonthlyClosure,
    MonthlyClosureItem,
)
from app.modules.billing.infrastructure.models import (
    FinancialAdjustmentModel,
    MonthlyClosureItemModel,
    MonthlyClosureModel,
)
from app.modules.patients.infrastructure.models import PatientModel


def _candidates_query(
    *, clinic_id: UUID, period: CompetencePeriod
) -> Select[tuple[AttendanceModel, AttendanceExamModel, str]]:
    return (
        select(AttendanceModel, AttendanceExamModel, PatientModel.name)
        .join(AttendanceExamModel, AttendanceExamModel.attendance_id == AttendanceModel.id)
        .join(PatientModel, PatientModel.id == AttendanceModel.patient_id)
        .where(
            AttendanceModel.clinic_id == clinic_id,
            AttendanceModel.billing_competence >= period.period_start,
            AttendanceModel.billing_competence <= period.period_end,
        )
    )


def _rows_to_candidates(
    rows: Sequence[Row[tuple[AttendanceModel, AttendanceExamModel, str]]],
) -> list[ClosureCandidateItem]:
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


class SqlAlchemyClosurePreviewRepository:
    """Also implements `ClosureCandidateLockRepository` structurally (no
    explicit inheritance needed, `Protocol` is duck-typed) — same query,
    same class, but `list_candidates_for_update`/`mark_associated_with_closure`
    are only ever called by the close use case, never by the read-only
    prévia."""

    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def list_candidates(
        self, *, clinic_id: UUID, period: CompetencePeriod
    ) -> list[ClosureCandidateItem]:
        rows = self._session.execute(_candidates_query(clinic_id=clinic_id, period=period)).all()
        return _rows_to_candidates(rows)

    def list_candidates_for_update(
        self, *, clinic_id: UUID, period: CompetencePeriod
    ) -> list[ClosureCandidateItem]:
        stmt = _candidates_query(clinic_id=clinic_id, period=period).with_for_update(
            of=[AttendanceModel, AttendanceExamModel]
        )
        rows = self._session.execute(stmt).all()
        return _rows_to_candidates(rows)

    def mark_associated_with_closure(self, *, attendance_ids: set[UUID], closure_id: UUID) -> None:
        if not attendance_ids:
            return
        self._session.execute(
            update(AttendanceModel)
            .where(AttendanceModel.id.in_(attendance_ids))
            .values(monthly_closure_id=closure_id)
        )

    def release_from_closure(self, *, closure_id: UUID) -> None:
        self._session.execute(
            update(AttendanceModel)
            .where(AttendanceModel.monthly_closure_id == closure_id)
            .values(monthly_closure_id=None)
        )


def _item_to_domain(model: MonthlyClosureItemModel) -> MonthlyClosureItem:
    return MonthlyClosureItem(
        id=model.id,
        monthly_closure_id=model.monthly_closure_id,
        attendance_id=model.attendance_id,
        attendance_exam_id=model.attendance_exam_id,
        protocol_number=model.protocol_number,
        patient_name=model.patient_name,
        exam_name=model.exam_name,
        price_base=model.price_base,
        quantity=model.quantity,
        discount_amount=model.discount_amount,
        surcharge_amount=model.surcharge_amount,
        total_amount=model.total_amount,
    )


def _adjustment_to_domain(model: FinancialAdjustmentModel) -> FinancialAdjustment:
    return FinancialAdjustment(
        id=model.id,
        monthly_closure_id=model.monthly_closure_id,
        monthly_closure_item_id=model.monthly_closure_item_id,
        kind=AdjustmentKind(model.kind),
        amount=model.amount,
        reason=model.reason,
        created_by=model.created_by,
        created_at=model.created_at,
    )


def _closure_to_domain(model: MonthlyClosureModel) -> MonthlyClosure:
    return MonthlyClosure(
        id=model.id,
        clinic_id=model.clinic_id,
        competence_year=model.competence_year,
        competence_month=model.competence_month,
        period_start=model.period_start,
        period_end=model.period_end,
        status=ClosureStatus(model.status),
        item_count=model.item_count,
        subtotal=model.subtotal,
        discount_total=model.discount_total,
        surcharge_total=model.surcharge_total,
        grand_total=model.grand_total,
        generated_by=model.generated_by,
        closed_by=model.closed_by,
        generated_at=model.generated_at,
        closed_at=model.closed_at,
        reopened_at=model.reopened_at,
        version=model.version,
        integrity_hash=model.integrity_hash,
        items=[_item_to_domain(item) for item in model.items],
        adjustments=[_adjustment_to_domain(item) for item in model.adjustments],
    )


class SqlAlchemyMonthlyClosureRepository:
    """Every read goes through `selectinload(items)` — a closure without its
    items is never a valid `MonthlyClosure` to hand back (`__post_init__`
    checks `item_count == len(items)`), so lazy-loading them later inside a
    response serializer would risk the "lazy load vazando pro response" the
    rule explicitly forbids (`.claude/rules/03-database.md`)."""

    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def acquire_active_lock(self, *, clinic_id: UUID, year: int, month: int) -> None:
        # Two independent int4 keys, not one hashed bigint: the period key
        # is exact (never collides), only the clinic-id hash could theoretically
        # collide — and a collision there only serializes two unrelated
        # closes for a moment, it never lets a wrong pair through
        # (`.claude/rules/03-database.md`: "advisory lock transacional...
        # por clínica + competência").
        self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:clinic_key), :period_key)"),
            {"clinic_key": str(clinic_id), "period_key": year * 100 + month},
        )

    def get_active_for_clinic_and_period(
        self, *, clinic_id: UUID, year: int, month: int
    ) -> MonthlyClosure | None:
        model = self._session.execute(
            select(MonthlyClosureModel)
            .options(selectinload(MonthlyClosureModel.items))
            .options(selectinload(MonthlyClosureModel.adjustments))
            .where(
                MonthlyClosureModel.clinic_id == clinic_id,
                MonthlyClosureModel.competence_year == year,
                MonthlyClosureModel.competence_month == month,
                MonthlyClosureModel.status == ClosureStatus.CLOSED.value,
            )
        ).scalar_one_or_none()
        return _closure_to_domain(model) if model is not None else None

    def add(self, closure: MonthlyClosure) -> None:
        self._session.add(
            MonthlyClosureModel(
                id=closure.id,
                clinic_id=closure.clinic_id,
                competence_year=closure.competence_year,
                competence_month=closure.competence_month,
                period_start=closure.period_start,
                period_end=closure.period_end,
                status=closure.status.value,
                item_count=closure.item_count,
                subtotal=closure.subtotal,
                discount_total=closure.discount_total,
                surcharge_total=closure.surcharge_total,
                grand_total=closure.grand_total,
                generated_by=closure.generated_by,
                closed_by=closure.closed_by,
                generated_at=closure.generated_at,
                closed_at=closure.closed_at,
                reopened_at=closure.reopened_at,
                version=closure.version,
                integrity_hash=closure.integrity_hash,
                items=[
                    MonthlyClosureItemModel(
                        id=item.id,
                        monthly_closure_id=item.monthly_closure_id,
                        attendance_id=item.attendance_id,
                        attendance_exam_id=item.attendance_exam_id,
                        protocol_number=item.protocol_number,
                        patient_name=item.patient_name,
                        exam_name=item.exam_name,
                        price_base=item.price_base,
                        quantity=item.quantity,
                        discount_amount=item.discount_amount,
                        surcharge_amount=item.surcharge_amount,
                        total_amount=item.total_amount,
                    )
                    for item in closure.items
                ],
            )
        )

    def get_by_id(self, closure_id: UUID) -> MonthlyClosure | None:
        model = self._session.execute(
            select(MonthlyClosureModel)
            .options(selectinload(MonthlyClosureModel.items))
            .options(selectinload(MonthlyClosureModel.adjustments))
            .where(MonthlyClosureModel.id == closure_id)
        ).scalar_one_or_none()
        return _closure_to_domain(model) if model is not None else None

    def get_by_id_for_update(self, closure_id: UUID) -> MonthlyClosure | None:
        model = self._session.execute(
            select(MonthlyClosureModel)
            .options(selectinload(MonthlyClosureModel.items))
            .options(selectinload(MonthlyClosureModel.adjustments))
            .where(MonthlyClosureModel.id == closure_id)
            .with_for_update()
        ).scalar_one_or_none()
        return _closure_to_domain(model) if model is not None else None

    def get_latest_for_clinic_and_period(
        self, *, clinic_id: UUID, year: int, month: int
    ) -> MonthlyClosure | None:
        model = self._session.execute(
            select(MonthlyClosureModel)
            .options(selectinload(MonthlyClosureModel.items))
            .options(selectinload(MonthlyClosureModel.adjustments))
            .where(
                MonthlyClosureModel.clinic_id == clinic_id,
                MonthlyClosureModel.competence_year == year,
                MonthlyClosureModel.competence_month == month,
            )
            .order_by(MonthlyClosureModel.version.desc())
            .limit(1)
        ).scalar_one_or_none()
        return _closure_to_domain(model) if model is not None else None

    def update_status(self, closure: MonthlyClosure) -> None:
        self._session.execute(
            update(MonthlyClosureModel)
            .where(MonthlyClosureModel.id == closure.id)
            .values(status=closure.status.value, reopened_at=closure.reopened_at)
        )

    def add_adjustment(self, adjustment: FinancialAdjustment) -> None:
        self._session.add(
            FinancialAdjustmentModel(
                id=adjustment.id,
                monthly_closure_id=adjustment.monthly_closure_id,
                monthly_closure_item_id=adjustment.monthly_closure_item_id,
                kind=adjustment.kind.value,
                amount=adjustment.amount,
                reason=adjustment.reason,
                created_by=adjustment.created_by,
                created_at=adjustment.created_at,
            )
        )

    def list_page(
        self, *, clinic_id: UUID | None, page: int, page_size: int
    ) -> tuple[list[MonthlyClosure], int]:
        stmt = select(MonthlyClosureModel).options(selectinload(MonthlyClosureModel.items))
        stmt = stmt.options(selectinload(MonthlyClosureModel.adjustments))
        count_stmt = select(func.count()).select_from(MonthlyClosureModel)
        if clinic_id is not None:
            stmt = stmt.where(MonthlyClosureModel.clinic_id == clinic_id)
            count_stmt = count_stmt.where(MonthlyClosureModel.clinic_id == clinic_id)

        total = self._session.execute(count_stmt).scalar_one()
        models = (
            self._session.execute(
                stmt.order_by(MonthlyClosureModel.closed_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        return [_closure_to_domain(model) for model in models], total
