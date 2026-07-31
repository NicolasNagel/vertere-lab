"""create idempotency_keys

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-28

Generic table backing `app/shared/idempotency` — used first by
`POST /attendances/{id}/confirm` (`.claude/rules/12-attendance.md`:
"Idempotency-Key obrigatória"), reusable later by monthly closure
(`.claude/rules/02-backend.md`: "POST de criação/confirmação/fechamento aceita
Idempotency-Key"). New table, no backfill needed
(`.claude/rules/03-database.md`: "expand → backfill → contract").
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("payload_hash", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="IN_PROGRESS"),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_keys"),
        sa.CheckConstraint(
            "status IN ('IN_PROGRESS','COMPLETED')", name="ck_idempotency_keys_status"
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name="fk_idempotency_keys_actor_id_users",
            ondelete="CASCADE",
        ),
    )
    op.create_unique_constraint(
        "uq_idempotency_keys_actor_operation_key",
        "idempotency_keys",
        ["actor_id", "operation", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_idempotency_keys_actor_operation_key", "idempotency_keys", type_="unique"
    )
    op.drop_table("idempotency_keys")
