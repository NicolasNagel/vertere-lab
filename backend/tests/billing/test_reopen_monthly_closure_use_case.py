from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.billing.application.reopen_monthly_closure import (
    ReopenMonthlyClosureCommand,
    ReopenMonthlyClosureUseCase,
)
from app.modules.billing.domain.entities import ClosureStatus, MonthlyClosure
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.domain.errors import ForbiddenError, InvalidStateTransitionError, NotFoundError
from tests.billing.fakes import (
    FakeAuditLogWriter,
    FakeClock,
    FakeClosureCandidateLockRepository,
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


def _closure(*, status: ClosureStatus = ClosureStatus.CLOSED) -> MonthlyClosure:
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


def _execute(
    closure: MonthlyClosure | None,
    *,
    actor: AuthenticatedUserDTO | None = None,
) -> tuple[FakeMonthlyClosureRepository, FakeClosureCandidateLockRepository, FakeAuditLogWriter]:
    closures = FakeMonthlyClosureRepository(closure)
    candidates = FakeClosureCandidateLockRepository()
    audit = FakeAuditLogWriter()
    use_case = ReopenMonthlyClosureUseCase(
        closures=closures,
        candidates=candidates,
        audit=audit,
        outbox=FakeOutboxEventRepository(),
        clock=FakeClock(_NOW),
    )
    use_case.execute(
        ReopenMonthlyClosureCommand(
            actor=actor or _actor("closures.reopen"),
            closure_id=closure.id if closure is not None else uuid4(),
            reason="Correção financeira autorizada.",
        )
    )
    return closures, candidates, audit


def test_reopens_under_lock_releases_attendances_audits_reason_and_rejects_invalid_requests() -> (
    None
):
    closure = _closure()
    closures, candidates, audit = _execute(closure)

    assert closure.status is ClosureStatus.REOPENED
    assert closure.reopened_at == _NOW
    assert closures.lock_calls == [closure.clinic_id]
    assert closures.updated == [closure]
    assert candidates.released_closure_ids == [closure.id]
    assert audit.entries[0].reason == "Correção financeira autorizada."

    with pytest.raises(ForbiddenError):
        _execute(_closure(), actor=_actor())
    with pytest.raises(NotFoundError):
        _execute(None)
    with pytest.raises(InvalidStateTransitionError):  # já reaberto
        _execute(_closure(status=ClosureStatus.REOPENED))
