"""Imports domain entities — spreadsheet staging.

No FastAPI/SQLAlchemy import here (rule: .claude/rules/00-global.md — domain
layer). Follows the staging-first flow required by
`.claude/rules/10-data-migration.md`: freeze the source file, load its raw
content into staging without transforming it, only normalize afterwards in
a later step. `ImportBatch`/`ImportStagingRow` are the staging primitives;
normalization (clinic/veterinarian/exam/patient) lives in dedicated use
cases that read from staging, never from the uploaded file directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class ImportBatchStatus(StrEnum):
    STAGED = "STAGED"
    DRY_RUN_DONE = "DRY_RUN_DONE"
    COMMITTED = "COMMITTED"


class ImportRowStatus(StrEnum):
    PENDING = "PENDING"
    VALID = "VALID"
    EXCEPTION = "EXCEPTION"
    IMPORTED = "IMPORTED"
    REJECTED = "REJECTED"


@dataclass(kw_only=True)
class ImportBatch:
    id: UUID
    source_filename: str
    checksum_sha256: str
    status: ImportBatchStatus = ImportBatchStatus.STAGED
    created_by: UUID | None = None
    created_at: datetime

    def mark_dry_run_done(self) -> None:
        self.status = ImportBatchStatus.DRY_RUN_DONE

    def mark_committed(self) -> None:
        self.status = ImportBatchStatus.COMMITTED


@dataclass(kw_only=True)
class ImportStagingRow:
    id: UUID
    batch_id: UUID
    sheet_name: str
    source_row_number: int
    raw_data: dict[str, Any] = field(default_factory=dict)
    row_status: ImportRowStatus = ImportRowStatus.PENDING
    rejection_reason: str | None = None

    def mark_valid(self) -> None:
        self.row_status = ImportRowStatus.VALID
        self.rejection_reason = None

    def mark_exception(self, reason: str) -> None:
        self.row_status = ImportRowStatus.EXCEPTION
        self.rejection_reason = reason

    def mark_imported(self) -> None:
        self.row_status = ImportRowStatus.IMPORTED

    def mark_rejected(self, reason: str) -> None:
        self.row_status = ImportRowStatus.REJECTED
        self.rejection_reason = reason


@dataclass(kw_only=True)
class ImportException:
    """A single ambiguous/unresolved case surfaced by any pipeline phase
    (clinics, veterinarians, exam catalog, patients, ...), persisted so a
    human can review and resolve it after the fact — the alternative is an
    exception that only ever existed in one HTTP response, which
    `.claude/rules/10-data-migration.md` ("gerar relatório de exceções para
    todo caso ambíguo") treats as not having been reported at all."""

    id: UUID
    batch_id: UUID
    phase: str
    source_row_number: int
    message: str
    created_at: datetime
