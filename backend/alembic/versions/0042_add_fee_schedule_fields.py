"""add structured schedule (weekdays, start/end time) to on-call and urgency fees

Revision ID: 0042
Revises: 0041
Create Date: 2026-11-15

Dias da semana e horário são só informativos (o tipo do atendimento é escolhido no registro) e
nunca entram no cálculo. `schedule_label` continua gravado: é gerado a partir dos campos novos
e mantém o texto livre antigo enquanto ninguém editar a taxa.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("on_call_fee_settings", "urgency_fee_settings")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "weekdays",
                postgresql.ARRAY(sa.SmallInteger()),
                nullable=False,
                server_default="{}",
            ),
        )
        op.add_column(table, sa.Column("start_time", sa.Time(), nullable=True))
        op.add_column(table, sa.Column("end_time", sa.Time(), nullable=True))
        op.create_check_constraint(
            f"ck_{table}_schedule_times_together",
            table,
            "(start_time IS NULL) = (end_time IS NULL)",
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_constraint(f"ck_{table}_schedule_times_together", table, type_="check")
        op.drop_column(table, "end_time")
        op.drop_column(table, "start_time")
        op.drop_column(table, "weekdays")
