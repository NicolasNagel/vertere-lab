"""Billing API — thin router, no business rule (rule:
.claude/rules/02-backend.md).

`GET /closures/preview` is read-only, no UoW. `POST /closures` (Incremento
4.2) is the first writer — wrapped in a unit of work and an
`Idempotency-Key` guard, same shape as `POST /attendances/{id}/confirm`.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session as SqlAlchemySession

from app.api.dependencies import get_session, get_unit_of_work
from app.modules.audit.infrastructure.repositories import SqlAlchemyAuditLogWriter
from app.modules.billing.api.schemas import (
    CloseMonthlyPeriodRequest,
    ClosurePreviewBlockedItemRead,
    ClosurePreviewItemRead,
    ClosurePreviewResponse,
    MonthlyClosureItemRead,
    MonthlyClosureRead,
)
from app.modules.billing.application.close_monthly_period import (
    CloseMonthlyPeriodCommand,
    CloseMonthlyPeriodUseCase,
)
from app.modules.billing.application.dtos import ClosurePreviewDTO, MonthlyClosureDTO
from app.modules.billing.application.preview_closure import (
    PreviewClosureQuery,
    PreviewClosureUseCase,
)
from app.modules.billing.infrastructure.repositories import (
    SqlAlchemyClosurePreviewRepository,
    SqlAlchemyMonthlyClosureRepository,
)
from app.modules.clinics.infrastructure.repositories import SqlAlchemyClinicRepository
from app.modules.identity.api.dependencies import require_permission
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.idempotency.application.guard import IdempotencyGuard
from app.shared.idempotency.infrastructure.repositories import SqlAlchemyIdempotencyRecordRepository
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork
from app.shared.outbox.infrastructure.repositories import SqlAlchemyOutboxEventRepository

router = APIRouter(prefix="/closures", tags=["billing"])


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
        grand_total=dto.grand_total,
        eligible_items=[
            ClosurePreviewItemRead(
                attendance_id=item.attendance_id,
                attendance_exam_id=item.attendance_exam_id,
                protocol_number=item.protocol_number,
                patient_name=item.patient_name,
                exam_name=item.exam_name,
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
            )
            for item in dto.items
        ],
    )


@router.get("/preview", response_model=ClosurePreviewResponse)
def preview_closure(
    clinic_id: UUID = Query(...),
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    session: SqlAlchemySession = Depends(get_session),
    current_user: AuthenticatedUserDTO = Depends(require_permission("closures.preview")),
) -> ClosurePreviewResponse:
    use_case = PreviewClosureUseCase(
        clinics=SqlAlchemyClinicRepository(session),
        candidates=SqlAlchemyClosurePreviewRepository(session),
        clock=SystemClock(),
    )
    result = use_case.execute(
        PreviewClosureQuery(actor=current_user, clinic_id=clinic_id, year=year, month=month)
    )
    return _closure_preview_read(result)


@router.post("", response_model=MonthlyClosureRead, status_code=201)
def close_monthly_period(
    payload: CloseMonthlyPeriodRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=255),
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("closures.close")),
) -> MonthlyClosureRead:
    clock = SystemClock()
    with uow:
        guard = IdempotencyGuard(records=SqlAlchemyIdempotencyRecordRepository(uow.session))
        # `operation` stays constant ("closures.close") — `clinic_id`/`year`/
        # `month` live in the payload, not the operation string, precisely so
        # that reusing the same key with different values collides as
        # "mesma key, payload diferente" (`.claude/rules/02-backend.md`) instead
        # of silently opening a brand new idempotency scope.
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
                year=payload.year,
                month=payload.month,
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
