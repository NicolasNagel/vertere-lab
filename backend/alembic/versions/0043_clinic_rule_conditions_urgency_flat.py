"""clinic fee rule conditions; urgency fee loses its schedule

Revision ID: 0043
Revises: 0042
Create Date: 2026-11-15

docs/plano-exames-precos.md, seção H:
- `clinic_fee_rules.exam_ids` / `attendance_types`: condições opcionais da regra (vazio = qualquer).
- `urgency_fee_settings`: volta a ser só um valor fixo; dias, horário e texto de agenda saem
  (só o plantão tem agenda).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "clinic_fee_rules",
        sa.Column(
            "exam_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "clinic_fee_rules",
        sa.Column(
            "attendance_types",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.drop_constraint(
        "ck_urgency_fee_settings_schedule_times_together", "urgency_fee_settings", type_="check"
    )
    op.drop_column("urgency_fee_settings", "end_time")
    op.drop_column("urgency_fee_settings", "start_time")
    op.drop_column("urgency_fee_settings", "weekdays")
    op.drop_column("urgency_fee_settings", "schedule_label")


def downgrade() -> None:
    op.add_column(
        "urgency_fee_settings",
        sa.Column("schedule_label", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "urgency_fee_settings",
        sa.Column(
            "weekdays",
            postgresql.ARRAY(sa.SmallInteger()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column("urgency_fee_settings", sa.Column("start_time", sa.Time(), nullable=True))
    op.add_column("urgency_fee_settings", sa.Column("end_time", sa.Time(), nullable=True))
    op.create_check_constraint(
        "ck_urgency_fee_settings_schedule_times_together",
        "urgency_fee_settings",
        "(start_time IS NULL) = (end_time IS NULL)",
    )
    op.drop_column("clinic_fee_rules", "attendance_types")
    op.drop_column("clinic_fee_rules", "exam_ids")
