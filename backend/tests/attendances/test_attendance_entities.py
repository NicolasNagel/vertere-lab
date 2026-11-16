from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.attendances.domain.entities import (
    AttendanceExam,
    AttendanceRecord,
    AttendanceStatus,
    CollectionMethod,
    ServiceLevel,
)
from app.shared.domain.errors import AttendanceAlreadyClosedError, InvalidStateTransitionError

_NOW = datetime(2026, 1, 3, 10, 2, tzinfo=UTC)


def _item(*, price_base: str, quantity: int = 1) -> AttendanceExam:
    return AttendanceExam(
        id=uuid4(),
        attendance_id=uuid4(),
        exam_id=uuid4(),
        exam_code="HEMO",
        exam_name="Hemograma",
        price_base=Decimal(price_base),
        quantity=quantity,
    )


def _legacy(
    *,
    items: list[AttendanceExam],
    service_level: ServiceLevel = ServiceLevel.NORMAL,
    **extra: object,
) -> AttendanceRecord:
    values: dict[str, object] = {
        "id": uuid4(),
        "clinic_id": uuid4(),
        "veterinarian_id": uuid4(),
        "patient_id": uuid4(),
        "collection_method": CollectionMethod.COURIER,
        "service_level": service_level,
        "service_date": date(2026, 1, 3),
        "items": items,
        "protocol_year": 2026,
        "protocol_sequence": 1,
        "on_call_fee": Decimal("0"),
        "legacy_source_row_number": 5,
        "legacy_protocol_reference": "1/2026",
        "import_batch_id": uuid4(),
        "now": _NOW,
        "created_by": None,
    }
    values.update(extra)
    return AttendanceRecord.create_from_legacy_import(**values)  # type: ignore[arg-type]


def test_legacy_import_lands_completed_with_totals_and_cannot_be_edited_or_cancelled() -> None:
    batch_id = uuid4()
    attendance = _legacy(items=[_item(price_base="75.00")], import_batch_id=batch_id)

    assert attendance.status == AttendanceStatus.COMPLETED
    assert (attendance.subtotal, attendance.grand_total) == (Decimal("75.00"), Decimal("75.00"))
    assert attendance.protocol_number == "P000001/26"
    assert attendance.billing_competence == date(2026, 1, 1)
    assert (attendance.legacy_source_row_number, attendance.legacy_protocol_reference) == (
        5,
        "1/2026",
    )
    assert attendance.import_batch_id == batch_id

    with pytest.raises(InvalidStateTransitionError):
        attendance.update_fields(
            clinic_id=None,
            veterinarian_id=None,
            patient_id=None,
            service_date=None,
            notes="tentativa de edição",
            now=_NOW,
            updated_by=None,
        )
    with pytest.raises((InvalidStateTransitionError, AttendanceAlreadyClosedError)):
        attendance.cancel(reason="teste", now=_NOW, cancelled_by=None)


def test_legacy_import_sums_multiple_items_and_on_call_fee() -> None:
    attendance = _legacy(
        items=[_item(price_base="100.00"), _item(price_base="50.00")],
        service_level=ServiceLevel.PLANTAO_ESPECIAL,
        on_call_fee=Decimal("150.00"),
        protocol_sequence=2,
    )

    assert attendance.subtotal == Decimal("150.00")
    assert attendance.on_call_fee == Decimal("150.00")
    assert attendance.grand_total == Decimal("300.00")
