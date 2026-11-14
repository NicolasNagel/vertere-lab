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


def _command(
    batch_id: UUID, *, permissions: frozenset[str] = frozenset({"imports.execute"})
) -> ImportExamCategoriesCommand:
    return ImportExamCategoriesCommand(
        actor_id=uuid4(), actor_permissions=permissions, batch_id=batch_id
    )


def test_import_requires_permission_creates_distinct_categories_and_is_idempotent() -> None:
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

    with pytest.raises(ForbiddenError):
        use_case.execute(_command(batch_id, permissions=frozenset()))

    first = use_case.execute(_command(batch_id))
    second = use_case.execute(_command(batch_id))

    assert first.imported_count == 7
    assert all(categories.get_by_name(name) is not None for name in names)
    assert (second.imported_count, second.skipped_existing_count) == (0, 7)


def test_import_skips_the_header_row_at_row_2() -> None:
    # Regressão: a planilha `Suporte` real não tem linha de título (ao contrário das outras
    # mestres), então o cabeçalho cai na linha 2. Um `_FIRST_DATA_ROW` errado importaria
    # "Tipo Exame" (o próprio cabeçalho) como se fosse categoria.
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

    result = _use_case(staging_rows=staging_rows, categories=categories).execute(_command(batch_id))

    assert result.imported_count == 1
    assert categories.get_by_name("Tipo Exame") is None
    assert categories.get_by_name("Hematológicos") is not None
