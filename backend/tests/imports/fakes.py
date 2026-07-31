"""In-memory fakes for the imports module repository protocols — used by
unit tests for use cases (rule: mock only at an external boundary; a fake
repository backing a pure use-case test is not the repository-under-test,
so this is fine per .claude/rules/08-testing.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.modules.imports.domain.entities import ImportBatch, ImportException, ImportStagingRow


def make_staging_row(
    *, batch_id: UUID, sheet_name: str, source_row_number: int, raw_data: dict[str, Any]
) -> ImportStagingRow:
    return ImportStagingRow(
        id=uuid4(),
        batch_id=batch_id,
        sheet_name=sheet_name,
        source_row_number=source_row_number,
        raw_data=raw_data,
    )


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class FakeImportBatchRepository:
    def __init__(self) -> None:
        self._batches: dict[UUID, ImportBatch] = {}

    def get_by_id(self, batch_id: UUID) -> ImportBatch | None:
        return self._batches.get(batch_id)

    def get_by_checksum(self, checksum_sha256: str) -> ImportBatch | None:
        for batch in self._batches.values():
            if batch.checksum_sha256 == checksum_sha256:
                return batch
        return None

    def add(self, batch: ImportBatch) -> None:
        self._batches[batch.id] = batch

    def save(self, batch: ImportBatch) -> None:
        self._batches[batch.id] = batch


class FakeImportStagingRowRepository:
    def __init__(self) -> None:
        self._rows: dict[UUID, ImportStagingRow] = {}

    def add_many(self, rows: list[ImportStagingRow]) -> None:
        for row in rows:
            self._rows[row.id] = row

    def list_by_batch(
        self, batch_id: UUID, *, sheet_name: str | None = None
    ) -> list[ImportStagingRow]:
        rows = [row for row in self._rows.values() if row.batch_id == batch_id]
        if sheet_name is not None:
            rows = [row for row in rows if row.sheet_name == sheet_name]
        return sorted(rows, key=lambda row: row.source_row_number)

    def save(self, row: ImportStagingRow) -> None:
        self._rows[row.id] = row


class FakeImportExceptionRepository:
    def __init__(self) -> None:
        self._exceptions: list[ImportException] = []

    def add_many(self, exceptions: list[ImportException]) -> None:
        self._exceptions.extend(exceptions)

    def list_by_batch(self, batch_id: UUID) -> list[ImportException]:
        return [exc for exc in self._exceptions if exc.batch_id == batch_id]
