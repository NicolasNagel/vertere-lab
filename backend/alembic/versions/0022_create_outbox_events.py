"""create outbox_events

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-31

Generic table backing `app/shared/outbox` — first writer is the monthly
closure flow (`.claude/rules/13-monthly-closure.md`: "grava auditoria e
outbox → commit"), reusable by any future use case that needs an effect
after its own commit (`.claude/rules/02-backend.md` pattern table, "Domain
Event"). New table, no backfill needed (`.claude/rules/03-database.md`:
"expand → backfill → contract").
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_events"),
        sa.CheckConstraint(
            "status IN ('PENDING','PROCESSED','FAILED')", name="ck_outbox_events_status"
        ),
    )


def downgrade() -> None:
    op.drop_table("outbox_events")
