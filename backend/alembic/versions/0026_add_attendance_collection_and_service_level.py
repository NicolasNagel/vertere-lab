"""add controlled collection method and service level to attendances

Revision ID: 0026
Revises: 0025
Create Date: 2026-07-31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("attendances", sa.Column("collection_method", sa.String(), nullable=True))
    op.add_column("attendances", sa.Column("service_level", sa.String(), nullable=True))
    op.execute(
        "UPDATE attendances SET collection_method = 'INTERNAL' WHERE collection_method IS NULL"
    )
    op.execute("UPDATE attendances SET service_level = 'NORMAL' WHERE service_level IS NULL")
    op.alter_column("attendances", "collection_method", nullable=False, server_default="INTERNAL")
    op.alter_column("attendances", "service_level", nullable=False, server_default="NORMAL")
    op.create_check_constraint(
        "ck_attendances_collection_method",
        "attendances",
        "collection_method IN ('HELITO_NICOLAS','INTERNAL','MARLI','COURIER','UBER')",
    )
    op.create_check_constraint(
        "ck_attendances_service_level",
        "attendances",
        "service_level IN ('NORMAL','ON_CALL')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_attendances_service_level", "attendances", type_="check")
    op.drop_constraint("ck_attendances_collection_method", "attendances", type_="check")
    op.drop_column("attendances", "service_level")
    op.drop_column("attendances", "collection_method")
