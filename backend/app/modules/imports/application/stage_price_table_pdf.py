"""Stage an uploaded price-table PDF — same staging-first discipline as
`stage_spreadsheet.py` (freeze + checksum + raw load, no transformation yet),
reusing the exact same `ImportBatch`/`ImportStagingRow` tables so the rest of
the pipeline (exceptions, dry-run/commit) doesn't need a parallel set of
concepts for a second source file type. `sheet_name` is fixed to
`SHEET_NAME` since a PDF has no sheets — it's just the discriminator that
lets `ImportStagingRowRepository.list_by_batch(..., sheet_name=...)` find
these rows the same way it finds `"Cadastro Clínicas"` rows for the xlsx
flow.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.modules.imports.domain.entities import ImportBatch, ImportStagingRow
from app.modules.imports.domain.repositories import (
    ImportBatchRepository,
    ImportStagingRowRepository,
)
from app.modules.imports.infrastructure.pdf_price_table_reader import (
    InvalidPriceTablePdfError,
    read_price_table,
)
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, ValidationError

_REQUIRED_PERMISSION = "imports.execute"

SHEET_NAME = "Tabela de Preços (PDF)"


@dataclass(frozen=True, kw_only=True)
class StagePriceTablePdfCommand:
    actor_id: UUID | None
    actor_permissions: frozenset[str]
    source_filename: str
    content: bytes


@dataclass(frozen=True, kw_only=True)
class StagePriceTablePdfResult:
    batch: ImportBatch
    already_staged: bool
    item_count: int
    ignored_surcharge_line_count: int
    unpaired_line_count: int


class StagePriceTablePdfUseCase:
    def __init__(
        self,
        *,
        batches: ImportBatchRepository,
        staging_rows: ImportStagingRowRepository,
        clock: Clock,
    ) -> None:
        self._batches = batches
        self._staging_rows = staging_rows
        self._clock = clock

    def execute(self, command: StagePriceTablePdfCommand) -> StagePriceTablePdfResult:
        if _REQUIRED_PERMISSION not in command.actor_permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        checksum = hashlib.sha256(command.content).hexdigest()

        existing = self._batches.get_by_checksum(checksum)
        if existing is not None:
            rows = self._staging_rows.list_by_batch(existing.id, sheet_name=SHEET_NAME)
            return StagePriceTablePdfResult(
                batch=existing,
                already_staged=True,
                item_count=len(rows),
                ignored_surcharge_line_count=0,
                unpaired_line_count=0,
            )

        try:
            parsed = read_price_table(command.content)
        except InvalidPriceTablePdfError as exc:
            raise ValidationError(str(exc)) from exc

        now = self._clock.now()
        batch = ImportBatch(
            id=uuid4(),
            source_filename=command.source_filename,
            checksum_sha256=checksum,
            created_by=command.actor_id,
            created_at=now,
        )
        self._batches.add(batch)

        staging_rows = [
            ImportStagingRow(
                id=uuid4(),
                batch_id=batch.id,
                sheet_name=SHEET_NAME,
                source_row_number=index,
                raw_data={
                    "category": item.category,
                    "name": item.name,
                    "price": str(item.price),
                    "page": item.page,
                },
            )
            for index, item in enumerate(parsed.items, start=1)
        ]
        self._staging_rows.add_many(staging_rows)

        return StagePriceTablePdfResult(
            batch=batch,
            already_staged=False,
            item_count=len(staging_rows),
            ignored_surcharge_line_count=len(parsed.ignored_surcharge_lines),
            unpaired_line_count=len(parsed.unpaired_lines),
        )
