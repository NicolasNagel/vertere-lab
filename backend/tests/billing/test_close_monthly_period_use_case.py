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
        user_id=uuid4(),
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
        "service_date": date(2026, 1, 15),
        "billing_competence": date(2026, 1, 1),
        "monthly_closure_id": None,
        "protocol_number": "2026/000001",
        "patient_name": "Rex",
        "exam_name": "Hemograma",
        "service_level": "NORMAL",
        "exam_category": "Hematológico",
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
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 1, 31),
    }
    defaults.update(overrides)
    return CloseMonthlyPeriodCommand(**defaults)  # type: ignore[arg-type]


def _closure_stub(status: ClosureStatus, *, version: int = 1) -> MonthlyClosure:
    return MonthlyClosure(
        id=uuid4(),
        clinic_id=_CLINIC_ID,
        competence_year=2026,
        competence_month=1,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
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
        version=version,
    )


def test_close_rejects_invalid_requests_and_writes_nothing() -> None:
    fixture = _Fixture(candidates=[_candidate()])
    with pytest.raises(ForbiddenError):
        fixture.use_case().execute(_command(actor=_actor(permissions=frozenset())))
    with pytest.raises(NotFoundError):
        fixture.use_case().execute(_command(clinic_id=uuid4()))

    existing = _Fixture(
        candidates=[_candidate()], active_closure=_closure_stub(ClosureStatus.CLOSED)
    )
    with pytest.raises(ClosureAlreadyExistsError):
        existing.use_case().execute(_command())
    assert existing.closures.added == []

    nothing_eligible = _Fixture(candidates=[_candidate(attendance_status="CANCELLED")])
    with pytest.raises(ValidationError):
        nothing_eligible.use_case().execute(_command())
    assert nothing_eligible.closures.added == []


def test_close_totals_eligible_items_once_per_on_call_fee_and_records_audit_and_outbox() -> None:
    attendance_a = uuid4()
    attendance_cancelled = uuid4()
    fixture = _Fixture(
        candidates=[
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
            _candidate(
                attendance_id=attendance_cancelled,
                attendance_status="CANCELLED",
                total_amount=Decimal("30.00"),
            ),
        ]
    )

    result = fixture.use_case().execute(_command())

    assert (result.status, result.item_count, len(result.items)) == ("CLOSED", 2, 2)
    assert result.subtotal == Decimal("150.00")
    # A taxa de plantão é do atendimento: entra uma vez, não por item.
    assert result.on_call_fee_total == Decimal("150.00")
    assert result.grand_total == Decimal("300.00")
    assert len(fixture.closures.added) == 1
    assert fixture.closures.lock_calls == [_CLINIC_ID]
    assert fixture.candidates.marked_attendance_ids == {attendance_a}  # só quem contribuiu

    assert [(entry.action, entry.entity_id) for entry in fixture.audit.entries] == [
        ("closures.closed", str(result.id))
    ]
    assert [(event.event_type, event.payload["closure_id"]) for event in fixture.outbox.events] == [
        ("closures.closed", str(result.id))
    ]


def test_reclose_increments_the_preserved_snapshot_version() -> None:
    fixture = _Fixture(candidates=[_candidate()])
    fixture.closures = FakeMonthlyClosureRepository(
        _closure_stub(ClosureStatus.REOPENED, version=3)
    )

    assert fixture.use_case().execute(_command()).version == 4
