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


def test_dry_run_raises_not_found_for_unknown_batch() -> None:
    use_case = DryRunPriceTableImportUseCase(
        staging_rows=FakeImportStagingRowRepository(),
        batches=FakeImportBatchRepository(),
        exams=FakeExamRepository(),
        audit=FakeAuditLogWriter(),
        clock=FakeClock(_NOW),
    )

    with pytest.raises(NotFoundError):
        use_case.execute(
            RunPriceTableImportCommand(
                actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=uuid4()
            )
        )


def test_dry_run_updates_price_for_real_but_caller_controls_persistence() -> None:
    batch_id, batches, staging_rows, exams = _setup()
    use_case = DryRunPriceTableImportUseCase(
        staging_rows=staging_rows,
        batches=batches,
        exams=exams,
        audit=FakeAuditLogWriter(),
        clock=FakeClock(_NOW),
    )

    result = use_case.execute(
        RunPriceTableImportCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 1
    assert len(result.exceptions) == 1
    # The use case itself has no opinion on commit — it always runs the phase for real against
    # the fakes, same as the xlsx pipeline's dry-run. The router not calling uow.commit() is
    # what actually makes this a "dry run" against a real database.
    batch = batches.get_by_id(batch_id)
    assert batch is not None
    assert batch.status.value == "STAGED"


def test_commit_persists_exceptions_and_marks_batch_committed() -> None:
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

    result = use_case.execute(
        RunPriceTableImportCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 1
    persisted = exceptions.list_by_batch(batch_id)
    assert len(persisted) == 1
    assert persisted[0].phase == "price_table"
    batch = batches.get_by_id(batch_id)
    assert batch is not None
    assert batch.status.value == "COMMITTED"


def test_reimporting_same_batch_does_not_duplicate_persisted_exceptions() -> None:
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
    command = RunPriceTableImportCommand(
        actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
    )

    use_case.execute(command)
    second = use_case.execute(command)

    assert second.imported_count == 0  # same price now, no-op
    assert len(exceptions.list_by_batch(batch_id)) == 1  # not duplicated
