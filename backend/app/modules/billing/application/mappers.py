from __future__ import annotations

from app.modules.billing.application.dtos import (
    ClosurePreviewBlockedItemDTO,
    ClosurePreviewDTO,
    ClosurePreviewItemDTO,
    MonthlyClosureDTO,
    MonthlyClosureItemDTO,
)
from app.modules.billing.domain.entities import (
    ClosurePreview,
    ClosurePreviewBlockedItem,
    ClosurePreviewItem,
    MonthlyClosure,
    MonthlyClosureItem,
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


def _closure_item_to_dto(item: MonthlyClosureItem) -> MonthlyClosureItemDTO:
    return MonthlyClosureItemDTO(
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


def monthly_closure_to_dto(closure: MonthlyClosure) -> MonthlyClosureDTO:
    return MonthlyClosureDTO(
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
        items=[_closure_item_to_dto(item) for item in closure.items],
    )
