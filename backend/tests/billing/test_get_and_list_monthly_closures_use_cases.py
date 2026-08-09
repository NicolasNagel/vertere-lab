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


# ---------------- GetMonthlyClosureUseCase ----------------


def test_get_without_permission_is_forbidden() -> None:
    use_case = GetMonthlyClosureUseCase(closures=FakeMonthlyClosureRepository())
    with pytest.raises(ForbiddenError):
        use_case.execute(
            GetMonthlyClosureQuery(actor=_actor(permissions=frozenset()), closure_id=uuid4())
        )


def test_get_unknown_closure_is_not_found() -> None:
    use_case = GetMonthlyClosureUseCase(closures=FakeMonthlyClosureRepository())
    with pytest.raises(NotFoundError):
        use_case.execute(
            GetMonthlyClosureQuery(
                actor=_actor(permissions=frozenset({"closures.read"})), closure_id=uuid4()
            )
        )


def test_get_returns_the_closure_with_its_items() -> None:
    closure = _closure()
    repository = FakeMonthlyClosureRepository()
    repository.add(closure)

    use_case = GetMonthlyClosureUseCase(closures=repository)
    result = use_case.execute(
        GetMonthlyClosureQuery(
            actor=_actor(permissions=frozenset({"closures.read"})), closure_id=closure.id
        )
    )

    assert result.id == closure.id
    assert len(result.items) == 1
    assert result.items[0].exam_name == "Hemograma"


# ---------------- GetClosureByPeriodUseCase ----------------


def test_get_by_period_without_permission_is_forbidden() -> None:
    use_case = GetClosureByPeriodUseCase(closures=FakeMonthlyClosureRepository())
    with pytest.raises(ForbiddenError):
        use_case.execute(
            GetClosureByPeriodQuery(
                actor=_actor(permissions=frozenset()),
                clinic_id=uuid4(),
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
            )
        )


def test_get_by_period_with_no_closure_is_not_found() -> None:
    use_case = GetClosureByPeriodUseCase(closures=FakeMonthlyClosureRepository())
    with pytest.raises(NotFoundError):
        use_case.execute(
            GetClosureByPeriodQuery(
                actor=_actor(permissions=frozenset({"closures.read"})),
                clinic_id=uuid4(),
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
            )
        )


def test_get_by_period_finds_the_closure_by_clinic_and_competence() -> None:
    closure = _closure()
    repository = FakeMonthlyClosureRepository()
    repository.add(closure)

    use_case = GetClosureByPeriodUseCase(closures=repository)
    result = use_case.execute(
        GetClosureByPeriodQuery(
            actor=_actor(permissions=frozenset({"closures.read"})),
            clinic_id=closure.clinic_id,
            period_start=closure.period_start,
            period_end=closure.period_end,
        )
    )

    assert result.id == closure.id


# ---------------- ListMonthlyClosuresUseCase ----------------


def test_list_without_permission_is_forbidden() -> None:
    use_case = ListMonthlyClosuresUseCase(closures=FakeMonthlyClosureRepository())
    with pytest.raises(ForbiddenError):
        use_case.execute(
            ListMonthlyClosuresQuery(
                actor=_actor(permissions=frozenset()), clinic_id=None, page=1, page_size=20
            )
        )


def test_list_returns_every_closure_added() -> None:
    repository = FakeMonthlyClosureRepository()
    repository.add(_closure())
    repository.add(_closure())

    use_case = ListMonthlyClosuresUseCase(closures=repository)
    result = use_case.execute(
        ListMonthlyClosuresQuery(
            actor=_actor(permissions=frozenset({"closures.read"})),
            clinic_id=None,
            page=1,
            page_size=20,
        )
    )

    assert result.total == 2
    assert len(result.items) == 2


def test_clinic_actor_only_lists_and_reads_own_closures() -> None:
    own_clinic_id = uuid4()
    foreign_closure = _closure()
    own_closure = _closure(clinic_id=own_clinic_id)
    repository = FakeMonthlyClosureRepository()
    repository.add(foreign_closure)
    repository.add(own_closure)
    actor = _clinic_actor(clinic_ids=frozenset({own_clinic_id}))

    result = ListMonthlyClosuresUseCase(closures=repository).execute(
        ListMonthlyClosuresQuery(actor=actor, clinic_id=None, page=1, page_size=20)
    )

    assert [item.id for item in result.items] == [own_closure.id]
    with pytest.raises(NotFoundError):
        GetMonthlyClosureUseCase(closures=repository).execute(
            GetMonthlyClosureQuery(actor=actor, closure_id=foreign_closure.id)
        )


# ---------------- monthly_closure_to_csv ----------------


def test_csv_export_has_a_header_and_one_row_per_item() -> None:
    closure = _closure()
    dto = monthly_closure_to_dto(closure)

    csv_content = monthly_closure_to_csv(dto)

    lines = csv_content.strip("\r\n").split("\r\n")
    assert lines[0] == "protocolo,paciente,exame,preco_base,quantidade,desconto,adicional,total"
    assert len(lines) == 2
    assert lines[1] == "2026/000001,Rex,Hemograma,100.00,1,0,0,100.00"


def test_csv_export_includes_the_on_call_fee_total_line() -> None:
    closure = _closure()
    closure.on_call_fee_total = Decimal("150.00")
    dto = monthly_closure_to_dto(closure)

    csv_content = monthly_closure_to_csv(dto)

    lines = csv_content.strip("\r\n").split("\r\n")
    assert "taxa_de_plantao_total,150.00" in lines


def test_csv_export_omits_the_on_call_fee_line_when_it_is_zero() -> None:
    closure = _closure()
    dto = monthly_closure_to_dto(closure)

    csv_content = monthly_closure_to_csv(dto)

    assert "taxa_de_plantao_total" not in csv_content


def test_csv_export_of_a_closure_without_items_is_header_only() -> None:
    closure = _closure()
    closure.items.clear()
    closure.item_count = 0
    dto = monthly_closure_to_dto(closure)

    csv_content = monthly_closure_to_csv(dto)

    assert csv_content.strip("\r\n").split("\r\n") == [
        "protocolo,paciente,exame,preco_base,quantidade,desconto,adicional,total"
    ]
