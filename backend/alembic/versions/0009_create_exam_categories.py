"""create exam_categories table

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-25

`catalog.read`/`catalog.manage` were already in the permission catalog
seeded by 0002 and already granted where relevant (RECEPTION/TECHNICAL/
TECHNICAL_MANAGER have catalog.read; FINANCE and TECHNICAL_MANAGER also
have catalog.manage) — no permission grant migration needed alongside this
one (same situation as veterinarians in 0005).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exam_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id", name="pk_exam_categories"),
        sa.UniqueConstraint("name", name="uq_exam_categories_name"),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_exam_categories_status"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_exam_categories_created_by_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name="fk_exam_categories_updated_by_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_exam_categories_status", "exam_categories", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("exam_categories")
