"""add legacy import traceability fields to attendances

Revision ID: 0036
Revises: 0035
Create Date: 2026-08-05

Fase 4 (migração do histórico da planilha, `docs/01-analise-planilha.md`
§6) precisa que cada `AttendanceRecord` migrado seja rastreável até a
linha de origem e preserve o protocolo antigo como referência — nunca
reutilizado como protocolo real (`.claude/rules/10-data-migration.md`).

`import_batch_id` + `legacy_source_row_number` juntos também são a chave
de idempotência: reprocessar o mesmo lote não deve duplicar o mesmo
atendimento (mesma regra de "reprocessar não duplica" das demais fases de
importação) — por isso o índice único parcial abaixo, defesa em
profundidade além da checagem que o caso de uso já faz antes de inserir.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("attendances", sa.Column("legacy_source_row_number", sa.Integer(), nullable=True))
    op.add_column("attendances", sa.Column("legacy_protocol_reference", sa.String(), nullable=True))
    op.add_column(
        "attendances",
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_attendances_import_batch_id_import_batches",
        "attendances",
        "import_batches",
        ["import_batch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_attendances_import_batch_source_row",
        "attendances",
        ["import_batch_id", "legacy_source_row_number"],
        unique=True,
        postgresql_where=sa.text("import_batch_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_attendances_import_batch_source_row", table_name="attendances")
    op.drop_constraint(
        "fk_attendances_import_batch_id_import_batches", "attendances", type_="foreignkey"
    )
    op.drop_column("attendances", "import_batch_id")
    op.drop_column("attendances", "legacy_protocol_reference")
    op.drop_column("attendances", "legacy_source_row_number")
