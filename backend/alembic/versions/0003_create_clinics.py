"""create clinics table

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-23

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clinics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("tax_id", sa.String(length=14), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
        sa.Column("address_zip_code", sa.String(length=8), nullable=True),
        sa.Column("address_street", sa.String(), nullable=True),
        sa.Column("address_number", sa.String(), nullable=True),
        sa.Column("address_neighborhood", sa.String(), nullable=True),
        sa.Column("address_city", sa.String(), nullable=True),
        sa.Column("address_state", sa.String(length=2), nullable=True),
        sa.Column("address_complement", sa.String(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_clinics"),
        sa.UniqueConstraint("tax_id", name="uq_clinics_tax_id"),
        sa.CheckConstraint(
            "status IN ('ACTIVE','INACTIVE','DELINQUENT','SPECIAL')", name="ck_clinics_status"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_clinics_created_by_users", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name="fk_clinics_updated_by_users", ondelete="SET NULL"
        ),
    )
    op.create_index("ix_clinics_name", "clinics", ["name"], unique=False)
    op.create_index("ix_clinics_status", "clinics", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("clinics")
