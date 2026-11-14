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


def test_import_requires_permission_and_reports_each_invalid_row_without_stopping_the_valid_ones() -> (
    None
):
    categories = FakeExamCategoryRepository()
    category = _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    manager = _actor(permissions=frozenset({"catalog.manage"}))
    CreateExamUseCase(
        exams=exams,
        categories=categories,
        species=_species_repo(),
        audit=FakeAuditLogWriter(),
        clock=FakeClock(_NOW),
        code_generator=lambda: "HEM900",
    ).execute(
        CreateExamCommand(
            actor=manager,
            name="Já existente",
            category_id=category.id,
            price_base=Decimal("50.00"),
            description=None,
            species_ids=frozenset({_DOG_SPECIES_ID}),
        )
    )
    use_case = _use_case(exams=exams, categories=categories, audit=audit)

    with pytest.raises(ForbiddenError):
        use_case.execute(ImportExamsCommand(actor=_actor(permissions=frozenset()), rows=(_row(),)))

    result = use_case.execute(
        ImportExamsCommand(
            actor=manager,
            rows=(
                _row(line=2, code="HEM001"),  # válida
                _row(line=3, code="HEM002", category_name="Categoria inexistente"),
                _row(line=4, code="HEM003", species_names=("Espécie inexistente",)),
                _row(line=5, code="hem001", name="Duplicado no arquivo"),
                _row(line=6, code="HEM900", name="Duplicado no banco"),
                _row(line=7, code="HEM004", price_base="not-a-number"),
                _row(line=8, code="HEM005", active=False),  # válida, entra inativa
            ),
        )
    )

    assert result.imported_count == 2
    assert [error.line for error in result.errors] == [3, 4, 5, 6, 7]
    assert result.errors[4].message == "Preço base inválido."
    assert "Categoria inexistente" in result.errors[0].message
    assert "Espécie inexistente" in result.errors[1].message
    assert "HEM900" in result.errors[3].message
    stored = exams.get_by_code("HEM001")
    assert stored is not None
    assert stored.name == "Hemograma completo"
    inactive = exams.get_by_code("HEM005")
    assert inactive is not None
    assert inactive.status.value == "INACTIVE"
    for rejected in ("HEM002", "HEM003", "HEM004"):
        assert exams.get_by_code(rejected) is None
    assert audit.entries[0].action == "exams.imported"
