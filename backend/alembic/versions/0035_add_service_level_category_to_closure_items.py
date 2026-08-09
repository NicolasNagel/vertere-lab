"""add service_level and exam_category to monthly_closure_items

Revision ID: 0035
Revises: 0034
Create Date: 2026-08-05

Tela 15 (fechamento consolidado) precisa exibir o badge NORMAL/PLANTÃO e o
breakdown por categoria de exame sem nunca reconsultar o atendimento vivo
(`.claude/rules/03-database.md`: "snapshot contém valor suficiente para
reprodução total sem consultar o atendimento original"). Ambos os campos já
existem em `attendances.service_level`/`exam_categories.name` — este
snapshot só os captura no momento do fechamento.

Nullable porque fechamentos já existentes não têm como ser retroativamente
preenchidos sem reconsultar o atendimento (o que violaria a própria regra
de snapshot) — linhas antigas ficam `NULL` e a UI trata isso como "sem
informação", nunca como "NORMAL" por padrão.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SERVICE_LEVELS = ("NORMAL", "PLANTAO_NORMAL", "PLANTAO_ESPECIAL")


def upgrade() -> None:
    op.add_column("monthly_closure_items", sa.Column("service_level", sa.String(), nullable=True))
    op.add_column("monthly_closure_items", sa.Column("exam_category", sa.String(), nullable=True))
    op.create_check_constraint(
        "ck_monthly_closure_items_service_level",
        "monthly_closure_items",
        f"service_level IS NULL OR service_level IN {_SERVICE_LEVELS}",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_monthly_closure_items_service_level", "monthly_closure_items", type_="check"
    )
    op.drop_column("monthly_closure_items", "exam_category")
    op.drop_column("monthly_closure_items", "service_level")
