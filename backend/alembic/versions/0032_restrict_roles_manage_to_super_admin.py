"""restrict roles.manage to SUPER_ADMIN

Revision ID: 0032
Revises: 0031
Create Date: 2026-08-04

`roles.manage` (edit a permission profile's own permission set / create a new
profile) was granted to both SUPER_ADMIN and LAB_ADMIN since 0002. Product
decision: editing the *rules* of a permission profile is exclusive to
SUPER_ADMIN — LAB_ADMIN keeps `roles.read`/`roles.assign` (see a role's
permissions, assign a role to a user) but loses the ability to redefine what a
role grants. This is a data-only change (role_permissions grant), not a
role-name check in code (rule: .claude/rules/01-product-domain.md — "código
nunca decide por nome de papel, só por resource.action"); authorization still
checks `roles.manage` everywhere, only SUPER_ADMIN's role now carries it.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.modules.identity.infrastructure.seed import ROLE_LAB_ADMIN

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSION_CODE = "roles.manage"
# Same fixed namespace as 0002_seed_identity_catalog.py, so the id stays
# deterministic and consistent with how every other seeded permission id was
# derived.
_PERMISSION_UUID_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-0000000000ff")
_PERMISSION_ID = uuid.uuid5(_PERMISSION_UUID_NAMESPACE, _PERMISSION_CODE)

role_permissions_table = sa.table(
    "role_permissions",
    sa.column("role_id", postgresql.UUID(as_uuid=True)),
    sa.column("permission_id", postgresql.UUID(as_uuid=True)),
    sa.column("granted_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    op.execute(
        role_permissions_table.delete().where(
            sa.and_(
                role_permissions_table.c.role_id == ROLE_LAB_ADMIN,
                role_permissions_table.c.permission_id == _PERMISSION_ID,
            )
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    already_granted = conn.execute(
        sa.select(role_permissions_table.c.role_id).where(
            sa.and_(
                role_permissions_table.c.role_id == ROLE_LAB_ADMIN,
                role_permissions_table.c.permission_id == _PERMISSION_ID,
            )
        )
    ).scalar_one_or_none()
    if already_granted is None:
        op.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id, granted_at) "
                "VALUES (:role_id, :permission_id, now())"
            ).bindparams(role_id=ROLE_LAB_ADMIN, permission_id=_PERMISSION_ID)
        )
