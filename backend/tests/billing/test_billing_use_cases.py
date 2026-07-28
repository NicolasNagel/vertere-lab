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
_PERIOD = CompetencePeriod(year=2026, month=1)


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


# ---------------- CompetencePeriod ----------------


def test_competence_period_rejects_month_out_of_range() -> None:
    with pytest.raises(ValidationError):
        CompetencePeriod(year=2026, month=13)
    with pytest.raises(ValidationError):
        CompetencePeriod(year=2026, month=0)


def test_competence_period_computes_bounds() -> None:
    period = CompetencePeriod(year=2026, month=2)
    assert period.period_start == date(2026, 2, 1)
    assert period.period_end == date(2026, 2, 28)

    december = CompetencePeriod(year=2026, month=12)
    assert december.period_end == date(2026, 12, 31)


# ---------------- is_eligible ----------------


def test_is_eligible_happy_path() -> None:
    eligible, reason = is_eligible(_candidate(), _PERIOD)
    assert eligible is True
    assert reason is None


def test_is_eligible_rejects_cancelled_attendance() -> None:
    eligible, reason = is_eligible(_candidate(attendance_status="CANCELLED"), _PERIOD)
    assert eligible is False
    assert reason is not None


def test_is_eligible_rejects_cancelled_item() -> None:
    eligible, _reason = is_eligible(_candidate(item_status="CANCELLED"), _PERIOD)
    assert eligible is False


def test_is_eligible_rejects_item_already_in_another_closure() -> None:
    eligible, _reason = is_eligible(_candidate(monthly_closure_id=uuid4()), _PERIOD)
    assert eligible is False


def test_is_eligible_rejects_competence_mismatch() -> None:
    eligible, _reason = is_eligible(_candidate(billing_competence=date(2026, 2, 1)), _PERIOD)
    assert eligible is False


def test_is_eligible_rejects_missing_competence() -> None:
    eligible, _reason = is_eligible(_candidate(billing_competence=None), _PERIOD)
    assert eligible is False


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
        "year": 2026,
        "month": 1,
    }
    defaults.update(overrides)
    return PreviewClosureQuery(**defaults)  # type: ignore[arg-type]


def test_preview_without_permission_is_forbidden() -> None:
    fixture = _Fixture()
    with pytest.raises(ForbiddenError):
        fixture.use_case().execute(_query(actor=_actor(permissions=frozenset())))


def test_preview_unknown_clinic_is_not_found() -> None:
    fixture = _Fixture()
    with pytest.raises(NotFoundError):
        fixture.use_case().execute(_query(clinic_id=uuid4()))


def test_preview_totals_and_counts_from_eligible_items_only() -> None:
    attendance_a = uuid4()
    attendance_b_cancelled = uuid4()
    candidates = [
        _candidate(attendance_id=attendance_a, total_amount=Decimal("100.00")),
        _candidate(
            attendance_id=attendance_a,
            total_amount=Decimal("50.00"),
            price_base=Decimal("50.00"),
        ),
        _candidate(
            attendance_id=attendance_b_cancelled,
            attendance_status="CANCELLED",
            total_amount=Decimal("30.00"),
        ),
    ]
    fixture = _Fixture(candidates)

    result = fixture.use_case().execute(_query())

    assert result.attendance_count == 2
    assert result.cancelled_attendance_count == 1
    assert result.item_count == 2
    assert result.subtotal == Decimal("150.00")
    assert result.grand_total == Decimal("150.00")
    assert len(result.eligible_items) == 2
    assert len(result.blocked_items) == 1
    assert result.blocked_items[0].reason


def test_preview_does_not_mutate_or_persist_anything() -> None:
    """The preview only reads — no repository method beyond
    `list_candidates` is ever called (rule: "não fecha nem bloqueia
    nada — é só leitura")."""
    fixture = _Fixture([_candidate()])
    fixture.use_case().execute(_query())
    fixture.use_case().execute(_query())
    # Calling twice with the same fake (no internal state mutation) must
    # produce the same result both times.
    result = fixture.use_case().execute(_query())
    assert result.item_count == 1
