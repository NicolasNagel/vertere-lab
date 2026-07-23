"""seed identity catalog (roles, permissions, role_permissions)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-22

No SUPER_ADMIN user is created here — a password baked into a migration is a
secret in code, which is forbidden. Use `app.scripts.bootstrap_admin` once
per environment instead.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.modules.identity.infrastructure.seed import PERMISSION_CODES, ROLE_DEFINITIONS

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Namespace fixo só para gerar UUIDs determinísticos de permissão a partir do
# código — não é usado para nada criptográfico.
_PERMISSION_UUID_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-0000000000ff")


def _permission_id(code: str) -> uuid.UUID:
    return uuid.uuid5(_PERMISSION_UUID_NAMESPACE, code)


roles_table = sa.table(
    "roles",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("name", sa.String()),
    sa.column("scope", sa.String()),
    sa.column("description", sa.String()),
    sa.column("is_system", sa.Boolean()),
)

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
    op.bulk_insert(
        permissions_table,
        [
            {"id": _permission_id(code), "code": code, "description": ""}
            for code in PERMISSION_CODES
        ],
    )

    op.bulk_insert(
        roles_table,
        [
            {
                "id": role_id,
                "name": name,
                "scope": scope,
                "description": description,
                "is_system": True,
            }
            for role_id, name, scope, description, _permission_codes in ROLE_DEFINITIONS
        ],
    )

    now = datetime.now(UTC)
    role_permission_rows = [
        {"role_id": role_id, "permission_id": _permission_id(code), "granted_at": now}
        for role_id, _name, _scope, _description, permission_codes in ROLE_DEFINITIONS
        for code in permission_codes
    ]
    if role_permission_rows:
        op.bulk_insert(role_permissions_table, role_permission_rows)


def downgrade() -> None:
    # Seguro apenas em ambiente sem usuários/perfis criados a partir deste
    # catálogo — se algum `users.role_id` já referenciar um destes papéis, o
    # downgrade falha por FK, o que é o comportamento correto (não apagar
    # dado referenciado silenciosamente).
    op.execute(sa.text("DELETE FROM role_permissions"))
    role_ids = [role_id for role_id, *_ in ROLE_DEFINITIONS]
    op.execute(roles_table.delete().where(roles_table.c.id.in_(role_ids)))
    op.execute(sa.text("DELETE FROM permissions"))
