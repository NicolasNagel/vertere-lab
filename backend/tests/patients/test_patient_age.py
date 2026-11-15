from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.modules.patients.domain.entities import AgeUnit, Patient, PatientAge, PatientSex
from app.shared.domain.errors import ValidationError

_NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _patient() -> Patient:
    return Patient(
        id=uuid4(),
        name="Rex",
        species_id=uuid4(),
        sex=PatientSex.MALE,
        owner_name="Maria Souza",
        created_at=_NOW,
        updated_at=_NOW,
    )


@pytest.mark.parametrize(
    ("value", "unit", "text"),
    [
        (1, AgeUnit.YEARS, "1 ano"),
        (3, AgeUnit.YEARS, "3 anos"),
        (0, AgeUnit.MONTHS, "0 meses"),
        (1, AgeUnit.MONTHS, "1 mês"),
        (8, AgeUnit.MONTHS, "8 meses"),
    ],
)
def test_age_describes_itself_in_portuguese(value: int, unit: AgeUnit, text: str) -> None:
    assert PatientAge(value=value, unit=unit).describe() == text


@pytest.mark.parametrize(
    ("value", "unit"),
    [(-1, AgeUnit.YEARS), (121, AgeUnit.YEARS), (1441, AgeUnit.MONTHS), (-5, AgeUnit.MONTHS)],
)
def test_age_outside_the_allowed_range_is_rejected(value: int, unit: AgeUnit) -> None:
    with pytest.raises(ValidationError):
        PatientAge(value=value, unit=unit)


def test_age_pair_rules_for_optional_input() -> None:
    assert PatientAge.from_optional(None, None) is None
    assert PatientAge.from_optional(4, "YEARS") == PatientAge(value=4, unit=AgeUnit.YEARS)
    with pytest.raises(ValidationError):
        PatientAge.from_optional(4, None)
    with pytest.raises(ValidationError):
        PatientAge.from_optional(None, "MONTHS")
    with pytest.raises(ValidationError):
        PatientAge.from_optional(4, "WEEKS")


def test_recorded_date_changes_only_when_the_age_changes() -> None:
    patient = _patient()
    first_day, later_day = date(2026, 1, 10), date(2026, 6, 1)

    patient.change_age(PatientAge(value=3, unit=AgeUnit.YEARS), today=first_day)
    assert (patient.age_recorded_on, patient.age_description) == (first_day, "3 anos")

    # Mesma idade confirmada mais tarde: a data de registro não é reescrita.
    patient.change_age(PatientAge(value=3, unit=AgeUnit.YEARS), today=later_day)
    assert patient.age_recorded_on == first_day

    patient.change_age(PatientAge(value=4, unit=AgeUnit.YEARS), today=later_day)
    assert (patient.age_recorded_on, patient.age_description) == (later_day, "4 anos")

    patient.change_age(None, today=later_day)
    assert patient.age is None
    assert patient.age_recorded_on is None
