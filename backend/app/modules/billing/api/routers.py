"""Billing API — thin router, no business rule (rule:
.claude/rules/02-backend.md).

`GET /closures/preview` is read-only, no UoW. `POST /closures` (Incremento
4.2) is the first writer — wrapped in a unit of work and an
`Idempotency-Key` guard, same shape as `POST /attendances/{id}/confirm`.
`GET /closures`, `GET /closures/{id}` and `GET /closures/{id}/export`
(Fatia C) are read-only again — always from the persisted snapshot, never
recomputed.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.orm import Session as SqlAlchemySession

from app.api.dependencies import get_session, get_unit_of_work
from app.modules.audit.infrastructure.repositories import SqlAlchemyAuditLogWriter
from app.modules.billing.api.schemas import (
    CloseMonthlyPeriodRequest,
    ClosurePreviewBlockedItemRead,
    ClosurePreviewItemRead,
    ClosurePreviewResponse,
    FinancialAdjustmentCreateRequest,
    FinancialAdjustmentRead,
    MonthlyClosureItemRead,
    MonthlyClosureListResponse,
    MonthlyClosureRead,
    MonthlyClosureSummaryRead,
    ReopenMonthlyClosureRequest,
)
from app.modules.billing.application.add_financial_adjustment import (
    AddFinancialAdjustmentCommand,
    AddFinancialAdjustmentUseCase,
)
from app.modules.billing.application.close_monthly_period import (
    CloseMonthlyPeriodCommand,
    CloseMonthlyPeriodUseCase,
)
from app.modules.billing.application.dtos import (
    ClosurePreviewDTO,
    FinancialAdjustmentDTO,
    MonthlyClosureDTO,
    MonthlyClosurePageDTO,
)
from app.modules.billing.application.export_monthly_closure import monthly_closure_to_csv
from app.modules.billing.application.get_closure_by_period import (
    GetClosureByPeriodQuery,
    GetClosureByPeriodUseCase,
)
from app.modules.billing.application.get_monthly_closure import (
    GetMonthlyClosureQuery,
    GetMonthlyClosureUseCase,
)
from app.modules.billing.application.list_monthly_closures import (
    ListMonthlyClosuresQuery,
    ListMonthlyClosuresUseCase,
)
from app.modules.billing.application.preview_closure import (
    PreviewClosureQuery,
    PreviewClosureUseCase,
)
from app.modules.billing.application.reopen_monthly_closure import (
    ReopenMonthlyClosureCommand,
    ReopenMonthlyClosureUseCase,
)
from app.modules.billing.domain.entities import AdjustmentKind
from app.modules.billing.infrastructure.repositories import (
    SqlAlchemyClosurePreviewRepository,
    SqlAlchemyMonthlyClosureRepository,
)
from app.modules.clinics.infrastructure.repositories import SqlAlchemyClinicRepository
from app.modules.identity.api.dependencies import require_permission
from app.shared.application.authorization import ActorContext
from app.shared.idempotency.application.guard import IdempotencyGuard
from app.shared.idempotency.infrastructure.repositories import SqlAlchemyIdempotencyRecordRepository
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork
from app.shared.outbox.infrastructure.repositories import SqlAlchemyOutboxEventRepository

router = APIRouter(prefix="/closures", tags=["billing"])


def _financial_adjustment_read(dto: FinancialAdjustmentDTO) -> FinancialAdjustmentRead:
    return FinancialAdjustmentRead(
        id=dto.id,
        monthly_closure_id=dto.monthly_closure_id,
        monthly_closure_item_id=dto.monthly_closure_item_id,
        kind=dto.kind,
        amount=dto.amount,
        reason=dto.reason,
        created_by=dto.created_by,
        created_at=dto.created_at,
    )


def _closure_preview_read(dto: ClosurePreviewDTO) -> ClosurePreviewResponse:
    return ClosurePreviewResponse(
        clinic_id=dto.clinic_id,
        competence_year=dto.competence_year,
        competence_month=dto.competence_month,
        period_start=dto.period_start,
        period_end=dto.period_end,
        attendance_count=dto.attendance_count,
        cancelled_attendance_count=dto.cancelled_attendance_count,
        item_count=dto.item_count,
        subtotal=dto.subtotal,
        discount_total=dto.discount_total,
        surcharge_total=dto.surcharge_total,
        on_call_fee_total=dto.on_call_fee_total,
        grand_total=dto.grand_total,
        eligible_items=[
            ClosurePreviewItemRead(
                attendance_id=item.attendance_id,
                attendance_exam_id=item.attendance_exam_id,
                protocol_number=item.protocol_number,
                patient_name=item.patient_name,
                exam_name=item.exam_name,
                service_level=item.service_level,
                exam_category=item.exam_category,
                total_amount=item.total_amount,
            )
            for item in dto.eligible_items
        ],
        blocked_items=[
            ClosurePreviewBlockedItemRead(
                attendance_id=item.attendance_id,
                attendance_exam_id=item.attendance_exam_id,
                protocol_number=item.protocol_number,
                patient_name=item.patient_name,
                exam_name=item.exam_name,
                total_amount=item.total_amount,
                reason=item.reason,
            )
            for item in dto.blocked_items
        ],
        generated_at=dto.generated_at,
    )


def _monthly_closure_read(dto: MonthlyClosureDTO) -> MonthlyClosureRead:
    return MonthlyClosureRead(
        id=dto.id,
        clinic_id=dto.clinic_id,
        competence_year=dto.competence_year,
        competence_month=dto.competence_month,
        period_start=dto.period_start,
        period_end=dto.period_end,
        status=dto.status,
        item_count=dto.item_count,
        subtotal=dto.subtotal,
        discount_total=dto.discount_total,
        surcharge_total=dto.surcharge_total,
        on_call_fee_total=dto.on_call_fee_total,
        grand_total=dto.grand_total,
        generated_by=dto.generated_by,
        closed_by=dto.closed_by,
        generated_at=dto.generated_at,
        closed_at=dto.closed_at,
        reopened_at=dto.reopened_at,
        version=dto.version,
        items=[
            MonthlyClosureItemRead(
                id=item.id,
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
                service_level=item.service_level,
                exam_category=item.exam_category,
            )
            for item in dto.items
        ],
        adjustments=[_financial_adjustment_read(item) for item in dto.adjustments],
    )


def _monthly_closure_summary_read(dto: MonthlyClosureDTO) -> MonthlyClosureSummaryRead:
    return MonthlyClosureSummaryRead(
        id=dto.id,
        clinic_id=dto.clinic_id,
        competence_year=dto.competence_year,
        competence_month=dto.competence_month,
        period_start=dto.period_start,
        period_end=dto.period_end,
        status=dto.status,
        item_count=dto.item_count,
        grand_total=dto.grand_total,
        closed_by=dto.closed_by,
        closed_at=dto.closed_at,
        version=dto.version,
    )


def _monthly_closure_page_read(dto: MonthlyClosurePageDTO) -> MonthlyClosureListResponse:
    return MonthlyClosureListResponse(
        items=[_monthly_closure_summary_read(item) for item in dto.items],
        total=dto.total,
        page=dto.page,
        page_size=dto.page_size,
    )


@router.get("/preview", response_model=ClosurePreviewResponse)
def preview_closure(
    clinic_id: UUID = Query(...),
    period_start: date = Query(...),
    period_end: date = Query(...),
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("closures.preview")),
) -> ClosurePreviewResponse:
    use_case = PreviewClosureUseCase(
        clinics=SqlAlchemyClinicRepository(session),
        candidates=SqlAlchemyClosurePreviewRepository(session),
        clock=SystemClock(),
    )
    result = use_case.execute(
        PreviewClosureQuery(
            actor=current_user,
            clinic_id=clinic_id,
            period_start=period_start,
            period_end=period_end,
        )
    )
    return _closure_preview_read(result)


@router.post("", response_model=MonthlyClosureRead, status_code=201)
def close_monthly_period(
    payload: CloseMonthlyPeriodRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=255),
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("closures.close")),
) -> MonthlyClosureRead:
    clock = SystemClock()
    with uow:
        guard = IdempotencyGuard(records=SqlAlchemyIdempotencyRecordRepository(uow.session))
        # `operation` stays constant ("closures.close") — `clinic_id`/
        # `period_start`/`period_end` live in the payload, not the operation
        # string, precisely so that reusing the same key with different
        # values collides as "mesma key, payload diferente"
        # (`.claude/rules/02-backend.md`) instead of silently opening a
        # brand new idempotency scope.
        outcome = guard.begin(
            actor_id=current_user.id,
            operation="closures.close",
            idempotency_key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            now=clock.now(),
        )
        if outcome.replayed_response is not None:
            uow.commit()
            _, body = outcome.replayed_response
            return MonthlyClosureRead.model_validate(body)

        candidates_repository = SqlAlchemyClosurePreviewRepository(uow.session)
        use_case = CloseMonthlyPeriodUseCase(
            clinics=SqlAlchemyClinicRepository(uow.session),
            candidates=candidates_repository,
            closures=SqlAlchemyMonthlyClosureRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            outbox=SqlAlchemyOutboxEventRepository(uow.session),
            clock=clock,
        )
        result = use_case.execute(
            CloseMonthlyPeriodCommand(
                actor=current_user,
                clinic_id=payload.clinic_id,
                period_start=payload.period_start,
                period_end=payload.period_end,
            )
        )
        response = _monthly_closure_read(result)
        guard.complete(
            outcome.record_id,
            status_code=201,
            body=response.model_dump(mode="json"),
            now=clock.now(),
        )
        uow.commit()
    return response


@router.get("", response_model=MonthlyClosureListResponse)
def list_monthly_closures(
    clinic_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("closures.read")),
) -> MonthlyClosureListResponse:
    use_case = ListMonthlyClosuresUseCase(closures=SqlAlchemyMonthlyClosureRepository(session))
    result = use_case.execute(
        ListMonthlyClosuresQuery(
            actor=current_user, clinic_id=clinic_id, page=page, page_size=page_size
        )
    )
    return _monthly_closure_page_read(result)


@router.get("/by-period", response_model=MonthlyClosureRead)
def get_closure_by_period(
    clinic_id: UUID = Query(...),
    period_start: date = Query(...),
    period_end: date = Query(...),
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("closures.read")),
) -> MonthlyClosureRead:
    use_case = GetClosureByPeriodUseCase(closures=SqlAlchemyMonthlyClosureRepository(session))
    result = use_case.execute(
        GetClosureByPeriodQuery(
            actor=current_user,
            clinic_id=clinic_id,
            period_start=period_start,
            period_end=period_end,
        )
    )
    return _monthly_closure_read(result)


@router.get("/{closure_id}", response_model=MonthlyClosureRead)
def get_monthly_closure(
    closure_id: UUID,
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("closures.read")),
) -> MonthlyClosureRead:
    use_case = GetMonthlyClosureUseCase(closures=SqlAlchemyMonthlyClosureRepository(session))
    result = use_case.execute(GetMonthlyClosureQuery(actor=current_user, closure_id=closure_id))
    return _monthly_closure_read(result)


@router.post("/{closure_id}/reopen", response_model=MonthlyClosureRead)
def reopen_monthly_closure(
    closure_id: UUID,
    payload: ReopenMonthlyClosureRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("closures.reopen")),
) -> MonthlyClosureRead:
    with uow:
        use_case = ReopenMonthlyClosureUseCase(
            closures=SqlAlchemyMonthlyClosureRepository(uow.session),
            candidates=SqlAlchemyClosurePreviewRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            outbox=SqlAlchemyOutboxEventRepository(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            ReopenMonthlyClosureCommand(
                actor=current_user,
                closure_id=closure_id,
                reason=payload.reason,
            )
        )
        response = _monthly_closure_read(result)
        uow.commit()
    return response


@router.post(
    "/{closure_id}/adjustments",
    response_model=FinancialAdjustmentRead,
    status_code=201,
)
def add_financial_adjustment(
    closure_id: UUID,
    payload: FinancialAdjustmentCreateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("closures.adjust")),
) -> FinancialAdjustmentRead:
    with uow:
        use_case = AddFinancialAdjustmentUseCase(
            closures=SqlAlchemyMonthlyClosureRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            outbox=SqlAlchemyOutboxEventRepository(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            AddFinancialAdjustmentCommand(
                actor=current_user,
                closure_id=closure_id,
                closure_item_id=payload.monthly_closure_item_id,
                kind=AdjustmentKind(payload.kind),
                amount=payload.amount,
                reason=payload.reason,
            )
        )
        response = _financial_adjustment_read(result)
        uow.commit()
    return response


@router.get("/{closure_id}/export")
def export_monthly_closure(
    closure_id: UUID,
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("closures.read")),
) -> Response:
    use_case = GetMonthlyClosureUseCase(closures=SqlAlchemyMonthlyClosureRepository(session))
    result = use_case.execute(GetMonthlyClosureQuery(actor=current_user, closure_id=closure_id))
    csv_content = monthly_closure_to_csv(result)
    filename = f"fechamento-{result.competence_year}-{result.competence_month:02d}-{result.id}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
