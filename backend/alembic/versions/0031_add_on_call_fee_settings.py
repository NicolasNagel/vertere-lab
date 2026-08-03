"""add configurable on-call fee settings

Revision ID: 0031
Revises: 0030
Create Date: 2026-08-03

The flat plantão fee (`ON_CALL_FEES` in
`app/modules/attendances/domain/entities.py`, introduced by migration 0028
as "definido pelo negócio, não configurável") is now editable via
`PATCH /api/v1/on-call-fee-settings/{service_level}` — reverses that
decision per explicit product call (see plan
`dentro-da-pasta-assets-enchanted-narwhal.md`). `NORMAL` gets no row: its
fee stays permanently zero. Seed values below are the amounts already in
effect (from 0028), not the placeholder figures shown in the mockup used as
visual reference — the mockup's numbers are prototype demo data.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ON_CALL_FEE_SETTINGS_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-0000000000bb")

on_call_fee_settings_table = sa.table(
    "on_call_fee_settings",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("service_level", sa.String()),
    sa.column("fee_amount", sa.Numeric(14, 2)),
    sa.column("schedule_label", sa.String()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
    sa.column("row_version", sa.Integer()),
)

_SEED_FEES: tuple[tuple[str, str], ...] = (
    ("PLANTAO_NORMAL", "100.00"),
    ("PLANTAO_ESPECIAL", "150.00"),
)


def upgrade() -> None:
    op.create_table(
        "on_call_fee_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_level", sa.String(), nullable=False),
        sa.Column("fee_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("schedule_label", sa.String(), nullable=False, server_default=""),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id", name="pk_on_call_fee_settings"),
        sa.UniqueConstraint("service_level", name="uq_on_call_fee_settings_service_level"),
        sa.CheckConstraint(
            "service_level IN ('PLANTAO_NORMAL','PLANTAO_ESPECIAL')",
            name="ck_on_call_fee_settings_service_level",
        ),
        sa.CheckConstraint(
            "fee_amount >= 0", name="ck_on_call_fee_settings_fee_amount_non_negative"
        ),
    )

    now = datetime.now(UTC)
    op.bulk_insert(
        on_call_fee_settings_table,
        [
            {
                "id": uuid.uuid5(_ON_CALL_FEE_SETTINGS_NAMESPACE, service_level),
                "service_level": service_level,
                "fee_amount": fee_amount,
                "schedule_label": "",
                "updated_at": now,
                "row_version": 1,
            }
            for service_level, fee_amount in _SEED_FEES
        ],
    )


def downgrade() -> None:
    op.drop_table("on_call_fee_settings")
