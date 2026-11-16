from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.modules.catalog.domain.entities import Exam, ExamStatus
from app.modules.catalog.domain.value_objects import ExamCode
from app.modules.imports.application.run_price_table_import import (
    CommitPriceTableImportUseCase,
    DryRunPriceTableImportUseCase,
    RunPriceTableImportCommand,
)
from app.modules.imports.application.stage_price_table_pdf import SHEET_NAME
from app.modules.imports.domain.entities import ImportBatch
from app.shared.domain.errors import NotFoundError
from tests.catalog.fakes import FakeAuditLogWriter, FakeExamRepository
from tests.imports.fakes import (
    FakeClock,
    FakeImportBatchRepository,
    FakeImportExceptionRepository,
    FakeImportStagingRowRepository,
    make_staging_row,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _exam(*, name: str, price: Decimal) -> Exam:
    return Exam(
        id=uuid4(),
        code=ExamCode("".join(ch for ch in name.upper() if ch.isalnum())),
        name=name,
        category_id=uuid4(),
        price_base=price,
        species_ids=frozenset({uuid4()}),
        status=ExamStatus.ACTIVE,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _setup() -> tuple[
    UUID, FakeImportBatchRepository, FakeImportStagingRowRepository, FakeExamRepository
]:
    batch_id = uuid4()
    batches = FakeImportBatchRepository()
    batches.add(
        ImportBatch(
            id=batch_id, source_filename="tabela.pdf", checksum_sha256="abc", created_at=_NOW
        )
    )
    staging_rows = FakeImportStagingRowRepository()
    staging_rows.add_many(
        [
            make_staging_row(
                batch_id=batch_id,
                sheet_name=SHEET_NAME,
                source_row_number=1,
                raw_data={"category": "perfis", "name": "Hemograma", "price": "30.00"},
            ),
            make_staging_row(
                batch_id=batch_id,
                sheet_name=SHEET_NAME,
                source_row_number=2,
                raw_data={"category": "perfis", "name": "Exame Fora Do Catálogo", "price": "10.00"},
            ),
        ]
    )
    exams = FakeExamRepository()
    exams.add(_exam(name="Hemograma", price=Decimal("28.00")))
    return batch_id, batches, staging_rows, exams


def _dry_run_use_case(
    batches: FakeImportBatchRepository,
    staging_rows: FakeImportStagingRowRepository,
    exams: FakeExamRepository,
) -> DryRunPriceTableImportUseCase:
    return DryRunPriceTableImportUseCase(
        staging_rows=staging_rows,
        batches=batches,
        exams=exams,
        audit=FakeAuditLogWriter(),
        clock=FakeClock(_NOW),
    )


def _command(batch_id: UUID) -> RunPriceTableImportCommand:
    return RunPriceTableImportCommand(
        actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
    )


def test_dry_run_rejects_unknown_batch_and_runs_for_real_leaving_persistence_to_the_caller() -> (
    None
):
    empty = _dry_run_use_case(
        FakeImportBatchRepository(), FakeImportStagingRowRepository(), FakeExamRepository()
    )
    with pytest.raises(NotFoundError):
        empty.execute(_command(uuid4()))

    batch_id, batches, staging_rows, exams = _setup()
    result = _dry_run_use_case(batches, staging_rows, exams).execute(_command(batch_id))

    assert result.imported_count == 1
    assert len(result.exceptions) == 1
    # O caso de uso não opina sobre commit: roda a fase de verdade contra os fakes, como o
    # dry-run do pipeline xlsx. É o router não chamar `uow.commit()` que faz disso um "dry run"
    # contra um banco real.
    batch = batches.get_by_id(batch_id)
    assert batch is not None
    assert batch.status.value == "STAGED"


def test_commit_persists_exceptions_once_marks_batch_committed_and_is_idempotent() -> None:
    batch_id, batches, staging_rows, exams = _setup()
    exceptions = FakeImportExceptionRepository()
    use_case = CommitPriceTableImportUseCase(
        staging_rows=staging_rows,
        batches=batches,
        exceptions=exceptions,
        exams=exams,
        audit=FakeAuditLogWriter(),
        clock=FakeClock(_NOW),
    )

    first = use_case.execute(_command(batch_id))
    second = use_case.execute(_command(batch_id))

    assert first.imported_count == 1
    assert second.imported_count == 0  # mesmo preço agora: no-op
    persisted = exceptions.list_by_batch(batch_id)
    assert [(item.phase) for item in persisted] == ["price_table"]  # não duplica ao reimportar
    batch = batches.get_by_id(batch_id)
    assert batch is not None
    assert batch.status.value == "COMMITTED"
