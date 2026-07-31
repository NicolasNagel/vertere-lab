"""SQLAlchemy mapping for the imports module — separate from domain
entities (rule: .claude/rules/03-database.md, "não é Active Record")."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.database import Base


class ImportBatchModel(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('STAGED','DRY_RUN_DONE','COMMITTED')", name="ck_import_batches_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_filename: Mapped[str] = mapped_column(nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(nullable=False, default="STAGED")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class ImportStagingRowModel(Base):
    __tablename__ = "import_staging_rows"
    __table_args__ = (
        CheckConstraint(
            "row_status IN ('PENDING','VALID','EXCEPTION','IMPORTED','REJECTED')",
            name="ck_import_staging_rows_status",
        ),
        UniqueConstraint(
            "batch_id",
            "sheet_name",
            "source_row_number",
            name="uq_import_staging_rows_batch_sheet_row",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False
    )
    sheet_name: Mapped[str] = mapped_column(nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    row_status: Mapped[str] = mapped_column(nullable=False, default="PENDING")
    rejection_reason: Mapped[str | None] = mapped_column(nullable=True)


class ImportExceptionModel(Base):
    __tablename__ = "import_exceptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False
    )
    phase: Mapped[str] = mapped_column(nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
