from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.imports.application.import_exam_categories import (
    SHEET_NAME,
    ImportExamCategoriesCommand,
    ImportExamCategoriesUseCase,
)
from app.shared.domain.errors import ForbiddenError
from tests.catalog.fakes import FakeAuditLogWriter, FakeExamCategoryRepository
from tests.imports.fakes import FakeClock, FakeImportStagingRowRepository, make_staging_row

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _use_case(
    *, staging_rows: FakeImportStagingRowRepository, categories: FakeExamCategoryRepository
) -> ImportExamCategoriesUseCase:
    return ImportExamCategoriesUseCase(
        staging_rows=staging_rows,
        categories=categories,
        audit=FakeAuditLogWriter(),
        clock=FakeClock(_NOW),
    )


def _stage_suporte(
    staging_rows: FakeImportStagingRowRepository, batch_id: UUID, names: list[str]
) -> None:
    staging_rows.add_many(
        [
            make_staging_row(
                batch_id=batch_id,
                sheet_name=SHEET_NAME,
                source_row_number=row_number,
                raw_data={"A": name},
            )
            for row_number, name in enumerate(names, start=3)
        ]
    )


def test_import_without_permission_is_forbidden() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_suporte(staging_rows, batch_id, ["Hematológicos"])
    use_case = _use_case(staging_rows=staging_rows, categories=FakeExamCategoryRepository())

    with pytest.raises(ForbiddenError):
        use_case.execute(
            ImportExamCategoriesCommand(
                actor_id=uuid4(), actor_permissions=frozenset(), batch_id=batch_id
            )
        )


def test_import_creates_all_distinct_categories() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    names = [
        "Hematológicos",
        "Bioquímicos",
        "Urinários",
        "Perfis",
        "Tercerizados",
        "Dermatológicos",
        "Coprológicos",
    ]
    _stage_suporte(staging_rows, batch_id, names)
    categories = FakeExamCategoryRepository()
    use_case = _use_case(staging_rows=staging_rows, categories=categories)

    result = use_case.execute(
        ImportExamCategoriesCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 7
    for name in names:
        assert categories.get_by_name(name) is not None


def test_import_skips_header_row_at_row_2() -> None:
    # Regression: the real `Suporte` sheet has no title row (unlike the
    # other master sheets) — its header lands on row 2, not row 1. A wrong
    # `_FIRST_DATA_ROW` here would import "Tipo Exame" (the header text
    # itself) as if it were a real category.
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    staging_rows.add_many(
        [
            make_staging_row(
                batch_id=batch_id,
                sheet_name=SHEET_NAME,
                source_row_number=2,
                raw_data={"A": "Tipo Exame"},
            ),
            make_staging_row(
                batch_id=batch_id,
                sheet_name=SHEET_NAME,
                source_row_number=3,
                raw_data={"A": "Hematológicos"},
            ),
        ]
    )
    categories = FakeExamCategoryRepository()
    use_case = _use_case(staging_rows=staging_rows, categories=categories)

    result = use_case.execute(
        ImportExamCategoriesCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 1
    assert categories.get_by_name("Tipo Exame") is None
    assert categories.get_by_name("Hematológicos") is not None


def test_reimporting_is_idempotent() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_suporte(staging_rows, batch_id, ["Perfis"])
    categories = FakeExamCategoryRepository()
    use_case = _use_case(staging_rows=staging_rows, categories=categories)
    command = ImportExamCategoriesCommand(
        actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
    )

    first = use_case.execute(command)
    second = use_case.execute(command)

    assert first.imported_count == 1
    assert second.imported_count == 0
    assert second.skipped_existing_count == 1
