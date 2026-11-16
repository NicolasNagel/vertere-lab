from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.billing.application.preview_closure import (
    PreviewClosureQuery,
    PreviewClosureUseCase,
)
from app.modules.billing.domain.eligibility import is_eligible
from app.modules.billing.domain.entities import ClosureCandidateItem, CompetencePeriod
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.domain.errors import ForbiddenError, NotFoundError, ValidationError
from tests.billing.fakes import (
    FakeClinicRepository,
    FakeClock,
    FakeClosurePreviewRepository,
    make_clinic,
)

_NOW = datetime(2026, 1, 15, tzinfo=UTC)
_CLINIC_ID = uuid4()
_PERIOD = CompetencePeriod.for_month(year=2026, month=1)


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


# ---------------- CompetencePeriod ----------------


def test_competence_period_bounds_and_validation() -> None:
    february = CompetencePeriod.for_month(year=2026, month=2)
    assert (february.period_start, february.period_end) == (date(2026, 2, 1), date(2026, 2, 28))
    assert CompetencePeriod.for_month(year=2026, month=12).period_end == date(2026, 12, 31)

    # Faixa livre (quinzena) é aceita; fim antes do início, mês inválido e vão enorme não.
    free = CompetencePeriod(period_start=date(2026, 1, 16), period_end=date(2026, 1, 31))
    assert (free.period_start, free.period_end) == (date(2026, 1, 16), date(2026, 1, 31))
    with pytest.raises(ValidationError):
        CompetencePeriod.for_month(year=2026, month=13)
    with pytest.raises(ValidationError):
        CompetencePeriod.for_month(year=2026, month=0)
    with pytest.raises(ValidationError):
        CompetencePeriod(period_start=date(2026, 1, 31), period_end=date(2026, 1, 1))
    with pytest.raises(ValidationError):
        CompetencePeriod(period_start=date(2026, 1, 1), period_end=date(2028, 1, 1))


# ---------------- is_eligible ----------------


def test_is_eligible_only_for_active_unclosed_items_inside_the_period() -> None:
    second_half = CompetencePeriod(period_start=date(2026, 1, 16), period_end=date(2026, 1, 31))

    assert is_eligible(_candidate(), _PERIOD) == (True, None)
    assert is_eligible(_candidate(service_date=date(2026, 1, 20)), second_half) == (True, None)

    blocked: list[tuple[dict[str, object], CompetencePeriod]] = [
        ({"attendance_status": "CANCELLED"}, _PERIOD),
        ({"item_status": "CANCELLED"}, _PERIOD),
        ({"monthly_closure_id": uuid4()}, _PERIOD),
        ({"service_date": date(2026, 2, 1)}, _PERIOD),
        ({"service_date": None}, _PERIOD),
        ({"service_date": date(2026, 1, 10)}, second_half),
    ]
    for overrides, period in blocked:
        eligible, reason = is_eligible(_candidate(**overrides), period)
        assert eligible is False, overrides
        assert reason, overrides


# ---------------- PreviewClosureUseCase ----------------


class _Fixture:
    def __init__(self, candidates: list[ClosureCandidateItem] | None = None) -> None:
        self.clinics = FakeClinicRepository([make_clinic(clinic_id=_CLINIC_ID)])
        self.candidates = FakeClosurePreviewRepository(candidates or [])

    def use_case(self) -> PreviewClosureUseCase:
        return PreviewClosureUseCase(
            clinics=self.clinics, candidates=self.candidates, clock=FakeClock(_NOW)
        )


def _query(**overrides: object) -> PreviewClosureQuery:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"closures.preview"})),
        "clinic_id": _CLINIC_ID,
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 1, 31),
    }
    defaults.update(overrides)
    return PreviewClosureQuery(**defaults)  # type: ignore[arg-type]


def test_preview_rejects_missing_permission_and_unknown_clinic() -> None:
    fixture = _Fixture()
    with pytest.raises(ForbiddenError):
        fixture.use_case().execute(_query(actor=_actor(permissions=frozenset())))
    with pytest.raises(NotFoundError):
        fixture.use_case().execute(_query(clinic_id=uuid4()))


def test_preview_totals_come_from_eligible_items_and_on_call_fee_counts_once_per_attendance() -> (
    None
):
    attendance_a = uuid4()
    candidates = [
        _candidate(attendance_id=attendance_a, total_amount=Decimal("100.00")),
        _candidate(
            attendance_id=attendance_a,
            total_amount=Decimal("50.00"),
            price_base=Decimal("50.00"),
        ),
        _candidate(attendance_status="CANCELLED", total_amount=Decimal("30.00")),
    ]
    fixture = _Fixture(candidates)
    result = fixture.use_case().execute(_query())

    assert (result.attendance_count, result.cancelled_attendance_count, result.item_count) == (
        2,
        1,
        2,
    )
    assert (result.subtotal, result.grand_total) == (Decimal("150.00"), Decimal("150.00"))
    assert (len(result.eligible_items), len(result.blocked_items)) == (2, 1)
    assert result.blocked_items[0].reason

    # Taxa de plantão vive no atendimento: duas linhas elegíveis somam a taxa uma vez só;
    # atendimento sem item elegível não contribui. A prévia só lê (repetir dá o mesmo).
    with_fee = [
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
    fee_fixture = _Fixture(with_fee)
    fee_result = fee_fixture.use_case().execute(_query())
    assert fee_result.on_call_fee_total == Decimal("150.00")
    assert fee_result.subtotal == Decimal("150.00")
    assert fee_result.grand_total == Decimal("300.00")
    assert fee_fixture.use_case().execute(_query()) == fee_result

    cancelled = (
        _Fixture(
            [
                _candidate(
                    attendance_status="CANCELLED",
                    total_amount=Decimal("100.00"),
                    attendance_on_call_fee=Decimal("150.00"),
                )
            ]
        )
        .use_case()
        .execute(_query())
    )
    assert (cancelled.on_call_fee_total, cancelled.grand_total) == (Decimal("0"), Decimal("0"))
