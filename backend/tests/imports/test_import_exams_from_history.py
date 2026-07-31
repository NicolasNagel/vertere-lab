from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.modules.catalog.domain.entities import ExamCategory, ExamCategoryStatus
from app.modules.imports.application.import_exams_from_history import (
    SHEET_NAME,
    ImportExamsFromHistoryCommand,
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


def test_import_without_permission_is_forbidden() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        date_serial="46025",
        category="Hematológicos",
        exam="Hemograma",
        price="25",
    )
    use_case = _use_case(
        staging_rows=staging_rows,
        exams=FakeExamRepository(),
        categories=FakeExamCategoryRepository(),
    )

    with pytest.raises(ForbiddenError):
        use_case.execute(
            ImportExamsFromHistoryCommand(
                actor_id=uuid4(), actor_permissions=frozenset(), batch_id=batch_id
            )
        )


def test_import_creates_exam_from_standalone_row() -> None:
    batch_id = uuid4()
    categories = FakeExamCategoryRepository()
    categories.add(_category("Hematológicos"))
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        date_serial="46025",
        category="Hematológicos",
        exam="Hemograma",
        price="25",
    )
    exams = FakeExamRepository()
    use_case = _use_case(staging_rows=staging_rows, exams=exams, categories=categories)

    result = use_case.execute(
        ImportExamsFromHistoryCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 1
    assert result.exceptions == ()
    exam = exams.get_by_code("HEMOGRAMA")
    assert exam is not None
    assert exam.name == "Hemograma"
    assert exam.price_base == Decimal("25")


def test_combined_exam_line_is_never_a_catalog_candidate() -> None:
    batch_id = uuid4()
    categories = FakeExamCategoryRepository()
    categories.add(_category("Perfis"))
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        date_serial="46025",
        category="Perfis",
        exam="Check-up 2 + Urinálise",
        price="145",
    )
    exams = FakeExamRepository()
    use_case = _use_case(staging_rows=staging_rows, exams=exams, categories=categories)

    result = use_case.execute(
        ImportExamsFromHistoryCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 0
    assert exams.get_by_code("CHECKUP2") is None
    assert exams.get_by_code("URINALISE") is None


def test_case_variants_merge_and_most_recent_price_wins() -> None:
    batch_id = uuid4()
    categories = FakeExamCategoryRepository()
    categories.add(_category("Hematológicos"))
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        date_serial="46025",  # earlier date
        category="Hematológicos",
        exam="hemograma",
        price="25",
    )
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=6,
        date_serial="46100",  # later date
        category="Hematológicos",
        exam="Hemograma",
        price="28",
    )
    exams = FakeExamRepository()
    use_case = _use_case(staging_rows=staging_rows, exams=exams, categories=categories)

    result = use_case.execute(
        ImportExamsFromHistoryCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 1
    exam = exams.get_by_code("HEMOGRAMA")
    assert exam is not None
    assert exam.name == "Hemograma"  # most recent occurrence's casing
    assert exam.price_base == Decimal("28")  # most recent occurrence's price


def test_accent_only_variants_merge_into_one_exam() -> None:
    # Regression found via QA against the real spreadsheet: "Basico 3" (a
    # typo missing the accent) and "Básico 3" were becoming two separate
    # catalog rows for the same panel — case-only folding didn't catch it.
    batch_id = uuid4()
    categories = FakeExamCategoryRepository()
    categories.add(_category("Perfis"))
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        date_serial="46025",
        category="Perfis",
        exam="Básico 3",
        price="80",
    )
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=6,
        date_serial="46020",  # earlier date — must not override the price
        category="Perfis",
        exam="Basico 3",
        price="80",
    )
    exams = FakeExamRepository()
    use_case = _use_case(staging_rows=staging_rows, exams=exams, categories=categories)

    result = use_case.execute(
        ImportExamsFromHistoryCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 1
    assert exams.get_by_code("BASICO3") is not None


def test_unknown_category_becomes_exception() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        date_serial="46025",
        category="Categoria Inexistente",
        exam="Hemograma",
        price="25",
    )
    exams = FakeExamRepository()
    use_case = _use_case(
        staging_rows=staging_rows, exams=exams, categories=FakeExamCategoryRepository()
    )

    result = use_case.execute(
        ImportExamsFromHistoryCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 0
    assert len(result.exceptions) == 1
    assert exams.get_by_code("HEMOGRAMA") is None


def test_zero_price_is_treated_as_no_price_not_a_crash() -> None:
    # Regression found via QA against an updated version of the real spreadsheet: some rows
    # record a bundled/complementary exam at "Valor" = 0 (e.g. "Hematócrito" given free
    # alongside another paid item). `Exam.price_base` requires > 0, so picking a zero price
    # used to crash the whole use case with an unhandled ValueError instead of degrading to a
    # per-exam exception.
    batch_id = uuid4()
    categories = FakeExamCategoryRepository()
    categories.add(_category("Hematológicos"))
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        date_serial="46025",
        category="Hematológicos",
        exam="Hematócrito",
        price="0",
    )
    exams = FakeExamRepository()
    use_case = _use_case(staging_rows=staging_rows, exams=exams, categories=categories)

    result = use_case.execute(
        ImportExamsFromHistoryCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 0
    assert len(result.exceptions) == 1
    assert exams.get_by_code("HEMATOCRITO") is None


def test_zero_price_occurrence_does_not_shadow_a_valid_price_on_another_occurrence() -> None:
    batch_id = uuid4()
    categories = FakeExamCategoryRepository()
    categories.add(_category("Hematológicos"))
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        date_serial="46025",
        category="Hematológicos",
        exam="Hematócrito",
        price="0",  # bundled free this time
    )
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=6,
        date_serial="46100",
        category="Hematológicos",
        exam="Hematócrito",
        price="15",  # charged normally another time
    )
    exams = FakeExamRepository()
    use_case = _use_case(staging_rows=staging_rows, exams=exams, categories=categories)

    result = use_case.execute(
        ImportExamsFromHistoryCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 1
    exam = exams.get_by_code("HEMATOCRITO")
    assert exam is not None
    assert exam.price_base == Decimal("15")


def test_missing_category_across_all_occurrences_becomes_exception() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        date_serial="46025",
        category=None,
        exam="Exame Sem Categoria",
        price="25",
    )
    exams = FakeExamRepository()
    use_case = _use_case(
        staging_rows=staging_rows, exams=exams, categories=FakeExamCategoryRepository()
    )

    result = use_case.execute(
        ImportExamsFromHistoryCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 0
    assert len(result.exceptions) == 1


def test_reimporting_same_exam_is_idempotent() -> None:
    batch_id = uuid4()
    categories = FakeExamCategoryRepository()
    categories.add(_category("Hematológicos"))
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        date_serial="46025",
        category="Hematológicos",
        exam="Hemograma",
        price="25",
    )
    exams = FakeExamRepository()
    use_case = _use_case(staging_rows=staging_rows, exams=exams, categories=categories)
    command = ImportExamsFromHistoryCommand(
        actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
    )

    first = use_case.execute(command)
    second = use_case.execute(command)

    assert first.imported_count == 1
    assert second.imported_count == 0
    assert second.skipped_existing_count == 1
