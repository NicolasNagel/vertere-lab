"""Imports API schemas — separate create/read models (rule:
.claude/rules/02-backend.md, never reuse the ORM model as response)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ImportBatchStatusLiteral = Literal["STAGED", "DRY_RUN_DONE", "COMMITTED"]


class ImportBatchRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    source_filename: str
    checksum_sha256: str
    status: ImportBatchStatusLiteral
    created_at: datetime


class SpreadsheetStageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch: ImportBatchRead
    already_staged: bool
    sheet_row_counts: dict[str, int]


class ImportRowExceptionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_row_number: int
    message: str


class ImportClinicsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    imported_count: int
    skipped_existing_count: int
    exceptions: list[ImportRowExceptionRead]


class ImportVeterinariansResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    imported_count: int
    skipped_existing_count: int
    exceptions: list[ImportRowExceptionRead]


class LinkVeterinarianClinicsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    links_created_count: int
    exceptions: list[ImportRowExceptionRead]


class ImportExamCategoriesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    imported_count: int
    skipped_existing_count: int


class ImportExamsFromHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    imported_count: int
    skipped_existing_count: int
    exceptions: list[ImportRowExceptionRead]


class ImportPatientsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    imported_count: int
    skipped_existing_count: int
    exceptions: list[ImportRowExceptionRead]


class PipelinePhaseRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: str
    imported_count: int
    skipped_existing_count: int
    exceptions: list[ImportRowExceptionRead]


class ImportPipelineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: UUID
    status: ImportBatchStatusLiteral
    phases: list[PipelinePhaseRead]
    total_imported_count: int
    total_exceptions_count: int


class PriceTablePdfStageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch: ImportBatchRead
    already_staged: bool
    item_count: int
    ignored_surcharge_line_count: int
    unpaired_line_count: int


class PriceTableImportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: UUID
    status: ImportBatchStatusLiteral
    imported_count: int
    skipped_existing_count: int
    exceptions: list[ImportRowExceptionRead]


class AttendanceHistoryImportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: UUID
    status: ImportBatchStatusLiteral
    imported_count: int
    skipped_existing_count: int
    rejected_count: int
    imported_grand_total: Decimal
    exceptions: list[ImportRowExceptionRead]


class ImportExceptionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: str
    source_row_number: int
    message: str
    created_at: datetime


class ImportExceptionsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: UUID
    exceptions: list[ImportExceptionRead]
