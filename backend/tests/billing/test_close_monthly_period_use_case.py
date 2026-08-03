from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.billing.application.close_monthly_period import (
    CloseMonthlyPeriodCommand,
    CloseMonthlyPeriodUseCase,
)
from app.modules.billing.domain.entities import ClosureCandidateItem, ClosureStatus, MonthlyClosure
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.domain.errors import (
    ClosureAlreadyExistsError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from tests.billing.fakes import (
    FakeAuditLogWriter,
    FakeClinicRepository,
    FakeClock,
    FakeClosureCandidateLockRepository,
    FakeMonthlyClosureRepository,
    FakeOutboxEventRepository,
    make_clinic,
)

_NOW = datetime(2026, 2, 1, tzinfo=UTC)
_CLINIC_ID = uuid4()


def _actor(*, permissions: frozenset[str]) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        id=uuid4(),
        email="finance@vertere.local",
        full_name="Finance",
        role_id=uuid4(),
        role_name="FINANCE",
        permissions=permissions,
    )


def _candidate(**overrides: object) -> ClosureCandidateItem:
    defaults: dict[str, object] = {
        "attendance_id": uuid4(),
        "attendance_exam_id": uuid4(),
        "attendance_status": "CONFIRMED",
        "item_status": "ACTIVE",
        "billing_competence": date(2026, 1, 1),
        "monthly_closure_id": None,
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
    return ClosureCandidateItem(**defaults)  # type: ignore[arg-type]


class _Fixture:
    def __init__(
        self,
        *,
        candidates: list[ClosureCandidateItem] | None = None,
        active_closure: MonthlyClosure | None = None,
    ) -> None:
        self.clinics = FakeClinicRepository([make_clinic(clinic_id=_CLINIC_ID)])
        self.candidates = FakeClosureCandidateLockRepository(candidates or [])
        self.closures = FakeMonthlyClosureRepository(active_closure)
        self.audit = FakeAuditLogWriter()
        self.outbox = FakeOutboxEventRepository()

    def use_case(self) -> CloseMonthlyPeriodUseCase:
        return CloseMonthlyPeriodUseCase(
            clinics=self.clinics,
            candidates=self.candidates,
            closures=self.closures,
            audit=self.audit,
            outbox=self.outbox,
            clock=FakeClock(_NOW),
        )


def _command(**overrides: object) -> CloseMonthlyPeriodCommand:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"closures.close"})),
        "clinic_id": _CLINIC_ID,
        "year": 2026,
        "month": 1,
    }
    defaults.update(overrides)
    return CloseMonthlyPeriodCommand(**defaults)  # type: ignore[arg-type]


def test_without_permission_is_forbidden() -> None:
    fixture = _Fixture(candidates=[_candidate()])
    with pytest.raises(ForbiddenError):
        fixture.use_case().execute(_command(actor=_actor(permissions=frozenset())))


def test_unknown_clinic_is_not_found() -> None:
    fixture = _Fixture(candidates=[_candidate()])
    with pytest.raises(NotFoundError):
        fixture.use_case().execute(_command(clinic_id=uuid4()))


def test_acquires_the_advisory_lock_before_checking_for_an_existing_closure() -> None:
    fixture = _Fixture(candidates=[_candidate()])
    fixture.use_case().execute(_command())
    assert fixture.closures.lock_calls == [(_CLINIC_ID, 2026, 1)]


def test_rejects_when_an_active_closure_already_exists() -> None:
    existing = MonthlyClosure(
        id=uuid4(),
        clinic_id=_CLINIC_ID,
        competence_year=2026,
        competence_month=1,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        status=ClosureStatus.CLOSED,
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
    fixture = _Fixture(candidates=[_candidate()], active_closure=existing)
    with pytest.raises(ClosureAlreadyExistsError):
        fixture.use_case().execute(_command())
    assert fixture.closures.added == []


def test_rejects_when_there_is_no_eligible_item() -> None:
    fixture = _Fixture(candidates=[_candidate(attendance_status="CANCELLED")])
    with pytest.raises(ValidationError):
        fixture.use_case().execute(_command())


def test_closes_with_totals_computed_from_eligible_items_only() -> None:
    attendance_a = uuid4()
    attendance_b_cancelled = uuid4()
    candidates = [
        _candidate(attendance_id=attendance_a, total_amount=Decimal("100.00")),
        _candidate(
            attendance_id=attendance_a, total_amount=Decimal("50.00"), price_base=Decimal("50.00")
        ),
        _candidate(
            attendance_id=attendance_b_cancelled,
            attendance_status="CANCELLED",
            total_amount=Decimal("30.00"),
        ),
    ]
    fixture = _Fixture(candidates=candidates)

    result = fixture.use_case().execute(_command())

    assert result.status == "CLOSED"
    assert result.item_count == 2
    assert result.subtotal == Decimal("150.00")
    assert result.grand_total == Decimal("150.00")
    assert len(result.items) == 2
    assert len(fixture.closures.added) == 1


def test_closes_with_on_call_fee_counted_once_per_attendance_not_per_item() -> None:
    """Same guarantee as the preview use case, at close time — a flat
    plantão fee on an attendance with 2 eligible exam items must be added
    to the closure header once, never once per item."""
    attendance_a = uuid4()
    candidates = [
        _candidate(
            attendance_id=attendance_a,
            total_amount=Decimal("100.00"),
            attendance_on_call_fee=Decimal("150.00"),
        ),
        _candidate(
            attendance_id=attendance_a,
            total_amount=Decimal("50.00"),
            price_base=Decimal("50.00"),
            attendance_on_call_fee=Decimal("150.00"),
        ),
    ]
    fixture = _Fixture(candidates=candidates)

    result = fixture.use_case().execute(_command())

    assert result.on_call_fee_total == Decimal("150.00")
    assert result.grand_total == Decimal("300.00")
    assert len(result.items) == 2


def test_associates_only_attendances_that_contributed_an_eligible_item() -> None:
    attendance_eligible = uuid4()
    attendance_blocked = uuid4()
    candidates = [
        _candidate(attendance_id=attendance_eligible),
        _candidate(attendance_id=attendance_blocked, attendance_status="CANCELLED"),
    ]
    fixture = _Fixture(candidates=candidates)

    fixture.use_case().execute(_command())

    assert fixture.candidates.marked_attendance_ids == {attendance_eligible}


def test_records_audit_and_outbox_entries() -> None:
    fixture = _Fixture(candidates=[_candidate()])

    result = fixture.use_case().execute(_command())

    assert len(fixture.audit.entries) == 1
    audit_entry = fixture.audit.entries[0]
    assert audit_entry.action == "closures.closed"
    assert audit_entry.entity_id == str(result.id)

    assert len(fixture.outbox.events) == 1
    outbox_event = fixture.outbox.events[0]
    assert outbox_event.event_type == "closures.closed"
    assert outbox_event.payload["closure_id"] == str(result.id)


def test_reclose_increments_the_preserved_snapshot_version() -> None:
    previous = MonthlyClosure(
        id=uuid4(),
        clinic_id=_CLINIC_ID,
        competence_year=2026,
        competence_month=1,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        status=ClosureStatus.REOPENED,
        item_count=0,
        subtotal=Decimal("0"),
        discount_total=Decimal("0"),
        surcharge_total=Decimal("0"),
        grand_total=Decimal("0"),
        generated_by=None,
        closed_by=None,
        generated_at=_NOW,
        closed_at=_NOW,
        version=3,
    )
    fixture = _Fixture(candidates=[_candidate()])
    fixture.closures = FakeMonthlyClosureRepository(previous)

    result = fixture.use_case().execute(_command())

    assert result.version == 4
