"""create veterinarian_clinics table

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-25

Pure join table between `veterinarians` and `clinics` (docs/05-roadmap-backlog.md
§4 item 3, "vínculo veterinário-clínica"). `ON DELETE CASCADE` on both FKs is
safe here even though the product rule is "inativar em vez de apagar"
(docs/.claude/rules/01-product-domain.md): `veterinarians`/`clinics` rows are
never hard-deleted in this system, only soft-inactivated, so the cascade
never actually fires against real history — it only guards against orphaned
link rows if a hard delete is ever done on a draft record.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "veterinarian_clinics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("veterinarian_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("primary_clinic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_veterinarian_clinics"),
        sa.UniqueConstraint(
            "veterinarian_id",
            "clinic_id",
            name="uq_veterinarian_clinics_veterinarian_clinic",
        ),
        sa.ForeignKeyConstraint(
            ["veterinarian_id"],
            ["veterinarians.id"],
            name="fk_veterinarian_clinics_veterinarian_id_veterinarians",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id"],
            ["clinics.id"],
            name="fk_veterinarian_clinics_clinic_id_clinics",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_veterinarian_clinics_created_by_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_veterinarian_clinics_veterinarian_id",
        "veterinarian_clinics",
        ["veterinarian_id"],
        unique=False,
    )
    op.create_index(
        "ix_veterinarian_clinics_clinic_id", "veterinarian_clinics", ["clinic_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("veterinarian_clinics")
