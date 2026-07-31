"""create imports staging tables

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-26

First slice of the spreadsheet-import pipeline
(`.claude/rules/10-data-migration.md`): staging only, no normalization tables
yet. `import_batches` freezes one upload by checksum (re-staging the same
file returns the existing batch instead of duplicating rows — the
idempotency guarantee lives here). `import_staging_rows` holds the raw,
untransformed cell content per sheet/row (`raw_data` as JSONB — deliberate
variable-shape snapshot of the source file, not a modeled relation, so
`.claude/rules/03-database.md`'s "JSONB só para metadado variável ou snapshot
deliberado" applies here).

Originally written as `0013` (down_revision `0012`), rebased to follow
`0015` (login rate limiting) after that migration landed on the same base
with an explicit note asking this side to rebase once committed — see
`0015_create_login_failures.py`'s docstring. `imports.execute` was already
in the permission catalog seeded by 0002 and already granted to
SUPER_ADMIN/LAB_ADMIN there (same situation as `attendances.create`/
`attendances.read` in 0011) — no permission grant migration needed
alongside this one.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_filename", sa.String(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="STAGED"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_import_batches"),
        sa.CheckConstraint(
            "status IN ('STAGED','DRY_RUN_DONE','COMMITTED')",
            name="ck_import_batches_status",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_import_batches_created_by_users",
            ondelete="SET NULL",
        ),
    )
    op.create_unique_constraint(
        "uq_import_batches_checksum_sha256", "import_batches", ["checksum_sha256"]
    )

    op.create_table(
        "import_staging_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sheet_name", sa.String(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("row_status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("rejection_reason", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_import_staging_rows"),
        sa.CheckConstraint(
            "row_status IN ('PENDING','VALID','EXCEPTION','IMPORTED','REJECTED')",
            name="ck_import_staging_rows_status",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["import_batches.id"],
            name="fk_import_staging_rows_batch_id_import_batches",
            ondelete="CASCADE",
        ),
    )
    op.create_unique_constraint(
        "uq_import_staging_rows_batch_sheet_row",
        "import_staging_rows",
        ["batch_id", "sheet_name", "source_row_number"],
    )
    op.create_index(
        "ix_import_staging_rows_batch_id", "import_staging_rows", ["batch_id"], unique=False
    )
    op.create_index(
        "ix_import_staging_rows_row_status", "import_staging_rows", ["row_status"], unique=False
    )


def downgrade() -> None:
    op.drop_table("import_staging_rows")
    op.drop_table("import_batches")
