from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.modules.billing.application.export_monthly_closure import monthly_closure_to_csv
from app.modules.billing.application.get_closure_by_period import (
    GetClosureByPeriodQuery,
    GetClosureByPeriodUseCase,
)
from app.modules.billing.application.get_monthly_closure import (
    GetMonthlyClosureQuery,
    GetMonthlyClosureUseCase,
)
from app.modules.billing.application.list_monthly_closures import (
    ListMonthlyClosuresQuery,
    ListMonthlyClosuresUseCase,
)
from app.modules.billing.application.mappers import monthly_closure_to_dto
from app.modules.billing.domain.entities import (
    ClosureStatus,
    MonthlyClosure,
    MonthlyClosureItem,
)
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.domain.errors import ForbiddenError, NotFoundError
from tests.billing.fakes import FakeMonthlyClosureRepository

_NOW = datetime(2026, 2, 1, tzinfo=UTC)


def _actor(*, permissions: frozenset[str]) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        user_id=uuid4(),
        email="finance@vertere.local",
        full_name="Finance",
        role_id=uuid4(),
        role_name="FINANCE",
        permissions=permissions,
    )


def _clinic_actor(*, clinic_ids: frozenset[UUID]) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        user_id=uuid4(),
        email="clinic@vertere.local",
        full_name="Clinic",
        role_id=uuid4(),
        role_name="CLINIC_STAFF",
        role_scope="CLINIC",
        permissions=frozenset({"closures.read"}),
        clinic_ids=clinic_ids,
    )


def _closure(*, clinic_id: object | None = None) -> MonthlyClosure:
    closure_id = uuid4()
    item = MonthlyClosureItem(
        id=uuid4(),
        monthly_closure_id=closure_id,
        attendance_id=uuid4(),
        attendance_exam_id=uuid4(),
        protocol_number="2026/000001",
        patient_name="Rex",
        exam_name="Hemograma",
        price_base=Decimal("100.00"),
        quantity=1,
        discount_amount=Decimal("0"),
        surcharge_amount=Decimal("0"),
        total_amount=Decimal("100.00"),
    )
    return MonthlyClosure(
        id=closure_id,
        clinic_id=clinic_id or uuid4(),  # type: ignore[arg-type]
        competence_year=2026,
        competence_month=1,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        status=ClosureStatus.CLOSED,
        item_count=1,
        subtotal=Decimal("100.00"),
        discount_total=Decimal("0"),
        surcharge_total=Decimal("0"),
        grand_total=Decimal("100.00"),
        generated_by=uuid4(),
        closed_by=uuid4(),
        generated_at=_NOW,
        closed_at=_NOW,
        items=[item],
    )


_READER = frozenset({"closures.read"})
_CSV_HEADER = "protocolo,paciente,exame,preco_base,quantidade,desconto,adicional,total"


def test_get_and_get_by_period_check_permission_and_return_the_closure_with_items() -> None:
    closure = _closure()
    repository = FakeMonthlyClosureRepository()
    repository.add(closure)
    get = GetMonthlyClosureUseCase(closures=repository)
    by_period = GetClosureByPeriodUseCase(closures=repository)
    period = {"period_start": closure.period_start, "period_end": closure.period_end}

    with pytest.raises(ForbiddenError):
        get.execute(
            GetMonthlyClosureQuery(actor=_actor(permissions=frozenset()), closure_id=closure.id)
        )
    with pytest.raises(ForbiddenError):
        by_period.execute(
            GetClosureByPeriodQuery(
                actor=_actor(permissions=frozenset()), clinic_id=closure.clinic_id, **period
            )
        )
    with pytest.raises(NotFoundError):
        get.execute(GetMonthlyClosureQuery(actor=_actor(permissions=_READER), closure_id=uuid4()))
    with pytest.raises(NotFoundError):
        by_period.execute(
            GetClosureByPeriodQuery(actor=_actor(permissions=_READER), clinic_id=uuid4(), **period)
        )

    result = get.execute(
        GetMonthlyClosureQuery(actor=_actor(permissions=_READER), closure_id=closure.id)
    )
    assert result.id == closure.id
    assert [item.exam_name for item in result.items] == ["Hemograma"]
    found = by_period.execute(
        GetClosureByPeriodQuery(
            actor=_actor(permissions=_READER), clinic_id=closure.clinic_id, **period
        )
    )
    assert found.id == closure.id


def test_list_closures_checks_permission_and_clinic_actor_sees_only_own() -> None:
    own_clinic_id = uuid4()
    foreign_closure = _closure()
    own_closure = _closure(clinic_id=own_clinic_id)
    repository = FakeMonthlyClosureRepository()
    repository.add(foreign_closure)
    repository.add(own_closure)
    list_use_case = ListMonthlyClosuresUseCase(closures=repository)

    with pytest.raises(ForbiddenError):
        list_use_case.execute(
            ListMonthlyClosuresQuery(
                actor=_actor(permissions=frozenset()), clinic_id=None, page=1, page_size=20
            )
        )
    everything = list_use_case.execute(
        ListMonthlyClosuresQuery(
            actor=_actor(permissions=_READER), clinic_id=None, page=1, page_size=20
        )
    )
    assert (everything.total, len(everything.items)) == (2, 2)

    clinic_actor = _clinic_actor(clinic_ids=frozenset({own_clinic_id}))
    own_only = list_use_case.execute(
        ListMonthlyClosuresQuery(actor=clinic_actor, clinic_id=None, page=1, page_size=20)
    )
    assert [item.id for item in own_only.items] == [own_closure.id]
    with pytest.raises(NotFoundError):
        GetMonthlyClosureUseCase(closures=repository).execute(
            GetMonthlyClosureQuery(actor=clinic_actor, closure_id=foreign_closure.id)
        )


def _csv_lines(closure: MonthlyClosure) -> list[str]:
    return monthly_closure_to_csv(monthly_closure_to_dto(closure)).splitlines()


def test_csv_export_lists_items_and_only_shows_on_call_fee_when_present() -> None:
    closure = _closure()
    lines = _csv_lines(closure)
    assert lines == [_CSV_HEADER, "P000001/26,Rex,Hemograma,100.00,1,0,0,100.00"]
    assert "taxas_total" not in "".join(lines)

    closure.on_call_fee_total = Decimal("150.00")
    assert "taxas_total,150.00" in _csv_lines(closure)

    closure.items.clear()
    closure.item_count = 0
    closure.on_call_fee_total = Decimal("0")
    assert _csv_lines(closure) == [_CSV_HEADER]
