"""add urgency fee, clinic fee rules and per-attendance fee composition

Revision ID: 0041
Revises: 0040
Create Date: 2026-11-15

Módulo de Taxas (docs/plano-exames-precos.md, seção G):
- `urgency_fee_settings`: uma linha, valor fixo da taxa de urgência (semeada com 0,00).
- `clinic_fee_rules`: taxa fixa personalizada por clínica, com vigência; soma ao total.
- `attendances`: `is_urgent`, `urgency_fee`, `clinic_fee` e `fee_lines` (composição das taxas
  aplicadas, snapshot). Atendimentos existentes ficam com 0 / false / [] e o total não muda.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_URGENCY_ID = uuid.UUID("00000000-0000-0000-0000-0000000000cc")

urgency_table = sa.table(
    "urgency_fee_settings",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("fee_amount", sa.Numeric(14, 2)),
    sa.column("schedule_label", sa.String()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
    sa.column("row_version", sa.Integer()),
)


def upgrade() -> None:
    op.create_table(
        "urgency_fee_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_urgency_fee_settings"),
        sa.CheckConstraint(
            "fee_amount >= 0", name="ck_urgency_fee_settings_fee_amount_non_negative"
        ),
    )
    op.bulk_insert(
        urgency_table,
        [
            {
                "id": _URGENCY_ID,
                "fee_amount": "0.00",
                "schedule_label": "",
                "updated_at": datetime.now(UTC),
                "row_version": 1,
            }
        ],
    )

    op.create_table(
        "clinic_fee_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "clinic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clinics.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("fee_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id", name="pk_clinic_fee_rules"),
        sa.CheckConstraint("fee_amount >= 0", name="ck_clinic_fee_rules_fee_amount_non_negative"),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from", name="ck_clinic_fee_rules_valid_range"
        ),
    )
    op.create_index("ix_clinic_fee_rules_clinic_id", "clinic_fee_rules", ["clinic_id"])

    op.add_column(
        "attendances",
        sa.Column("is_urgent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "attendances",
        sa.Column("urgency_fee", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "attendances",
        sa.Column("clinic_fee", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "attendances",
        sa.Column(
            "fee_lines",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_check_constraint(
        "ck_attendances_urgency_fee_non_negative", "attendances", "urgency_fee >= 0"
    )
    op.create_check_constraint(
        "ck_attendances_clinic_fee_non_negative", "attendances", "clinic_fee >= 0"
    )


def downgrade() -> None:
    op.drop_constraint("ck_attendances_clinic_fee_non_negative", "attendances", type_="check")
    op.drop_constraint("ck_attendances_urgency_fee_non_negative", "attendances", type_="check")
    op.drop_column("attendances", "fee_lines")
    op.drop_column("attendances", "clinic_fee")
    op.drop_column("attendances", "urgency_fee")
    op.drop_column("attendances", "is_urgent")
    op.drop_index("ix_clinic_fee_rules_clinic_id", table_name="clinic_fee_rules")
    op.drop_table("clinic_fee_rules")
    op.drop_table("urgency_fee_settings")
