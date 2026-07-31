"""replace species seed with the lab's real vocabulary

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-27

0007's seed (`Cão, Gato, Ave, Outro`) was a placeholder guess made before any
real operational data existed. The spreadsheet import (Fase 2/3,
`.claude/rules/10-data-migration.md`) surfaced the lab's actual species
vocabulary — `Canino, Felino, Bovino, Equino, Coelho, Caprino` — which is
both more specific (splits "Cão"/"Gato" into the same names, just spelled
the way the lab already uses them) and broader (adds farm/exotic species the
placeholder never covered). Keeping both sets side by side would mean
`Canino` and `Cão` coexisting as two rows for the same species — exactly the
"cadastro sem identificador estável" duplication this system exists to
avoid (`docs/01-analise-planilha.md` §2.1). Replacing is safe here because
no `Patient`/`Exam` has been created against the placeholder seed yet — this
module is pre-launch (`RESTRICT` on `patients.species_id` and
`exam_species.species_id` would block the delete otherwise, which is the
correct safety net if that assumption is ever wrong).

`downgrade` restores the placeholder list — reversible, but only meaningful
if nothing referenced the new species in between (same RESTRICT guard).

Originally written as `0014`, rebased to `0017` (after `0016`, itself
rebased from `0013`) — see `0016_create_imports_staging.py`'s docstring.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SPECIES_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-0000000000aa")
_PLACEHOLDER_SPECIES: tuple[str, ...] = ("Cão", "Gato", "Ave", "Outro")
_REAL_SPECIES: tuple[str, ...] = ("Canino", "Felino", "Bovino", "Equino", "Coelho", "Caprino")

species_table = sa.table(
    "species",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("name", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    op.execute(species_table.delete().where(species_table.c.name.in_(_PLACEHOLDER_SPECIES)))
    now = datetime.now(UTC)
    op.bulk_insert(
        species_table,
        [
            {"id": uuid.uuid5(_SPECIES_NAMESPACE, name), "name": name, "created_at": now}
            for name in _REAL_SPECIES
        ],
    )


def downgrade() -> None:
    op.execute(species_table.delete().where(species_table.c.name.in_(_REAL_SPECIES)))
    now = datetime.now(UTC)
    op.bulk_insert(
        species_table,
        [
            {"id": uuid.uuid5(_SPECIES_NAMESPACE, name), "name": name, "created_at": now}
            for name in _PLACEHOLDER_SPECIES
        ],
    )
