"""drop orphaned exam plantao surcharge fields

Revision ID: 0030
Revises: 0029
Create Date: 2026-08-02

The per-exam-item plantão surcharge was replaced by a flat per-attendance
fee (`AttendanceRecord.on_call_fee`, migration 0028) — `attendance_items.py`
has hardcoded `surcharge_amount=Decimal("0")` on every item since then, so
these columns have been dead weight, never read for anything financial.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_exams_plantao_surcharge_exclusive", "exams", type_="check")
    op.drop_column("exams", "plantao_surcharge_fixed")
    op.drop_column("exams", "plantao_surcharge_percent")


def downgrade() -> None:
    op.add_column("exams", sa.Column("plantao_surcharge_fixed", sa.Numeric(14, 2), nullable=True))
    op.add_column("exams", sa.Column("plantao_surcharge_percent", sa.Numeric(5, 2), nullable=True))
    op.create_check_constraint(
        "ck_exams_plantao_surcharge_exclusive",
        "exams",
        "plantao_surcharge_fixed IS NULL OR plantao_surcharge_percent IS NULL",
    )
