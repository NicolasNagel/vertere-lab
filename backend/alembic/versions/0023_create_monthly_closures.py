"""create monthly_closures and monthly_closure_items

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-31

Incremento 4.2 (fechar de verdade) — `docs/03-modelo-de-dominio.md` §6,
`.claude/rules/13-monthly-closure.md`. `attendances.monthly_closure_id` has
existed since 0018 with no FK because this table didn't exist yet; this
migration finally adds that FK.

`status` only allows `CLOSED`/`REOPENED` here — this slice never persists a
draft-closure row (the prévia in Incremento 4.1 stays in-memory-only), so
`DRAFT`/`CANCELLED` from the abstract state diagram are not reachable and
are deliberately not in the CHECK constraint. `REOPENED` is unused until
Incremento 4.3 but included now, same precedent as 0011 listing
`attendances.status` values before every transition existed.

The partial unique index enforces "unicidade ativa por clínica e
competência" (`.claude/rules/03-database.md`) at the database level, in
addition to (never instead of) the advisory lock the close use case takes —
defense in depth against a code path that forgets to lock.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monthly_closures",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("competence_year", sa.Integer(), nullable=False),
        sa.Column("competence_month", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="CLOSED"),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("surcharge_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("grand_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("generated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("closed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("integrity_hash", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_monthly_closures"),
        sa.CheckConstraint("status IN ('CLOSED','REOPENED')", name="ck_monthly_closures_status"),
        sa.CheckConstraint("subtotal >= 0", name="ck_monthly_closures_subtotal_non_negative"),
        sa.CheckConstraint(
            "discount_total >= 0", name="ck_monthly_closures_discount_total_non_negative"
        ),
        sa.CheckConstraint(
            "surcharge_total >= 0", name="ck_monthly_closures_surcharge_total_non_negative"
        ),
        sa.CheckConstraint("grand_total >= 0", name="ck_monthly_closures_grand_total_non_negative"),
        sa.CheckConstraint("item_count >= 0", name="ck_monthly_closures_item_count_non_negative"),
        sa.ForeignKeyConstraint(
            ["clinic_id"],
            ["clinics.id"],
            name="fk_monthly_closures_clinic_id_clinics",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["generated_by"],
            ["users.id"],
            name="fk_monthly_closures_generated_by_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["closed_by"],
            ["users.id"],
            name="fk_monthly_closures_closed_by_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "uq_monthly_closures_active_clinic_competence",
        "monthly_closures",
        ["clinic_id", "competence_year", "competence_month"],
        unique=True,
        postgresql_where=sa.text("status = 'CLOSED'"),
    )

    op.create_table(
        "monthly_closure_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("monthly_closure_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attendance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attendance_exam_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("protocol_number", sa.String(), nullable=True),
        sa.Column("patient_name", sa.String(), nullable=False),
        sa.Column("exam_name", sa.String(), nullable=False),
        sa.Column("price_base", sa.Numeric(14, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("surcharge_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_monthly_closure_items"),
        sa.CheckConstraint("quantity > 0", name="ck_monthly_closure_items_quantity_positive"),
        sa.CheckConstraint(
            "discount_amount >= 0", name="ck_monthly_closure_items_discount_non_negative"
        ),
        sa.CheckConstraint(
            "surcharge_amount >= 0", name="ck_monthly_closure_items_surcharge_non_negative"
        ),
        sa.CheckConstraint("total_amount >= 0", name="ck_monthly_closure_items_total_non_negative"),
        sa.ForeignKeyConstraint(
            ["monthly_closure_id"],
            ["monthly_closures.id"],
            name="fk_monthly_closure_items_monthly_closure_id_monthly_closures",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["attendance_id"],
            ["attendances.id"],
            name="fk_monthly_closure_items_attendance_id_attendances",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["attendance_exam_id"],
            ["attendance_exams.id"],
            name="fk_monthly_closure_items_attendance_exam_id_attendance_exams",
            ondelete="RESTRICT",
        ),
    )

    # RESTRICT, not SET NULL: a closure row is meant to be immutable and
    # never deleted, but if it ever were, silently nulling
    # `monthly_closure_id` back out would look like the attendance got
    # un-closed — the delete must fail loudly instead
    # (`.claude/rules/13-monthly-closure.md`: "fechamento fechado é
    # imutável").
    op.create_foreign_key(
        "fk_attendances_monthly_closure_id_monthly_closures",
        "attendances",
        "monthly_closures",
        ["monthly_closure_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_attendances_monthly_closure_id_monthly_closures", "attendances", type_="foreignkey"
    )
    op.drop_table("monthly_closure_items")
    op.drop_index("uq_monthly_closures_active_clinic_competence", table_name="monthly_closures")
    op.drop_table("monthly_closures")
