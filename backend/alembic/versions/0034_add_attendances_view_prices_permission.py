"""add attendances.view_prices permission (Master-only)

Revision ID: 0034
Revises: 0033
Create Date: 2026-08-04

New permission code, following the same pattern as `0012_add_users_activate_
permission.py`: not part of `0002_seed_identity_catalog.py` (frozen), so a
new row + grant is inserted here. `attendances.view_prices` controls whether
a profile can see prices while building an attendance — narrower than
`pricing.read` (the pricing catalog admin screen), which `FINANCE` genuinely
needs and keeps unrestricted. This one is Master-only
(`app.modules.identity.domain.constants.MASTER_ONLY_PERMISSIONS`), so only
`ROLE_SUPER_ADMIN` — the sole GLOBAL-scope role — is granted it here.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.modules.identity.infrastructure.seed import PERMISSION_DESCRIPTIONS, ROLE_SUPER_ADMIN

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSION_CODE = "attendances.view_prices"
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
            [
                {
                    "id": _PERMISSION_ID,
                    "code": _PERMISSION_CODE,
                    "description": PERMISSION_DESCRIPTIONS[_PERMISSION_CODE],
                }
            ],
        )

    already_granted = conn.execute(
        sa.select(role_permissions_table.c.role_id).where(
            sa.and_(
                role_permissions_table.c.role_id == ROLE_SUPER_ADMIN,
                role_permissions_table.c.permission_id == _PERMISSION_ID,
            )
        )
    ).scalar_one_or_none()
    if already_granted is None:
        op.bulk_insert(
            role_permissions_table,
            [
                {
                    "role_id": ROLE_SUPER_ADMIN,
                    "permission_id": _PERMISSION_ID,
                    "granted_at": datetime.now(UTC),
                }
            ],
        )


def downgrade() -> None:
    op.execute(
        role_permissions_table.delete().where(
            role_permissions_table.c.permission_id == _PERMISSION_ID
        )
    )
    op.execute(permissions_table.delete().where(permissions_table.c.id == _PERMISSION_ID))
