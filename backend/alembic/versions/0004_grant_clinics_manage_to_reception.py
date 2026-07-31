"""grant clinics.manage to RECEPTION

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-23

`clinics.read`/`clinics.manage` were already in the permission catalog
seeded by 0002 (docs/07-nucleo-v1.md §2.2 anticipated Fase 2), but RECEPTION
only got `clinics.read` there — a gap now that Clinic actually exists:
docs/07-nucleo-v1.md §2.1 describes RECEPTION's purpose as "cadastros e
atendimentos", which includes registering clinics, not just reading them.
0002 already ran, so this is a new migration rather than an edit to it (rule:
.claude/rules/03-database.md — "nunca edite migration já aplicada").
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.modules.identity.infrastructure.seed import ROLE_RECEPTION

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

role_permissions_table = sa.table(
    "role_permissions",
    sa.column("role_id", postgresql.UUID(as_uuid=True)),
    sa.column("permission_id", postgresql.UUID(as_uuid=True)),
    sa.column("granted_at", sa.DateTime(timezone=True)),
)

permissions_table = sa.table(
    "permissions",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("code", sa.String()),
)


def upgrade() -> None:
    conn = op.get_bind()
    permission_id = conn.execute(
        sa.select(permissions_table.c.id).where(permissions_table.c.code == "clinics.manage")
    ).scalar_one()
    op.bulk_insert(
        role_permissions_table,
        [
            {
                "role_id": ROLE_RECEPTION,
                "permission_id": permission_id,
                "granted_at": datetime.now(UTC),
            }
        ],
    )


def downgrade() -> None:
    conn = op.get_bind()
    permission_id = conn.execute(
        sa.select(permissions_table.c.id).where(permissions_table.c.code == "clinics.manage")
    ).scalar_one()
    op.execute(
        role_permissions_table.delete().where(
            role_permissions_table.c.role_id == ROLE_RECEPTION,
            role_permissions_table.c.permission_id == permission_id,
        )
    )
