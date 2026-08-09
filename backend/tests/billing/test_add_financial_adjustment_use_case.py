from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.modules.billing.application.add_financial_adjustment import (
    AddFinancialAdjustmentCommand,
    AddFinancialAdjustmentUseCase,
)
from app.modules.billing.domain.entities import AdjustmentKind, ClosureStatus, MonthlyClosure
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.domain.errors import ForbiddenError, InvalidStateTransitionError, ValidationError
from tests.billing.fakes import (
    FakeAuditLogWriter,
    FakeClock,
    FakeMonthlyClosureRepository,
    FakeOutboxEventRepository,
)

_NOW = datetime(2026, 3, 1, tzinfo=UTC)


def _actor(*permissions: str) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        user_id=uuid4(),
        email="finance@vertere.local",
        full_name="Finance",
        role_id=uuid4(),
        role_name="FINANCE",
        permissions=frozenset(permissions),
    )


def _closure(status: ClosureStatus = ClosureStatus.CLOSED) -> MonthlyClosure:
    return MonthlyClosure(
        id=uuid4(),
        clinic_id=uuid4(),
        competence_year=2026,
        competence_month=2,
        period_start=date(2026, 2, 1),
        period_end=date(2026, 2, 28),
        status=status,
        item_count=0,
        subtotal=Decimal("0"),
        discount_total=Decimal("0"),
        surcharge_total=Decimal("0"),
        grand_total=Decimal("0"),
        generated_by=None,
        closed_by=None,
        generated_at=_NOW,
        closed_at=_NOW,
    )


def _command(closure_id: UUID, **overrides: object) -> AddFinancialAdjustmentCommand:
    values: dict[str, object] = {
        "actor": _actor("closures.adjust"),
        "closure_id": closure_id,
        "closure_item_id": None,
        "kind": AdjustmentKind.DEBIT,
        "amount": Decimal("12.345"),
        "reason": "Diferença financeira identificada.",
    }
    values.update(overrides)
    return AddFinancialAdjustmentCommand(**values)  # type: ignore[arg-type]


def test_adds_append_only_adjustment_with_audit_and_rounding() -> None:
    closure = _closure()
    repository = FakeMonthlyClosureRepository(closure)
    audit = FakeAuditLogWriter()
    use_case = AddFinancialAdjustmentUseCase(
        closures=repository,
        audit=audit,
        outbox=FakeOutboxEventRepository(),
        clock=FakeClock(_NOW),
    )

    result = use_case.execute(_command(closure.id))

    assert result.amount == Decimal("12.35")
    assert repository.adjustments[0].monthly_closure_id == closure.id
    assert closure.grand_total == Decimal("0")
    assert audit.entries[0].reason == "Diferença financeira identificada."


def test_rejects_adjustment_on_reopened_closure() -> None:
    closure = _closure(ClosureStatus.REOPENED)
    use_case = AddFinancialAdjustmentUseCase(
        closures=FakeMonthlyClosureRepository(closure),
        audit=FakeAuditLogWriter(),
        outbox=FakeOutboxEventRepository(),
        clock=FakeClock(_NOW),
    )
    with pytest.raises(InvalidStateTransitionError):
        use_case.execute(_command(closure.id))


def test_rejects_missing_permission() -> None:
    closure = _closure()
    use_case = AddFinancialAdjustmentUseCase(
        closures=FakeMonthlyClosureRepository(closure),
        audit=FakeAuditLogWriter(),
        outbox=FakeOutboxEventRepository(),
        clock=FakeClock(_NOW),
    )
    with pytest.raises(ForbiddenError):
        use_case.execute(_command(closure.id, actor=_actor()))


def test_rejects_item_from_another_closure() -> None:
    closure = _closure()
    use_case = AddFinancialAdjustmentUseCase(
        closures=FakeMonthlyClosureRepository(closure),
        audit=FakeAuditLogWriter(),
        outbox=FakeOutboxEventRepository(),
        clock=FakeClock(_NOW),
    )
    with pytest.raises(ValidationError):
        use_case.execute(_command(closure.id, closure_item_id=uuid4()))
