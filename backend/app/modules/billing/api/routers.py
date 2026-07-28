"""Billing API — thin router, no business rule (rule:
.claude/rules/backend.md).

Only `GET /closures/preview` exists in this slice — read-only, no UoW
(nothing is written).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as SqlAlchemySession

from app.api.dependencies import get_session
from app.modules.billing.api.schemas import (
    ClosurePreviewBlockedItemRead,
    ClosurePreviewItemRead,
    ClosurePreviewResponse,
)
from app.modules.billing.application.dtos import ClosurePreviewDTO
from app.modules.billing.application.preview_closure import (
    PreviewClosureQuery,
    PreviewClosureUseCase,
)
from app.modules.billing.infrastructure.repositories import SqlAlchemyClosurePreviewRepository
from app.modules.clinics.infrastructure.repositories import SqlAlchemyClinicRepository
from app.modules.identity.api.dependencies import require_permission
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.infrastructure.clock import SystemClock

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
