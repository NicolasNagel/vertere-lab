"""create import_exceptions table

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-28

Last piece of the spreadsheet-import pipeline (`.claude/rules/10-data-migration.md` — "gerar
relatório de exceções para todo caso ambíguo"): every phase use case (clinics, veterinarians,
exam catalog, patients) already collects per-row exceptions and returns them in its HTTP
response, but nothing persisted them — an exception that only ever existed in one response body
is, for reconciliation purposes, the same as never having been reported. `POST
/imports/{batch_id}/commit` (the new pipeline-orchestration endpoint) persists every phase's
exceptions here; `GET /imports/{batch_id}/exceptions` lists them for human review.

No `row_status`/foreign key to `import_staging_rows` on purpose: some phases (exam catalog,
patients) group several staging rows into one derived entity, so a single exception doesn't
always map to exactly one staging row — `source_row_number` alone (already how every phase
reports the row to look at) is kept as a plain reference column, not a hard FK.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phase", sa.String(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_import_exceptions"),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["import_batches.id"],
            name="fk_import_exceptions_batch_id_import_batches",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_import_exceptions_batch_id", "import_exceptions", ["batch_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("import_exceptions")
