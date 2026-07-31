"""create login_failures table (login rate limiting)

Revision ID: 0015
Revises: 0012
Create Date: 2026-07-27

Achado em teste manual adversarial (ADR-007): o endpoint de login não tinha
nenhuma proteção contra força bruta — 15 tentativas de senha errada em
paralelo, todas 401, sem throttling. `.claude/rules/06-auth-security-lgpd.md`
já exigia "rate limit em login" explicitamente.

Persistido no PostgreSQL, não em memória de processo nem Redis: a app roda
como Function stateless (`AGENTS.md` — "Vercel é stateless"), e Redis só
entra com justificativa medida — uma tabela simples com um índice já resolve
sem introduzir peça de infra nova.

`down_revision = "0012"`, não o topo real do diretório local: há migrações
0013/0014 de outra fatia (importação de dados) ainda não commitadas no
momento em que esta foi escrita. Encadear nelas quebraria o histórico de
quem só tiver este commit. Quando aquele trabalho for commitado, a cadeia
correta é resolvida normalmente (rebase do `down_revision` de um dos lados,
como qualquer migration concorrente).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0015"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_failures",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("login", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_login_failures"),
    )
    op.create_index(
        "ix_login_failures_login_occurred_at",
        "login_failures",
        ["login", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_login_failures_login_occurred_at", table_name="login_failures")
    op.drop_table("login_failures")
