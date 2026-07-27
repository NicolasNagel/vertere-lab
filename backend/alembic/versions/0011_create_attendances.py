"""create attendances table (draft-only slice)

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-26

`attendances.create`/`attendances.read` were already in the permission
catalog seeded by 0002 and already granted to RECEPTION there — no
permission grant migration needed alongside this one (same situation as
veterinarians in 0005 and exams in 0009/0010).

This is the smallest possible slice of `AttendanceRecord`
(`docs/03-modelo-de-dominio.md` §3): an empty `DRAFT`, referencing only
`clinic_id`/`veterinarian_id`/`patient_id`. No `owner_id` column — ADR-004
already eliminated the `Owner` aggregate, so there is nothing to reference;
the tutor is read from `patients` at snapshot time in a later slice. No
protocol columns, no money columns, no `service_type_id`/
`collection_method_id` — `.claude/rules/attendence.md` is explicit that
"confirmação gera protocolo" and "nenhum atendimento confirmado existe sem
item", so a draft-only slice has none of that yet. These arrive via an
additive (expand) migration when the confirmation slice needs them —
see `app/modules/attendances/domain/entities.py` docstring.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attendances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("veterinarian_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="DRAFT"),
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
        sa.PrimaryKeyConstraint("id", name="pk_attendances"),
        sa.CheckConstraint(
            "status IN ('DRAFT','CONFIRMED','IN_PROGRESS','COMPLETED','CANCELLED','ON_HOLD')",
            name="ck_attendances_status",
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id"],
            ["clinics.id"],
            name="fk_attendances_clinic_id_clinics",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["veterinarian_id"],
            ["veterinarians.id"],
            name="fk_attendances_veterinarian_id_veterinarians",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
            name="fk_attendances_patient_id_patients",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_attendances_created_by_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name="fk_attendances_updated_by_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_attendances_clinic_id", "attendances", ["clinic_id"], unique=False)
    op.create_index(
        "ix_attendances_veterinarian_id", "attendances", ["veterinarian_id"], unique=False
    )
    op.create_index("ix_attendances_patient_id", "attendances", ["patient_id"], unique=False)
    op.create_index("ix_attendances_status", "attendances", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("attendances")
