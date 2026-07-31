"""add attendances.cancel_reason

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-29

Expand-only: nullable column, no backfill needed
(`.claude/rules/03-database.md`: "expand → backfill → contract"). Backs
Fatia 3 of the attendance plan checkpoint — `POST /attendances/{id}/cancel`
(`.claude/rules/12-attendance.md`: "cancelamento exige motivo").
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("attendances", sa.Column("cancel_reason", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("attendances", "cancel_reason")
