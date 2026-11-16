"""exam panels (pacotes/perfis) and component snapshot on attendance items

Revision ID: 0039
Revises: 0038
Create Date: 2026-11-14

A panel is an ordinary `exams` row whose composition lives in `exam_panel_items`; it is sold at
its own price. Attendance items snapshot the composition (code + name) when the panel is added,
so later edits to a panel never rewrite what an old attendance contained. Additive only:
existing rows get an empty composition, so this is safe to roll back.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exam_panel_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("panel_id", sa.Uuid(), nullable=False),
        sa.Column("component_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["panel_id"], ["exams.id"], name="fk_exam_panel_items_panel", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["component_id"], ["exams.id"], name="fk_exam_panel_items_component"
        ),
        sa.UniqueConstraint("panel_id", "component_id", name="uq_exam_panel_items_panel_component"),
        sa.CheckConstraint("panel_id <> component_id", name="ck_exam_panel_items_not_self"),
    )
    op.create_index("ix_exam_panel_items_component_id", "exam_panel_items", ["component_id"])
    op.add_column(
        "attendance_exams",
        sa.Column(
            "components_snapshot",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("attendance_exams", "components_snapshot")
    op.drop_index("ix_exam_panel_items_component_id", table_name="exam_panel_items")
    op.drop_table("exam_panel_items")
