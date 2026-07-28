from __future__ import annotations

from app.modules.billing.application.dtos import (
    ClosurePreviewBlockedItemDTO,
    ClosurePreviewDTO,
    ClosurePreviewItemDTO,
)
from app.modules.billing.domain.entities import (
    ClosurePreview,
    ClosurePreviewBlockedItem,
    ClosurePreviewItem,
)


def _item_to_dto(item: ClosurePreviewItem) -> ClosurePreviewItemDTO:
    return ClosurePreviewItemDTO(
        attendance_id=item.attendance_id,
        attendance_exam_id=item.attendance_exam_id,
        protocol_number=item.protocol_number,
        patient_name=item.patient_name,
        exam_name=item.exam_name,
        total_amount=item.total_amount,
    )


def _blocked_item_to_dto(item: ClosurePreviewBlockedItem) -> ClosurePreviewBlockedItemDTO:
    return ClosurePreviewBlockedItemDTO(
        attendance_id=item.attendance_id,
        attendance_exam_id=item.attendance_exam_id,
        protocol_number=item.protocol_number,
        patient_name=item.patient_name,
        exam_name=item.exam_name,
        total_amount=item.total_amount,
        reason=item.reason,
    )


def closure_preview_to_dto(preview: ClosurePreview) -> ClosurePreviewDTO:
    return ClosurePreviewDTO(
        clinic_id=preview.clinic_id,
        competence_year=preview.competence_year,
        competence_month=preview.competence_month,
        period_start=preview.period_start,
        period_end=preview.period_end,
        attendance_count=preview.attendance_count,
        cancelled_attendance_count=preview.cancelled_attendance_count,
        item_count=preview.item_count,
        subtotal=preview.subtotal,
        discount_total=preview.discount_total,
        surcharge_total=preview.surcharge_total,
        grand_total=preview.grand_total,
        eligible_items=[_item_to_dto(item) for item in preview.eligible_items],
        blocked_items=[_blocked_item_to_dto(item) for item in preview.blocked_items],
        generated_at=preview.generated_at,
    )
