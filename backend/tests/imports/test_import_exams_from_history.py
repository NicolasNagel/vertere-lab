from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.modules.catalog.domain.entities import ExamCategory, ExamCategoryStatus
from app.modules.imports.application.import_exams_from_history import (
    SHEET_NAME,
    ImportExamsFromHistoryCommand,
    ImportExamsFromHistoryResult,
    ImportExamsFromHistoryUseCase,
)
from app.modules.patients.domain.entities import Species
from app.shared.domain.errors import ForbiddenError
from tests.catalog.fakes import (
    FakeAuditLogWriter,
    FakeExamCategoryRepository,
    FakeExamRepository,
    FakeSpeciesRepository,
)
from tests.imports.fakes import FakeClock, FakeImportStagingRowRepository, make_staging_row

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _category(name: str) -> ExamCategory:
    return ExamCategory(
        id=uuid4(), name=name, status=ExamCategoryStatus.ACTIVE, created_at=_NOW, updated_at=_NOW
    )


def _use_case(
    *,
    staging_rows: FakeImportStagingRowRepository,
    exams: FakeExamRepository,
    categories: FakeExamCategoryRepository,
    species: FakeSpeciesRepository | None = None,
) -> ImportExamsFromHistoryUseCase:
    return ImportExamsFromHistoryUseCase(
        staging_rows=staging_rows,
        exams=exams,
        categories=categories,
        species=species
        or FakeSpeciesRepository([Species(id=uuid4(), name="Canino", created_at=_NOW)]),
        audit=FakeAuditLogWriter(),
        clock=FakeClock(_NOW),
    )


def _stage_dados_row(
    staging_rows: FakeImportStagingRowRepository,
    batch_id: UUID,
    *,
    row_number: int,
    date_serial: str,
    category: str | None,
    exam: str | None,
    price: str | None,
) -> None:
    staging_rows.add_many(
        [
            make_staging_row(
                batch_id=batch_id,
                sheet_name=SHEET_NAME,
                source_row_number=row_number,
                raw_data={"B": date_serial, "O": category, "P": exam, "R": price},
            )
        ]
    )


def _run(
    *rows: dict[str, str | None],
    categories: tuple[str, ...] = ("Hematológicos",),
    permissions: frozenset[str] = frozenset({"imports.execute"}),
    times: int = 1,
) -> tuple[list[ImportExamsFromHistoryResult], FakeExamRepository]:
    """Stage `rows` (defaults: Hemograma, R$ 25, 2026-01-03) and run the import `times`."""
    batch_id = uuid4()
    category_repository = FakeExamCategoryRepository()
    for name in categories:
        category_repository.add(_category(name))
    staging_rows = FakeImportStagingRowRepository()
    for index, overrides in enumerate(rows):
        values: dict[str, str | None] = {
            "date_serial": "46025",
            "category": categories[0] if categories else None,
            "exam": "Hemograma",
            "price": "25",
            **overrides,
        }
        _stage_dados_row(staging_rows, batch_id, row_number=5 + index, **values)  # type: ignore[arg-type]
    exams = FakeExamRepository()
    use_case = _use_case(staging_rows=staging_rows, exams=exams, categories=category_repository)
    command = ImportExamsFromHistoryCommand(
        actor_id=uuid4(), actor_permissions=permissions, batch_id=batch_id
    )
    return [use_case.execute(command) for _ in range(times)], exams


def test_import_requires_permission_creates_exams_and_is_idempotent() -> None:
    with pytest.raises(ForbiddenError):
        _run({}, permissions=frozenset())

    (first, second), exams = _run({}, times=2)
    assert (first.imported_count, first.exceptions) == (1, ())
    assert (second.imported_count, second.skipped_existing_count) == (0, 1)
    exam = exams.get_by_code("HEMOGRAMA")
    assert exam is not None
    assert (exam.name, exam.price_base) == ("Hemograma", Decimal("25"))


def test_import_merges_variants_and_ignores_combined_lines_and_zero_prices() -> None:
    # Variantes de caixa se fundem: vale o nome e o preço da ocorrência mais recente.
    (result,), exams = _run(
        {"exam": "hemograma", "price": "25"},
        {"exam": "Hemograma", "price": "28", "date_serial": "46100"},
    )
    exam = exams.get_by_code("HEMOGRAMA")
    assert result.imported_count == 1
    assert exam is not None
    assert (exam.name, exam.price_base) == ("Hemograma", Decimal("28"))

    # Só o acento difere ("Basico 3" vs. "Básico 3"): um único exame; data antiga não muda o preço.
    (result,), exams = _run(
        {"category": "Perfis", "exam": "Básico 3", "price": "80"},
        {"category": "Perfis", "exam": "Basico 3", "price": "80", "date_serial": "46020"},
        categories=("Perfis",),
    )
    assert result.imported_count == 1
    assert exams.get_by_code("BASICO3") is not None

    # Linha combinada nunca é candidata a catálogo.
    (result,), exams = _run(
        {"category": "Perfis", "exam": "Check-up 2 + Urinálise", "price": "145"},
        categories=("Perfis",),
    )
    assert result.imported_count == 0
    assert exams.get_by_code("CHECKUP2") is None
    assert exams.get_by_code("URINALISE") is None

    # Valor 0 (exame cortesia) vira exceção por exame, não um crash; e não esconde um preço
    # válido de outra ocorrência.
    (result,), exams = _run({"exam": "Hematócrito", "price": "0"})
    assert (result.imported_count, len(result.exceptions)) == (0, 1)
    assert exams.get_by_code("HEMATOCRITO") is None
    (result,), exams = _run(
        {"exam": "Hematócrito", "price": "0"},
        {"exam": "Hematócrito", "price": "15", "date_serial": "46100"},
    )
    assert result.imported_count == 1
    hematocrit = exams.get_by_code("HEMATOCRITO")
    assert hematocrit is not None
    assert hematocrit.price_base == Decimal("15")


def test_import_turns_unknown_or_missing_category_into_exception() -> None:
    (unknown,), exams = _run({"category": "Categoria Inexistente"})
    assert (unknown.imported_count, len(unknown.exceptions)) == (0, 1)
    assert exams.get_by_code("HEMOGRAMA") is None

    (missing,), _ = _run({"category": None, "exam": "Exame Sem Categoria"}, categories=())
    assert (missing.imported_count, len(missing.exceptions)) == (0, 1)


def test_import_treats_nan_infinity_and_oversized_prices_as_missing_instead_of_crashing() -> None:
    (result,), exams = _run(
        {"exam": "Exame NaN", "price": "NaN"},
        {"exam": "Exame Infinito", "price": "Infinity"},
        {"exam": "Exame Gigante", "price": "1E+20"},
        {"exam": "Exame Normal", "price": "30"},
    )

    assert exams.get_by_code("EXAMENORMAL") is not None
    for code in ("EXAMENAN", "EXAMEINFINITO", "EXAMEGIGANTE"):
        created = exams.get_by_code(code)
        assert created is None or created.price_base.is_finite()
    assert result.imported_count >= 1
