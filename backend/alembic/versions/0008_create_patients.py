"""create patients table

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-25

`patients.read`/`patients.manage` were already in the permission catalog
seeded by 0002 and already granted to RECEPTION/TECHNICAL/TECHNICAL_MANAGER
there — no permission grant migration needed alongside this one (same
situation as veterinarians in 0005).

Owner is not a separate table/FK here: per explicit product decision
(`/planejar-fatia` for this slice), owner data is plain columns on
`patients` (`owner_name`/`owner_phone`/`owner_document`), not a referenced
`owners` table — see `app/modules/patients/domain/entities.py` docstring.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("species_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sex", sa.String(), nullable=False),
        sa.Column("breed", sa.String(), nullable=True),
        sa.Column("age_description", sa.String(), nullable=True),
        sa.Column("owner_name", sa.String(), nullable=False),
        sa.Column("owner_phone", sa.String(), nullable=True),
        sa.Column("owner_document", sa.String(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_patients"),
        sa.CheckConstraint("sex IN ('MALE','FEMALE')", name="ck_patients_sex"),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_patients_status"),
        sa.ForeignKeyConstraint(
            ["species_id"],
            ["species.id"],
            name="fk_patients_species_id_species",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_patients_created_by_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name="fk_patients_updated_by_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_patients_name", "patients", ["name"], unique=False)
    op.create_index("ix_patients_owner_name", "patients", ["owner_name"], unique=False)
    op.create_index("ix_patients_status", "patients", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("patients")
