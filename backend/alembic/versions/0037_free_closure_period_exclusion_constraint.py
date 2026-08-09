"""replace clinic+competence unique index with a period-overlap exclusion constraint

Revision ID: 0037
Revises: 0036
Create Date: 2026-08-08

Some clinics close quinzenalmente instead of by full calendar month — a
closure's period is now any free `[period_start, period_end]` range chosen
at close time, so `(clinic_id, competence_year, competence_month)` equality
can no longer be the uniqueness key (two half-month closures share the same
year+month but must never collide with each other, while two closures with
literally overlapping date ranges for the same clinic must).

Real invariant becomes a PostgreSQL EXCLUDE constraint on
`(clinic_id, daterange(period_start, period_end, '[]'))`, restricted to
`status = 'CLOSED'` — exactly mirrors what the old partial unique index did
for the calendar-month case, generalized to any range
(`.claude/rules/03-database.md`: "Unique ativo por clínica+competência").
Requires the `btree_gist` extension for a GiST index over a scalar column
(`clinic_id`) combined with a range operator (`&&`).

`competence_year`/`competence_month` columns are untouched — they remain as
display/grouping metadata only, never again part of any uniqueness key.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.drop_index("uq_monthly_closures_active_clinic_competence", table_name="monthly_closures")
    op.execute(
        """
        ALTER TABLE monthly_closures
        ADD CONSTRAINT excl_monthly_closures_active_clinic_period
        EXCLUDE USING gist (
            clinic_id WITH =,
            daterange(period_start, period_end, '[]') WITH &&
        )
        WHERE (status = 'CLOSED')
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE monthly_closures DROP CONSTRAINT excl_monthly_closures_active_clinic_period"
    )
    op.create_index(
        "uq_monthly_closures_active_clinic_competence",
        "monthly_closures",
        ["clinic_id", "competence_year", "competence_month"],
        unique=True,
        postgresql_where=sa.text("status = 'CLOSED'"),
    )
    # btree_gist left installed — dropping a shared extension on downgrade
    # risks breaking other objects that may have started depending on it;
    # harmless to leave enabled (`.claude/rules/03-database.md`: "downgrade
    # quando seguro; quando não for, documente o procedimento").
