"""replace ON_CALL service level with PLANTAO_NORMAL/PLANTAO_ESPECIAL flat fee

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "attendances",
        sa.Column("on_call_fee", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_attendances_on_call_fee_non_negative", "attendances", "on_call_fee >= 0"
    )

    # A constraint antiga só permite 'NORMAL'/'ON_CALL' e a nova só permite
    # 'NORMAL'/'PLANTAO_NORMAL'/'PLANTAO_ESPECIAL' — nenhuma das duas convive
    # com uma linha 'ON_CALL' pendente de migrar, então o UPDATE precisa
    # rodar com NENHUMA das duas ativa (visto na prática ao rodar esta
    # migration contra um banco de dev com atendimento 'ON_CALL' já
    # existente — Testcontainers não pegou isso por rodar sempre em schema
    # vazio, sem dado representativo).
    op.drop_constraint("ck_attendances_service_level", "attendances", type_="check")

    # Dados já existentes marcados como o antigo "ON_CALL" migram para o
    # tier mais barato (conservador — não retroage cobrança maior sem
    # revisão manual). `on_call_fee` fica 0 para essas linhas: o adicional
    # que elas já tiveram (se houve) está preservado no snapshot antigo de
    # `surcharge_amount`/`surcharge_total` por item, que esta migration não
    # toca (`.claude/rules/12-attendance.md`: snapshot é imutável).
    op.execute(
        "UPDATE attendances SET service_level = 'PLANTAO_NORMAL' WHERE service_level = 'ON_CALL'"
    )

    op.create_check_constraint(
        "ck_attendances_service_level",
        "attendances",
        "service_level IN ('NORMAL','PLANTAO_NORMAL','PLANTAO_ESPECIAL')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_attendances_service_level", "attendances", type_="check")
    op.execute(
        "UPDATE attendances SET service_level = 'ON_CALL' "
        "WHERE service_level IN ('PLANTAO_NORMAL','PLANTAO_ESPECIAL')"
    )
    op.create_check_constraint(
        "ck_attendances_service_level", "attendances", "service_level IN ('NORMAL','ON_CALL')"
    )
    op.drop_constraint("ck_attendances_on_call_fee_non_negative", "attendances", type_="check")
    op.drop_column("attendances", "on_call_fee")
