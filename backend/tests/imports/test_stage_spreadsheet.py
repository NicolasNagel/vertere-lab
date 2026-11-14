from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.imports.application.stage_spreadsheet import (
    StageSpreadsheetCommand,
    StageSpreadsheetUseCase,
)
from app.shared.domain.errors import ForbiddenError, ValidationError
from tests.imports.fakes import FakeClock, FakeImportBatchRepository, FakeImportStagingRowRepository
from tests.imports.xlsx_builder import build_xlsx

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _use_case(
    *, batches: FakeImportBatchRepository, staging_rows: FakeImportStagingRowRepository
) -> StageSpreadsheetUseCase:
    return StageSpreadsheetUseCase(
        batches=batches, staging_rows=staging_rows, clock=FakeClock(_NOW)
    )


def _content() -> bytes:
    return build_xlsx(
        "Cadastro Clínicas",
        [["Clínica", "Status"], ["Bicho Urbano", "Ativo"], ["Schweitzer", "Ativo"]],
    )


def _command(
    *, permissions: frozenset[str] = frozenset({"imports.execute"}), content: bytes | None = None
) -> StageSpreadsheetCommand:
    return StageSpreadsheetCommand(
        actor_id=uuid4(),
        actor_permissions=permissions,
        source_filename="planilha.xlsx",
        content=_content() if content is None else content,
    )


def test_stage_rejects_missing_permission_and_invalid_xlsx() -> None:
    use_case = _use_case(
        batches=FakeImportBatchRepository(), staging_rows=FakeImportStagingRowRepository()
    )

    with pytest.raises(ForbiddenError):
        use_case.execute(_command(permissions=frozenset()))
    with pytest.raises(ValidationError):
        use_case.execute(_command(content=b"not a zip file"))


def test_stage_creates_batch_and_rows_and_staging_the_same_file_twice_is_idempotent() -> None:
    batches = FakeImportBatchRepository()
    staging_rows = FakeImportStagingRowRepository()
    use_case = _use_case(batches=batches, staging_rows=staging_rows)

    first = use_case.execute(_command())
    second = use_case.execute(_command())

    assert first.already_staged is False
    assert first.sheet_row_counts == {"Cadastro Clínicas": 3}
    stored_rows = staging_rows.list_by_batch(first.batch.id)
    assert len(stored_rows) == 3
    assert stored_rows[0].raw_data == {"A": "Clínica", "B": "Status"}
    assert stored_rows[1].raw_data == {"A": "Bicho Urbano", "B": "Ativo"}
    assert second.already_staged is True
    assert second.batch.id == first.batch.id
    assert len(staging_rows.list_by_batch(first.batch.id)) == 3
