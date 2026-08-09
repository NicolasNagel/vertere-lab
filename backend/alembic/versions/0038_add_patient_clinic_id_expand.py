"""add nullable clinic ownership to patients (expand phase)

Revision ID: 0038
Revises: 0037
Create Date: 2026-08-09

Legacy rows deliberately remain NULL. Only LAB/GLOBAL actors may see them
until an audited reconciliation assigns a clinic.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("clinic_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_patients_clinic_id_clinics",
        "patients",
        "clinics",
        ["clinic_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_patients_clinic_id", "patients", ["clinic_id"])


def downgrade() -> None:
    op.drop_index("ix_patients_clinic_id", table_name="patients")
    op.drop_constraint("fk_patients_clinic_id_clinics", "patients", type_="foreignkey")
    op.drop_column("patients", "clinic_id")
