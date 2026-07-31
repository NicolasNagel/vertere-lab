"""Stage an uploaded spreadsheet — freeze + checksum + raw load, no
transformation (`.claude/rules/10-data-migration.md`, steps 1-4: "congelar
cópia", "checksum do arquivo congelado", "carregar em staging sem
transformar o conteúdo original", "guardar número da linha e conteúdo
bruto").

Re-staging the same file (same checksum) returns the existing batch instead
of creating a duplicate — this is what keeps the whole pipeline idempotent
at the entry point, per the same rule file ("importação idempotente").
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
from app.modules.imports.infrastructure.xlsx_reader import InvalidXlsxError, read_workbook
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, ValidationError

_REQUIRED_PERMISSION = "imports.execute"


@dataclass(frozen=True, kw_only=True)
class StageSpreadsheetCommand:
    actor_id: UUID | None
    actor_permissions: frozenset[str]
    source_filename: str
    content: bytes


@dataclass(frozen=True, kw_only=True)
class StageSpreadsheetResult:
    batch: ImportBatch
    already_staged: bool
    sheet_row_counts: dict[str, int]


class StageSpreadsheetUseCase:
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

    def execute(self, command: StageSpreadsheetCommand) -> StageSpreadsheetResult:
        if _REQUIRED_PERMISSION not in command.actor_permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        checksum = hashlib.sha256(command.content).hexdigest()

        existing = self._batches.get_by_checksum(checksum)
        if existing is not None:
            rows = self._staging_rows.list_by_batch(existing.id)
            counts: dict[str, int] = {}
            for row in rows:
                counts[row.sheet_name] = counts.get(row.sheet_name, 0) + 1
            return StageSpreadsheetResult(
                batch=existing, already_staged=True, sheet_row_counts=counts
            )

        try:
            sheets = read_workbook(command.content)
        except InvalidXlsxError as exc:
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

        staging_rows: list[ImportStagingRow] = []
        counts = {}
        for sheet in sheets:
            counts[sheet.name] = len(sheet.rows)
            for xlsx_row in sheet.rows:
                staging_rows.append(
                    ImportStagingRow(
                        id=uuid4(),
                        batch_id=batch.id,
                        sheet_name=sheet.name,
                        source_row_number=xlsx_row.row_number,
                        raw_data=dict(xlsx_row.cells),
                    )
                )
        self._staging_rows.add_many(staging_rows)

        return StageSpreadsheetResult(batch=batch, already_staged=False, sheet_row_counts=counts)
