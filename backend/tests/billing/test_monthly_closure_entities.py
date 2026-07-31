"""Unit tests for the persistent `MonthlyClosure`/`MonthlyClosureItem`
entities (Incremento 4.2) — invariants only, no persistence here (see
`tests/integration/test_billing_closures_repository.py` for that)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.billing.domain.entities import ClosureStatus, MonthlyClosure, MonthlyClosureItem
from app.shared.domain.errors import ValidationError

_NOW = datetime(2026, 2, 1, tzinfo=UTC)


def _item(**overrides: object) -> MonthlyClosureItem:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "monthly_closure_id": uuid4(),
        "attendance_id": uuid4(),
        "attendance_exam_id": uuid4(),
        "protocol_number": "2026/000001",
        "patient_name": "Rex",
        "exam_name": "Hemograma",
        "price_base": Decimal("100.00"),
        "quantity": 1,
        "discount_amount": Decimal("0"),
        "surcharge_amount": Decimal("0"),
        "total_amount": Decimal("100.00"),
    }
    defaults.update(overrides)
    return MonthlyClosureItem(**defaults)  # type: ignore[arg-type]


def _closure(*, items: list[MonthlyClosureItem], **overrides: object) -> MonthlyClosure:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "clinic_id": uuid4(),
        "competence_year": 2026,
        "competence_month": 1,
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 1, 31),
        "status": ClosureStatus.CLOSED,
        "item_count": len(items),
        "subtotal": Decimal("100.00"),
        "discount_total": Decimal("0"),
        "surcharge_total": Decimal("0"),
        "grand_total": Decimal("100.00"),
        "generated_by": uuid4(),
        "closed_by": uuid4(),
        "generated_at": _NOW,
        "closed_at": _NOW,
        "items": items,
    }
    defaults.update(overrides)
    return MonthlyClosure(**defaults)  # type: ignore[arg-type]


def test_builds_a_valid_closure_with_matching_item_count() -> None:
    closure = _closure(items=[_item()])
    assert closure.status == ClosureStatus.CLOSED
    assert closure.item_count == 1


def test_rejects_a_closure_whose_item_count_disagrees_with_the_items_list() -> None:
    with pytest.raises(ValidationError, match="Contagem de itens"):
        _closure(items=[_item()], item_count=2)


@pytest.mark.parametrize("field", ["subtotal", "discount_total", "surcharge_total", "grand_total"])
def test_rejects_negative_header_totals(field: str) -> None:
    with pytest.raises(ValidationError):
        _closure(items=[_item()], **{field: Decimal("-1")})


def test_rejects_an_item_with_zero_or_negative_quantity() -> None:
    with pytest.raises(ValidationError, match="Quantidade"):
        _item(quantity=0)


@pytest.mark.parametrize("field", ["discount_amount", "surcharge_amount", "total_amount"])
def test_rejects_an_item_with_negative_money_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        _item(**{field: Decimal("-1")})
