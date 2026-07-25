"""create species table and seed initial catalog

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-25

`patients.read`/`patients.manage` were already in the permission catalog
seeded by 0002 and already granted to RECEPTION/TECHNICAL/TECHNICAL_MANAGER
there — no permission grant migration needed alongside this one (same
situation as veterinarians in 0005). Species has no dedicated permission:
it is a fixed reference list gated by `patients.read` (see
`app/modules/patients/application/list_species.py`), not an independently
manageable resource in this slice — decided in `/planejar-fatia` instead of
a mockup, since no screen in `assets/features/screens/` covers it.

Seed values are a literal list, not app code (rule:
.claude/rules/database.md — "migration não importa código de aplicação
instável").
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SPECIES_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-0000000000aa")
_INITIAL_SPECIES: tuple[str, ...] = ("Cão", "Gato", "Ave", "Outro")

species_table = sa.table(
    "species",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("name", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    op.create_table(
        "species",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_species"),
        sa.UniqueConstraint("name", name="uq_species_name"),
    )

    now = datetime.now(UTC)
    op.bulk_insert(
        species_table,
        [
            {"id": uuid.uuid5(_SPECIES_NAMESPACE, name), "name": name, "created_at": now}
            for name in _INITIAL_SPECIES
        ],
    )


def downgrade() -> None:
    op.drop_table("species")
