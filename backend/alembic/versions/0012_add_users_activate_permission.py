"""add users.activate permission

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-26

`PATCH /users/{id}/deactivate` had no symmetric reactivation endpoint. Adding
`users.activate` as a new permission code (rather than reusing
`users.deactivate` for both directions) keeps the audit trail and the
authorization check honest about which action was actually taken. 0002
already ran, so this is a new migration rather than an edit to it (rule:
.claude/rules/03-database.md — "nunca edite migration já aplicada"). Granted to
SUPER_ADMIN and LAB_ADMIN, the only roles that hold `users.deactivate` today.

`PERMISSION_CODES` in `infrastructure/seed.py` now also lists
`users.activate`, since it is the live source `0002_seed_identity_catalog.py`
reads from. That means a *fresh* database (0001..head run back-to-back, as in
tests or a new environment) already gets this permission inserted by 0002 —
only a database where 0002 ran *before* this migration existed is actually
missing it. This migration checks for that instead of assuming either case.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.modules.identity.infrastructure.seed import ROLE_LAB_ADMIN, ROLE_SUPER_ADMIN

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSION_CODE = "users.activate"
# Same fixed namespace as 0002_seed_identity_catalog.py, so the id stays
# deterministic and consistent with how every other seeded permission id was
# derived.
_PERMISSION_UUID_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-0000000000ff")
_PERMISSION_ID = uuid.uuid5(_PERMISSION_UUID_NAMESPACE, _PERMISSION_CODE)

permissions_table = sa.table(
    "permissions",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("code", sa.String()),
    sa.column("description", sa.String()),
)

role_permissions_table = sa.table(
    "role_permissions",
    sa.column("role_id", postgresql.UUID(as_uuid=True)),
    sa.column("permission_id", postgresql.UUID(as_uuid=True)),
    sa.column("granted_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    conn = op.get_bind()

    permission_exists = conn.execute(
        sa.select(permissions_table.c.id).where(permissions_table.c.id == _PERMISSION_ID)
    ).scalar_one_or_none()
    if permission_exists is None:
        op.bulk_insert(
            permissions_table,
            [{"id": _PERMISSION_ID, "code": _PERMISSION_CODE, "description": ""}],
        )

    now = datetime.now(UTC)
    already_granted = set(
        conn.execute(
            sa.select(role_permissions_table.c.role_id).where(
                role_permissions_table.c.permission_id == _PERMISSION_ID
            )
        )
        .scalars()
        .all()
    )
    missing_grants = [
        {"role_id": role_id, "permission_id": _PERMISSION_ID, "granted_at": now}
        for role_id in (ROLE_SUPER_ADMIN, ROLE_LAB_ADMIN)
        if role_id not in already_granted
    ]
    if missing_grants:
        op.bulk_insert(role_permissions_table, missing_grants)


def downgrade() -> None:
    op.execute(
        role_permissions_table.delete().where(
            role_permissions_table.c.permission_id == _PERMISSION_ID
        )
    )
    op.execute(permissions_table.delete().where(permissions_table.c.id == _PERMISSION_ID))
