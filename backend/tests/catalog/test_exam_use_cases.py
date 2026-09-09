from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.catalog.application.create_exam import CreateExamCommand, CreateExamUseCase
from app.modules.catalog.application.create_exam_category import (
    CreateExamCategoryCommand,
    CreateExamCategoryUseCase,
)
from app.modules.catalog.application.deactivate_exam import (
    DeactivateExamCommand,
    DeactivateExamUseCase,
)
from app.modules.catalog.application.dtos import ExamCategoryDTO
from app.modules.catalog.application.get_exam import GetExamQuery, GetExamUseCase
from app.modules.catalog.application.list_exams import ListExamsQuery, ListExamsUseCase
from app.modules.catalog.application.update_exam import UpdateExamCommand, UpdateExamUseCase
from app.modules.catalog.domain.entities import ExamStatus
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.domain.entities import Species
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from tests.catalog.fakes import (
    FakeAuditLogWriter,
    FakeClock,
    FakeExamCategoryRepository,
    FakeExamRepository,
    FakeSpeciesRepository,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_DOG_SPECIES_ID = uuid4()
_CAT_SPECIES_ID = uuid4()


def _actor(*, permissions: frozenset[str]) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        user_id=uuid4(),
        email="user@vertere.local",
        full_name="User",
        role_id=uuid4(),
        role_name="FINANCE",
        permissions=permissions,
    )


def _species_repo() -> FakeSpeciesRepository:
    return FakeSpeciesRepository(
        [
            Species(id=_DOG_SPECIES_ID, name="Cão", created_at=_NOW),
            Species(id=_CAT_SPECIES_ID, name="Gato", created_at=_NOW),
        ]
    )


def _seed_category(categories: FakeExamCategoryRepository) -> ExamCategoryDTO:
    audit = FakeAuditLogWriter()
    return CreateExamCategoryUseCase(
        categories=categories, audit=audit, clock=FakeClock(_NOW)
    ).execute(
        CreateExamCategoryCommand(
            actor=_actor(permissions=frozenset({"catalog.manage"})), name="Hematologia"
        )
    )


def _create_command(category_id: object, **overrides: object) -> CreateExamCommand:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"catalog.manage", "pricing.read"})),
        "name": "Hemograma completo",
        "category_id": category_id,
        "price_base": Decimal("85.00"),
        "description": None,
        "species_ids": frozenset({_DOG_SPECIES_ID}),
    }
    defaults.update(overrides)
    return CreateExamCommand(**defaults)  # type: ignore[arg-type]


def test_create_exam_succeeds_and_audits() -> None:
    categories = FakeExamCategoryRepository()
    category = _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    use_case = CreateExamUseCase(
        exams=exams,
        categories=categories,
        species=_species_repo(),
        audit=audit,
        clock=FakeClock(_NOW),
        code_generator=lambda: "HEM001",
    )

    result = use_case.execute(_create_command(category.id))

    assert result.code == "HEM001"
    assert result.price_base == Decimal("85.00")
    assert result.status == ExamStatus.ACTIVE.value
    assert audit.entries[0].action == "exams.created"


def test_create_exam_without_permission_is_forbidden() -> None:
    categories = FakeExamCategoryRepository()
    category = _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    use_case = CreateExamUseCase(
        exams=exams,
        categories=categories,
        species=_species_repo(),
        audit=audit,
        clock=FakeClock(_NOW),
    )

    with pytest.raises(ForbiddenError):
        use_case.execute(_create_command(category.id, actor=_actor(permissions=frozenset())))


def test_create_exam_with_unknown_category_not_found() -> None:
    categories = FakeExamCategoryRepository()
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    use_case = CreateExamUseCase(
        exams=exams,
        categories=categories,
        species=_species_repo(),
        audit=audit,
        clock=FakeClock(_NOW),
    )

    with pytest.raises(NotFoundError):
        use_case.execute(_create_command(uuid4()))


def test_create_exam_with_unknown_species_is_invalid() -> None:
    categories = FakeExamCategoryRepository()
    category = _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    use_case = CreateExamUseCase(
        exams=exams,
        categories=categories,
        species=_species_repo(),
        audit=audit,
        clock=FakeClock(_NOW),
    )

    with pytest.raises(ValidationError):
        use_case.execute(_create_command(category.id, species_ids=frozenset({uuid4()})))


def test_create_exam_retries_generated_code_collision() -> None:
    categories = FakeExamCategoryRepository()
    category = _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    generated_codes = iter(("HEM001", "HEM001", "BIO00001"))
    use_case = CreateExamUseCase(
        exams=exams,
        categories=categories,
        species=_species_repo(),
        audit=audit,
        clock=FakeClock(_NOW),
        code_generator=lambda: next(generated_codes),
    )
    use_case.execute(_create_command(category.id))
    second = use_case.execute(_create_command(category.id, name="Outro exame"))

    assert second.code == "BIO00001"


def test_get_exam_omits_price_without_pricing_permission() -> None:
    categories = FakeExamCategoryRepository()
    category = _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    created = CreateExamUseCase(
        exams=exams,
        categories=categories,
        species=_species_repo(),
        audit=audit,
        clock=FakeClock(_NOW),
    ).execute(_create_command(category.id))

    use_case = GetExamUseCase(exams=exams)
    result = use_case.execute(
        GetExamQuery(actor=_actor(permissions=frozenset({"catalog.read"})), exam_id=created.id)
    )

    assert result.price_base is None


def test_get_exam_includes_price_with_pricing_permission() -> None:
    categories = FakeExamCategoryRepository()
    category = _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    created = CreateExamUseCase(
        exams=exams,
        categories=categories,
        species=_species_repo(),
        audit=audit,
        clock=FakeClock(_NOW),
    ).execute(_create_command(category.id))

    use_case = GetExamUseCase(exams=exams)
    result = use_case.execute(
        GetExamQuery(
            actor=_actor(permissions=frozenset({"catalog.read", "pricing.read"})),
            exam_id=created.id,
        )
    )

    assert result.price_base == Decimal("85.00")


def test_update_exam_with_stale_row_version_conflicts() -> None:
    categories = FakeExamCategoryRepository()
    category = _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    created = CreateExamUseCase(
        exams=exams,
        categories=categories,
        species=_species_repo(),
        audit=audit,
        clock=FakeClock(_NOW),
    ).execute(_create_command(category.id))

    use_case = UpdateExamUseCase(
        exams=exams,
        categories=categories,
        species=_species_repo(),
        audit=audit,
        clock=FakeClock(_NOW),
    )
    with pytest.raises(ConflictError):
        use_case.execute(
            UpdateExamCommand(
                actor=_actor(permissions=frozenset({"catalog.manage"})),
                exam_id=created.id,
                name="Hemograma completo renomeado",
                category_id=category.id,
                price_base=Decimal("90.00"),
                description=None,
                species_ids=frozenset({_DOG_SPECIES_ID}),
                status=ExamStatus.ACTIVE.value,
                expected_row_version=created.row_version + 1,
            )
        )


def test_deactivate_exam_preserves_record() -> None:
    categories = FakeExamCategoryRepository()
    category = _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    created = CreateExamUseCase(
        exams=exams,
        categories=categories,
        species=_species_repo(),
        audit=audit,
        clock=FakeClock(_NOW),
    ).execute(_create_command(category.id))

    use_case = DeactivateExamUseCase(exams=exams, audit=audit, clock=FakeClock(_NOW))
    result = use_case.execute(
        DeactivateExamCommand(
            actor=_actor(permissions=frozenset({"catalog.manage", "pricing.read"})),
            exam_id=created.id,
        )
    )

    assert result.status == ExamStatus.INACTIVE.value
    stored = exams.get_by_id(created.id)
    assert stored is not None
    assert stored.name == created.name


def test_list_exams_requires_permission() -> None:
    exams = FakeExamRepository()
    use_case = ListExamsUseCase(exams=exams)

    with pytest.raises(ForbiddenError):
        use_case.execute(
            ListExamsQuery(actor=_actor(permissions=frozenset()), page=1, page_size=20)
        )
