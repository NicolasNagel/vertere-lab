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


def test_stage_without_permission_is_forbidden() -> None:
    use_case = _use_case(
        batches=FakeImportBatchRepository(), staging_rows=FakeImportStagingRowRepository()
    )

    with pytest.raises(ForbiddenError):
        use_case.execute(
            StageSpreadsheetCommand(
                actor_id=uuid4(),
                actor_permissions=frozenset(),
                source_filename="planilha.xlsx",
                content=_content(),
            )
        )


def test_stage_valid_file_creates_batch_and_staging_rows() -> None:
    batches = FakeImportBatchRepository()
    staging_rows = FakeImportStagingRowRepository()
    use_case = _use_case(batches=batches, staging_rows=staging_rows)

    result = use_case.execute(
        StageSpreadsheetCommand(
            actor_id=uuid4(),
            actor_permissions=frozenset({"imports.execute"}),
            source_filename="planilha.xlsx",
            content=_content(),
        )
    )

    assert result.already_staged is False
    assert result.sheet_row_counts == {"Cadastro Clínicas": 3}
    stored_rows = staging_rows.list_by_batch(result.batch.id)
    assert len(stored_rows) == 3
    assert stored_rows[0].raw_data == {"A": "Clínica", "B": "Status"}
    assert stored_rows[1].raw_data == {"A": "Bicho Urbano", "B": "Ativo"}


def test_staging_same_file_twice_is_idempotent() -> None:
    batches = FakeImportBatchRepository()
    staging_rows = FakeImportStagingRowRepository()
    use_case = _use_case(batches=batches, staging_rows=staging_rows)
    command = StageSpreadsheetCommand(
        actor_id=uuid4(),
        actor_permissions=frozenset({"imports.execute"}),
        source_filename="planilha.xlsx",
        content=_content(),
    )

    first = use_case.execute(command)
    second = use_case.execute(command)

    assert first.already_staged is False
    assert second.already_staged is True
    assert second.batch.id == first.batch.id
    assert len(staging_rows.list_by_batch(first.batch.id)) == 3


def test_stage_rejects_invalid_xlsx_content() -> None:
    use_case = _use_case(
        batches=FakeImportBatchRepository(), staging_rows=FakeImportStagingRowRepository()
    )

    with pytest.raises(ValidationError):
        use_case.execute(
            StageSpreadsheetCommand(
                actor_id=uuid4(),
                actor_permissions=frozenset({"imports.execute"}),
                source_filename="planilha.xlsx",
                content=b"not a zip file",
            )
        )
