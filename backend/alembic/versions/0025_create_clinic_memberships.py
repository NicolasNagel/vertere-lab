"""create clinic_memberships table

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-31

Scopes a user to a specific clinic — the CLINIC-scope counterpart to
`lab_memberships` (all-clinic scope). A user can hold several rows here (one
per clinic), unlike `lab_memberships`, which is unique per user. This is the
foundation for the `require_permission(clinic_scoped=True)` branch, currently
a `NotImplementedError` stub (`app/modules/identity/api/dependencies.py`) —
CLINIC-scope roles (`CLINIC_ADMIN`/`VETERINARIAN`/`CLINIC_STAFF`) cannot even
log in today (`LoginUseCase`/`ResolveSessionUseCase` reject `RoleScope.CLINIC`
unconditionally) until that branch and this table exist.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clinic_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_clinic_memberships"),
        sa.UniqueConstraint("user_id", "clinic_id", name="uq_clinic_memberships_user_id_clinic_id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_clinic_memberships_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id"],
            ["clinics.id"],
            name="fk_clinic_memberships_clinic_id_clinics",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
            name="fk_clinic_memberships_granted_by_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_clinic_memberships_user_id", "clinic_memberships", ["user_id"], unique=False
    )
    op.create_index(
        "ix_clinic_memberships_clinic_id", "clinic_memberships", ["clinic_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("clinic_memberships")
