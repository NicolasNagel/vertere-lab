"""add friendly pt-BR descriptions to permissions

Revision ID: 0033
Revises: 0032
Create Date: 2026-08-04

`0002_seed_identity_catalog.py` inserted every permission with
`description=""` (frozen migration, never edited). The permission code alone
(`attendances.override_price`) is not something a lab administrator should
have to decode in the Usuários & Permissões screen — this migration backfills
`permissions.description` with the friendly text from
`app.modules.identity.infrastructure.seed.PERMISSION_DESCRIPTIONS`, keyed by
`code` so it fixes both a fresh database (0002 runs, then this one) and one
that already had 0002 applied with the empty description.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.modules.identity.infrastructure.seed import PERMISSION_CODES, PERMISSION_DESCRIPTIONS

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

permissions_table = sa.table(
    "permissions",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("code", sa.String()),
    sa.column("description", sa.String()),
)

_OLD_DESCRIPTION = ""


def upgrade() -> None:
    missing = [code for code in PERMISSION_CODES if code not in PERMISSION_DESCRIPTIONS]
    if missing:
        raise RuntimeError(f"PERMISSION_DESCRIPTIONS está sem entrada para: {missing}")

    for code, description in PERMISSION_DESCRIPTIONS.items():
        op.execute(
            permissions_table.update()
            .where(permissions_table.c.code == code)
            .values(description=description)
        )


def downgrade() -> None:
    for code in PERMISSION_DESCRIPTIONS:
        op.execute(
            permissions_table.update()
            .where(permissions_table.c.code == code)
            .values(description=_OLD_DESCRIPTION)
        )
