"""add on_call_fee_total to monthly_closures

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "monthly_closures",
        sa.Column("on_call_fee_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_monthly_closures_on_call_fee_total_non_negative",
        "monthly_closures",
        "on_call_fee_total >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_monthly_closures_on_call_fee_total_non_negative", "monthly_closures", type_="check"
    )
    op.drop_column("monthly_closures", "on_call_fee_total")
