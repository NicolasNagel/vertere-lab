"""create exams and exam_species tables

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-25

`catalog.read`/`catalog.manage` and `pricing.read`/`pricing.manage` were
already in the permission catalog seeded by 0002 and already granted where
relevant — no permission grant migration needed alongside this one.

Price uses `NUMERIC(14,2)` (`.claude/rules/globals.md`, "Dinheiro: Python
Decimal; PostgreSQL NUMERIC(14,2). Nunca float.") — a deliberate divergence
from the "cents" integer naming in the spec's example payload
(`assets/features/screens/spec-pages.md`, "Tela de Cadastro de Exames &
Preços"), documented in ADR-005. `plantao_surcharge_fixed` and
`plantao_surcharge_percent` are mutually exclusive (check constraint),
matching "percentual ou valor fixo" from the spec.

One migration for both tables: `exam_species` only exists to support
`exams`, so together they are a single coherent change (rule:
.claude/rules/database.md, "uma mudança coerente por migration").
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exams",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("price_base", sa.Numeric(14, 2), nullable=False),
        sa.Column("plantao_surcharge_fixed", sa.Numeric(14, 2), nullable=True),
        sa.Column("plantao_surcharge_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_exams"),
        sa.UniqueConstraint("code", name="uq_exams_code"),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_exams_status"),
        sa.CheckConstraint("price_base > 0", name="ck_exams_price_base_positive"),
        sa.CheckConstraint(
            "plantao_surcharge_fixed IS NULL OR plantao_surcharge_percent IS NULL",
            name="ck_exams_plantao_surcharge_exclusive",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["exam_categories.id"],
            name="fk_exams_category_id_exam_categories",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_exams_created_by_users", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name="fk_exams_updated_by_users", ondelete="SET NULL"
        ),
    )
    op.create_index("ix_exams_status", "exams", ["status"], unique=False)
    op.create_index("ix_exams_category_id", "exams", ["category_id"], unique=False)

    op.create_table(
        "exam_species",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exam_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("species_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_exam_species"),
        sa.UniqueConstraint("exam_id", "species_id", name="uq_exam_species_exam_species"),
        sa.ForeignKeyConstraint(
            ["exam_id"], ["exams.id"], name="fk_exam_species_exam_id_exams", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["species_id"],
            ["species.id"],
            name="fk_exam_species_species_id_species",
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    op.drop_table("exam_species")
    op.drop_table("exams")
