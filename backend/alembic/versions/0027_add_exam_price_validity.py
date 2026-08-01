"""add explicit validity window to exam prices

Revision ID: 0027
Revises: 0026
Create Date: 2026-07-31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("exams", sa.Column("price_valid_from", sa.Date(), nullable=True))
    op.add_column("exams", sa.Column("price_valid_to", sa.Date(), nullable=True))
    op.execute("UPDATE exams SET price_valid_from = DATE '1900-01-01'")
    op.alter_column(
        "exams", "price_valid_from", nullable=False, server_default=sa.text("DATE '1900-01-01'")
    )
    op.create_check_constraint(
        "ck_exams_price_validity",
        "exams",
        "price_valid_to IS NULL OR price_valid_to >= price_valid_from",
    )


def downgrade() -> None:
    op.drop_constraint("ck_exams_price_validity", "exams", type_="check")
    op.drop_column("exams", "price_valid_to")
    op.drop_column("exams", "price_valid_from")
