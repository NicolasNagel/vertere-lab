"""Dry-run/commit entry points for the price-table PDF phase — same shape as
`run_import_pipeline.py`'s `DryRunImportUseCase`/`CommitImportUseCase`, just
wrapping a single phase (`ImportPriceTableUseCase`) instead of six. Kept
separate from that pipeline rather than folded into it: this operates on a
PDF-sourced batch (its own `ImportBatch`, staged by
`StagePriceTablePdfUseCase`), not the xlsx-sourced one — running the xlsx
pipeline's six phases against a batch that only has
`"Tabela de Preços (PDF)"` staging rows would just no-op five phases for no
reason and blur what each batch is actually for.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.domain.repositories import ExamRepository
from app.modules.imports.application.import_price_table import (
    ImportPriceTableCommand,
    ImportPriceTableUseCase,
    ImportRowException,
)
from app.modules.imports.domain.entities import ImportException
from app.modules.imports.domain.repositories import (
    ImportBatchRepository,
    ImportExceptionRepository,
    ImportStagingRowRepository,
)
from app.shared.application.clock import Clock
from app.shared.domain.errors import NotFoundError

_PHASE_PRICE_TABLE = "price_table"


@dataclass(frozen=True, kw_only=True)
class RunPriceTableImportCommand:
    actor_id: UUID | None
    actor_permissions: frozenset[str]
    batch_id: UUID


@dataclass(frozen=True, kw_only=True)
class PriceTableImportResult:
    batch_id: UUID
    imported_count: int
    skipped_existing_count: int
    exceptions: tuple[ImportRowException, ...]


class DryRunPriceTableImportUseCase:
    """Runs the phase for real against the caller's session, but the caller (the router) must
    never commit that transaction — same rollback-based dry-run as `DryRunImportUseCase`."""

    def __init__(
        self,
        *,
        staging_rows: ImportStagingRowRepository,
        batches: ImportBatchRepository,
        exams: ExamRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._batches = batches
        self._phase = ImportPriceTableUseCase(
            staging_rows=staging_rows, exams=exams, audit=audit, clock=clock
        )

    def execute(self, command: RunPriceTableImportCommand) -> PriceTableImportResult:
        if self._batches.get_by_id(command.batch_id) is None:
            raise NotFoundError("Lote de importação não encontrado.")
        result = self._phase.execute(
            ImportPriceTableCommand(
                actor_id=command.actor_id,
                actor_permissions=command.actor_permissions,
                batch_id=command.batch_id,
            )
        )
        return PriceTableImportResult(
            batch_id=command.batch_id,
            imported_count=result.imported_count,
            skipped_existing_count=result.skipped_existing_count,
            exceptions=result.exceptions,
        )


class CommitPriceTableImportUseCase:
    """Same phase run as `DryRunPriceTableImportUseCase`, plus persisting every collected
    exception (deduplicated against what's already there, same as `CommitImportUseCase`) and
    marking the batch `COMMITTED`. The caller (the router) commits this transaction."""

    def __init__(
        self,
        *,
        staging_rows: ImportStagingRowRepository,
        batches: ImportBatchRepository,
        exceptions: ImportExceptionRepository,
        exams: ExamRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._batches = batches
        self._exceptions = exceptions
        self._clock = clock
        self._phase = ImportPriceTableUseCase(
            staging_rows=staging_rows, exams=exams, audit=audit, clock=clock
        )

    def execute(self, command: RunPriceTableImportCommand) -> PriceTableImportResult:
        batch = self._batches.get_by_id(command.batch_id)
        if batch is None:
            raise NotFoundError("Lote de importação não encontrado.")

        result = self._phase.execute(
            ImportPriceTableCommand(
                actor_id=command.actor_id,
                actor_permissions=command.actor_permissions,
                batch_id=command.batch_id,
            )
        )

        already_persisted = {
            (exc.phase, exc.source_row_number, exc.message)
            for exc in self._exceptions.list_by_batch(command.batch_id)
        }
        now = self._clock.now()
        exception_rows = [
            ImportException(
                id=uuid4(),
                batch_id=command.batch_id,
                phase=_PHASE_PRICE_TABLE,
                source_row_number=exc.source_row_number,
                message=exc.message,
                created_at=now,
            )
            for exc in result.exceptions
            if (_PHASE_PRICE_TABLE, exc.source_row_number, exc.message) not in already_persisted
        ]
        if exception_rows:
            self._exceptions.add_many(exception_rows)

        batch.mark_committed()
        self._batches.save(batch)

        return PriceTableImportResult(
            batch_id=command.batch_id,
            imported_count=result.imported_count,
            skipped_existing_count=result.skipped_existing_count,
            exceptions=result.exceptions,
        )
