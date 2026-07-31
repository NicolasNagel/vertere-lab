"""SQLAlchemy repositories for the imports module. No commit here — the
unit of work owns the transaction (rule: .claude/rules/02-backend.md)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.imports.domain.entities import (
    ImportBatch,
    ImportBatchStatus,
    ImportException,
    ImportRowStatus,
    ImportStagingRow,
)
from app.modules.imports.infrastructure.models import (
    ImportBatchModel,
    ImportExceptionModel,
    ImportStagingRowModel,
)


def _batch_to_entity(model: ImportBatchModel) -> ImportBatch:
    return ImportBatch(
        id=model.id,
        source_filename=model.source_filename,
        checksum_sha256=model.checksum_sha256,
        status=ImportBatchStatus(model.status),
        created_by=model.created_by,
        created_at=model.created_at,
    )


def _row_to_entity(model: ImportStagingRowModel) -> ImportStagingRow:
    return ImportStagingRow(
        id=model.id,
        batch_id=model.batch_id,
        sheet_name=model.sheet_name,
        source_row_number=model.source_row_number,
        raw_data=model.raw_data,
        row_status=ImportRowStatus(model.row_status),
        rejection_reason=model.rejection_reason,
    )


class SqlAlchemyImportBatchRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, batch_id: UUID) -> ImportBatch | None:
        model = self._session.get(ImportBatchModel, batch_id)
        return _batch_to_entity(model) if model is not None else None

    def get_by_checksum(self, checksum_sha256: str) -> ImportBatch | None:
        stmt = select(ImportBatchModel).where(ImportBatchModel.checksum_sha256 == checksum_sha256)
        model = self._session.execute(stmt).scalar_one_or_none()
        return _batch_to_entity(model) if model is not None else None

    def add(self, batch: ImportBatch) -> None:
        self._session.add(
            ImportBatchModel(
                id=batch.id,
                source_filename=batch.source_filename,
                checksum_sha256=batch.checksum_sha256,
                status=batch.status.value,
                created_by=batch.created_by,
                created_at=batch.created_at,
            )
        )

    def save(self, batch: ImportBatch) -> None:
        model = self._session.get(ImportBatchModel, batch.id)
        if model is None:
            raise ValueError(f"ImportBatch {batch.id} não encontrado.")
        model.status = batch.status.value


class SqlAlchemyImportStagingRowRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_many(self, rows: list[ImportStagingRow]) -> None:
        self._session.add_all(
            [
                ImportStagingRowModel(
                    id=row.id,
                    batch_id=row.batch_id,
                    sheet_name=row.sheet_name,
                    source_row_number=row.source_row_number,
                    raw_data=row.raw_data,
                    row_status=row.row_status.value,
                    rejection_reason=row.rejection_reason,
                )
                for row in rows
            ]
        )

    def list_by_batch(
        self, batch_id: UUID, *, sheet_name: str | None = None
    ) -> list[ImportStagingRow]:
        stmt = select(ImportStagingRowModel).where(ImportStagingRowModel.batch_id == batch_id)
        if sheet_name is not None:
            stmt = stmt.where(ImportStagingRowModel.sheet_name == sheet_name)
        stmt = stmt.order_by(ImportStagingRowModel.source_row_number)
        models = self._session.execute(stmt).scalars().all()
        return [_row_to_entity(model) for model in models]

    def save(self, row: ImportStagingRow) -> None:
        model = self._session.get(ImportStagingRowModel, row.id)
        if model is None:
            raise ValueError(f"ImportStagingRow {row.id} não encontrado.")
        model.row_status = row.row_status.value
        model.rejection_reason = row.rejection_reason


def _exception_to_entity(model: ImportExceptionModel) -> ImportException:
    return ImportException(
        id=model.id,
        batch_id=model.batch_id,
        phase=model.phase,
        source_row_number=model.source_row_number,
        message=model.message,
        created_at=model.created_at,
    )


class SqlAlchemyImportExceptionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_many(self, exceptions: list[ImportException]) -> None:
        self._session.add_all(
            [
                ImportExceptionModel(
                    id=exc.id,
                    batch_id=exc.batch_id,
                    phase=exc.phase,
                    source_row_number=exc.source_row_number,
                    message=exc.message,
                    created_at=exc.created_at,
                )
                for exc in exceptions
            ]
        )

    def list_by_batch(self, batch_id: UUID) -> list[ImportException]:
        stmt = (
            select(ImportExceptionModel)
            .where(ImportExceptionModel.batch_id == batch_id)
            .order_by(ImportExceptionModel.phase, ImportExceptionModel.source_row_number)
        )
        models = self._session.execute(stmt).scalars().all()
        return [_exception_to_entity(model) for model in models]
