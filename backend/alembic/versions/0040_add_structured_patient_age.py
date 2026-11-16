"""add structured age (value + unit + recorded date) to patients

Revision ID: 0040
Revises: 0039
Create Date: 2026-11-14

Aditiva: `age_description` (texto livre) continua existindo para dado legado e importação.
O backfill converte só os textos inequívocos ("3 anos", "8 meses", "2a", "6m"); o resto
fica sem idade estruturada, com o texto original preservado.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_YEARS = r"^\s*(\d{1,2})\s*(anos?|a)\s*$"
_MONTHS = r"^\s*(\d{1,3})\s*(mes(es)?|m)\s*$"


def upgrade() -> None:
    op.add_column("patients", sa.Column("age_value", sa.SmallInteger(), nullable=True))
    op.add_column("patients", sa.Column("age_unit", sa.String(), nullable=True))
    op.add_column("patients", sa.Column("age_recorded_on", sa.Date(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE patients
            SET age_value = (regexp_match(age_description, :years, 'i'))[1]::smallint,
                age_unit = 'YEARS',
                age_recorded_on = created_at::date
            WHERE age_description ~* :years
            """
        ).bindparams(years=_YEARS)
    )
    op.execute(
        sa.text(
            """
            UPDATE patients
            SET age_value = (regexp_match(age_description, :months, 'i'))[1]::smallint,
                age_unit = 'MONTHS',
                age_recorded_on = created_at::date
            WHERE age_description ~* :months AND age_value IS NULL
            """
        ).bindparams(months=_MONTHS)
    )

    op.create_check_constraint(
        "ck_patients_age_pair", "patients", "(age_value IS NULL) = (age_unit IS NULL)"
    )
    op.create_check_constraint(
        "ck_patients_age_recorded", "patients", "(age_value IS NULL) = (age_recorded_on IS NULL)"
    )
    op.create_check_constraint(
        "ck_patients_age_range",
        "patients",
        "age_unit IS NULL OR (age_unit = 'YEARS' AND age_value BETWEEN 0 AND 120)"
        " OR (age_unit = 'MONTHS' AND age_value BETWEEN 0 AND 1440)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_patients_age_range", "patients", type_="check")
    op.drop_constraint("ck_patients_age_recorded", "patients", type_="check")
    op.drop_constraint("ck_patients_age_pair", "patients", type_="check")
    op.drop_column("patients", "age_recorded_on")
    op.drop_column("patients", "age_unit")
    op.drop_column("patients", "age_value")
