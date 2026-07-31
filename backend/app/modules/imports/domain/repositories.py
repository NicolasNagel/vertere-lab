"""Repository protocols for the imports module.

Interface lives in `domain` (rule: .claude/rules/02-backend.md); implementation
lives in `infrastructure`. Repository never commits — the unit of work does.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.imports.domain.entities import ImportBatch, ImportException, ImportStagingRow


class ImportBatchRepository(Protocol):
    def get_by_id(self, batch_id: UUID) -> ImportBatch | None: ...

    def get_by_checksum(self, checksum_sha256: str) -> ImportBatch | None: ...

    def add(self, batch: ImportBatch) -> None: ...

    def save(self, batch: ImportBatch) -> None: ...


class ImportStagingRowRepository(Protocol):
    def add_many(self, rows: list[ImportStagingRow]) -> None: ...

    def list_by_batch(
        self, batch_id: UUID, *, sheet_name: str | None = None
    ) -> list[ImportStagingRow]: ...

    def save(self, row: ImportStagingRow) -> None: ...


class ImportExceptionRepository(Protocol):
    def add_many(self, exceptions: list[ImportException]) -> None: ...

    def list_by_batch(self, batch_id: UUID) -> list[ImportException]: ...
