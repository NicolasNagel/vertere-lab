"""create veterinarians table

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-25

`veterinarians.read`/`veterinarians.manage` were already in the permission
catalog seeded by 0002 and already granted to RECEPTION there (unlike
clinics.manage, which needed the follow-up 0004 migration) — so no
permission grant migration is needed alongside this one.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "veterinarians",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("crmv", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("is_autonomous", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
        sa.Column("notes", sa.String(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_veterinarians"),
        sa.UniqueConstraint("crmv", name="uq_veterinarians_crmv"),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_veterinarians_status"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_veterinarians_created_by_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name="fk_veterinarians_updated_by_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_veterinarians_name", "veterinarians", ["name"], unique=False)
    op.create_index("ix_veterinarians_status", "veterinarians", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("veterinarians")
