"""enable the unaccent extension for accent-insensitive search

Revision ID: 0044
Revises: 0043
Create Date: 2026-11-19

The lists searched with `lower(column) LIKE %term%`, so "joao" never found "João". Search now compares
`lower(unaccent(column))` with the accent-folded term. `unaccent` is a *trusted* extension (PostgreSQL
13+): the database owner can create it, no superuser is needed. The downgrade keeps the extension: it may
predate this migration (created by a DBA) and leaving an unused one is harmless, while dropping it
could break other objects that depend on it.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0044"
down_revision: str | None = "0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")


def downgrade() -> None:
    # Intentionally a no-op: see the module docstring.
    pass
