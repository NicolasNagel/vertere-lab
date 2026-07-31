"""create append-only financial adjustments

Revision ID: 0024
Revises: 0023
Create Date: 2026-07-31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "financial_adjustments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("monthly_closure_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("monthly_closure_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_financial_adjustments"),
        sa.CheckConstraint(
            "kind IN ('CREDIT','DEBIT')",
            name="ck_financial_adjustments_kind",
        ),
        sa.CheckConstraint("amount > 0", name="ck_financial_adjustments_amount_positive"),
        sa.ForeignKeyConstraint(
            ["monthly_closure_id"],
            ["monthly_closures.id"],
            name="fk_financial_adjustments_closure",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["monthly_closure_item_id"],
            ["monthly_closure_items.id"],
            name="fk_financial_adjustments_item",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_financial_adjustments_created_by",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_financial_adjustments_closure_created_at",
        "financial_adjustments",
        ["monthly_closure_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_financial_adjustments_closure_created_at",
        table_name="financial_adjustments",
    )
    op.drop_table("financial_adjustments")
