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
from app.modules.catalog.application.dtos import ExamCategoryDTO
from app.modules.catalog.application.import_exams import (
    ExamImportRow,
    ImportExamsCommand,
    ImportExamsUseCase,
)
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.domain.entities import Species
from app.shared.domain.errors import ForbiddenError
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
        id=uuid4(),
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


def _seed_category(
    categories: FakeExamCategoryRepository, *, name: str = "Hematologia"
) -> ExamCategoryDTO:
    audit = FakeAuditLogWriter()
    return CreateExamCategoryUseCase(
        categories=categories, audit=audit, clock=FakeClock(_NOW)
    ).execute(
        CreateExamCategoryCommand(
            actor=_actor(permissions=frozenset({"catalog.manage"})), name=name
        )
    )


def _row(**overrides: object) -> ExamImportRow:
    defaults: dict[str, object] = {
        "line": 2,
        "code": "HEM001",
        "name": "Hemograma completo",
        "category_name": "Hematologia",
        "price_base": "85.00",
        "description": None,
        "plantao_surcharge_fixed": None,
        "plantao_surcharge_percent": None,
        "species_names": ("Cão",),
        "active": True,
    }
    defaults.update(overrides)
    return ExamImportRow(**defaults)  # type: ignore[arg-type]


def _use_case(
    *,
    exams: FakeExamRepository,
    categories: FakeExamCategoryRepository,
    audit: FakeAuditLogWriter,
) -> ImportExamsUseCase:
    return ImportExamsUseCase(
        exams=exams,
        categories=categories,
        species=_species_repo(),
        audit=audit,
        clock=FakeClock(_NOW),
    )


def test_import_without_permission_is_forbidden() -> None:
    use_case = _use_case(
        exams=FakeExamRepository(),
        categories=FakeExamCategoryRepository(),
        audit=FakeAuditLogWriter(),
    )

    with pytest.raises(ForbiddenError):
        use_case.execute(ImportExamsCommand(actor=_actor(permissions=frozenset()), rows=(_row(),)))


def test_import_valid_row_creates_exam_and_audits() -> None:
    categories = FakeExamCategoryRepository()
    _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    use_case = _use_case(exams=exams, categories=categories, audit=audit)

    result = use_case.execute(
        ImportExamsCommand(actor=_actor(permissions=frozenset({"catalog.manage"})), rows=(_row(),))
    )

    assert result.imported_count == 1
    assert result.errors == ()
    stored = exams.get_by_code("HEM001")
    assert stored is not None
    assert stored.name == "Hemograma completo"
    assert audit.entries[0].action == "exams.imported"


def test_import_reports_unknown_category_without_stopping_valid_rows() -> None:
    categories = FakeExamCategoryRepository()
    _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    use_case = _use_case(exams=exams, categories=categories, audit=audit)

    result = use_case.execute(
        ImportExamsCommand(
            actor=_actor(permissions=frozenset({"catalog.manage"})),
            rows=(
                _row(line=2, code="HEM001"),
                _row(line=3, code="HEM002", category_name="Categoria inexistente"),
            ),
        )
    )

    assert result.imported_count == 1
    assert exams.get_by_code("HEM001") is not None
    assert exams.get_by_code("HEM002") is None
    assert len(result.errors) == 1
    assert result.errors[0].line == 3
    assert "Categoria inexistente" in result.errors[0].message


def test_import_reports_unknown_species() -> None:
    categories = FakeExamCategoryRepository()
    _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    use_case = _use_case(exams=exams, categories=categories, audit=audit)

    result = use_case.execute(
        ImportExamsCommand(
            actor=_actor(permissions=frozenset({"catalog.manage"})),
            rows=(_row(species_names=("Espécie inexistente",)),),
        )
    )

    assert result.imported_count == 0
    assert "Espécie inexistente" in result.errors[0].message


def test_import_reports_duplicate_code_within_file() -> None:
    categories = FakeExamCategoryRepository()
    _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    use_case = _use_case(exams=exams, categories=categories, audit=audit)

    result = use_case.execute(
        ImportExamsCommand(
            actor=_actor(permissions=frozenset({"catalog.manage"})),
            rows=(
                _row(line=2, code="HEM001"),
                _row(line=3, code="hem001", name="Duplicado"),
            ),
        )
    )

    assert result.imported_count == 1
    assert len(result.errors) == 1
    assert result.errors[0].line == 3


def test_import_reports_duplicate_code_already_in_database() -> None:
    categories = FakeExamCategoryRepository()
    category = _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    CreateExamUseCase(
        exams=exams,
        categories=categories,
        species=_species_repo(),
        audit=audit,
        clock=FakeClock(_NOW),
    ).execute(
        CreateExamCommand(
            actor=_actor(permissions=frozenset({"catalog.manage"})),
            code="HEM001",
            name="Já existente",
            category_id=category.id,
            price_base=Decimal("50.00"),
            description=None,
            plantao_surcharge_fixed=None,
            plantao_surcharge_percent=None,
            species_ids=frozenset({_DOG_SPECIES_ID}),
        )
    )
    use_case = _use_case(exams=exams, categories=categories, audit=audit)

    result = use_case.execute(
        ImportExamsCommand(actor=_actor(permissions=frozenset({"catalog.manage"})), rows=(_row(),))
    )

    assert result.imported_count == 0
    assert "HEM001" in result.errors[0].message


def test_import_reports_invalid_price() -> None:
    categories = FakeExamCategoryRepository()
    _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    use_case = _use_case(exams=exams, categories=categories, audit=audit)

    result = use_case.execute(
        ImportExamsCommand(
            actor=_actor(permissions=frozenset({"catalog.manage"})),
            rows=(_row(price_base="not-a-number"),),
        )
    )

    assert result.imported_count == 0
    assert result.errors[0].message == "Preço base inválido."


def test_import_inactive_row_creates_inactive_exam() -> None:
    categories = FakeExamCategoryRepository()
    _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    use_case = _use_case(exams=exams, categories=categories, audit=audit)

    result = use_case.execute(
        ImportExamsCommand(
            actor=_actor(permissions=frozenset({"catalog.manage"})),
            rows=(_row(active=False),),
        )
    )

    assert result.imported_count == 1
    stored = exams.get_by_code("HEM001")
    assert stored is not None
    assert stored.status.value == "INACTIVE"
