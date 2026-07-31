"""add attendance confirmation fields, items and protocol sequence

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-27

Expand-only migration for the confirmation slice announced in
`app/modules/attendances/domain/entities.py` (0011's docstring) and
`.claude/rules/12-attendance.md`. All new columns on `attendances` are
nullable or carry a default — no backfill needed, no existing row breaks
(`.claude/rules/03-database.md`: "expand → backfill → contract").

`monthly_closure_id` has no FK yet — `monthly_closures` only appears in
Incremento 4.2. The column exists now because "item já em fechamento é
imutável" is a structural invariant the confirmation slice must already
respect (`docs/03-modelo-de-dominio.md` §6).

`attendance_sequences` backs the transactional protocol counter — the
repository uses `SELECT ... FOR UPDATE`, never `MAX + 1`
(`.claude/rules/03-database.md`).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("attendances", sa.Column("billing_competence", sa.Date(), nullable=True))
    op.add_column(
        "attendances",
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "attendances",
        sa.Column("discount_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "attendances",
        sa.Column("surcharge_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "attendances",
        sa.Column("grand_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column("attendances", sa.Column("protocol_year", sa.Integer(), nullable=True))
    op.add_column("attendances", sa.Column("protocol_sequence", sa.Integer(), nullable=True))
    op.add_column("attendances", sa.Column("protocol_number", sa.String(), nullable=True))
    op.add_column(
        "attendances", sa.Column("monthly_closure_id", postgresql.UUID(as_uuid=True), nullable=True)
    )

    op.create_check_constraint(
        "ck_attendances_subtotal_non_negative", "attendances", "subtotal >= 0"
    )
    op.create_check_constraint(
        "ck_attendances_discount_total_non_negative", "attendances", "discount_total >= 0"
    )
    op.create_check_constraint(
        "ck_attendances_surcharge_total_non_negative", "attendances", "surcharge_total >= 0"
    )
    op.create_check_constraint(
        "ck_attendances_grand_total_non_negative", "attendances", "grand_total >= 0"
    )
    op.create_unique_constraint(
        "uq_attendances_protocol_year_sequence",
        "attendances",
        ["protocol_year", "protocol_sequence"],
    )
    op.create_index(
        "ix_attendances_clinic_billing_competence",
        "attendances",
        ["clinic_id", "billing_competence"],
        unique=False,
    )

    op.create_table(
        "attendance_exams",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attendance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exam_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exam_code", sa.String(), nullable=False),
        sa.Column("exam_name", sa.String(), nullable=False),
        sa.Column("price_base", sa.Numeric(14, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("surcharge_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("override_reason", sa.String(), nullable=True),
        sa.Column("override_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
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
        sa.PrimaryKeyConstraint("id", name="pk_attendance_exams"),
        sa.CheckConstraint("quantity > 0", name="ck_attendance_exams_quantity_positive"),
        sa.CheckConstraint(
            "discount_amount >= 0", name="ck_attendance_exams_discount_non_negative"
        ),
        sa.CheckConstraint(
            "surcharge_amount >= 0", name="ck_attendance_exams_surcharge_non_negative"
        ),
        sa.CheckConstraint("total_amount >= 0", name="ck_attendance_exams_total_non_negative"),
        sa.CheckConstraint("status IN ('ACTIVE','CANCELLED')", name="ck_attendance_exams_status"),
        sa.ForeignKeyConstraint(
            ["attendance_id"],
            ["attendances.id"],
            name="fk_attendance_exams_attendance_id_attendances",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["exam_id"],
            ["exams.id"],
            name="fk_attendance_exams_exam_id_exams",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["override_by"],
            ["users.id"],
            name="fk_attendance_exams_override_by_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_attendance_exams_attendance_id", "attendance_exams", ["attendance_id"], unique=False
    )
    op.create_index("ix_attendance_exams_exam_id", "attendance_exams", ["exam_id"], unique=False)

    op.create_table(
        "attendance_sequences",
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("year", name="pk_attendance_sequences"),
    )


def downgrade() -> None:
    op.drop_table("attendance_sequences")

    op.drop_index("ix_attendance_exams_exam_id", table_name="attendance_exams")
    op.drop_index("ix_attendance_exams_attendance_id", table_name="attendance_exams")
    op.drop_table("attendance_exams")

    op.drop_index("ix_attendances_clinic_billing_competence", table_name="attendances")
    op.drop_constraint("uq_attendances_protocol_year_sequence", "attendances", type_="unique")
    op.drop_constraint("ck_attendances_grand_total_non_negative", "attendances", type_="check")
    op.drop_constraint("ck_attendances_surcharge_total_non_negative", "attendances", type_="check")
    op.drop_constraint("ck_attendances_discount_total_non_negative", "attendances", type_="check")
    op.drop_constraint("ck_attendances_subtotal_non_negative", "attendances", type_="check")

    op.drop_column("attendances", "monthly_closure_id")
    op.drop_column("attendances", "protocol_number")
    op.drop_column("attendances", "protocol_sequence")
    op.drop_column("attendances", "protocol_year")
    op.drop_column("attendances", "grand_total")
    op.drop_column("attendances", "surcharge_total")
    op.drop_column("attendances", "discount_total")
    op.drop_column("attendances", "subtotal")
    op.drop_column("attendances", "billing_competence")
