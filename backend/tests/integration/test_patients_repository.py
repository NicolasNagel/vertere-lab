"""Integração com PostgreSQL real: o repositório de pacientes não pode deixar uma escrita
com versão velha sobrescrever outra já gravada (lost update).

QA 2026-11-19: dois PATCH simultâneos com a mesma `expected_row_version` responderam 200 e 200,
porque `save()` gravava `row_version + 1` sem conferir a versão que estava no banco.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.modules.patients.domain.entities import Patient, PatientSex
from app.modules.patients.infrastructure.repositories import SqlAlchemyPatientRepository
from app.shared.domain.errors import ConflictError

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _reset_data(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        session.execute(text("DELETE FROM patients"))
        session.commit()


def _new_patient(session_factory: sessionmaker[Session]) -> UUID:
    now = datetime.now(UTC)
    with session_factory() as session:
        species_id = session.execute(text("SELECT id FROM species LIMIT 1")).scalar_one()
        patient = Patient(
            id=uuid4(),
            name="Rex",
            species_id=species_id,
            sex=PatientSex.MALE,
            owner_name="Maria",
            created_at=now,
            updated_at=now,
        )
        SqlAlchemyPatientRepository(session).add(patient)
        session.commit()
        return patient.id


def test_a_stale_save_is_a_conflict_not_a_silent_overwrite(
    session_factory: sessionmaker[Session],
) -> None:
    patient_id = _new_patient(session_factory)

    with session_factory() as first, session_factory() as second:
        first_copy = SqlAlchemyPatientRepository(first).get_by_id(patient_id, for_update=True)
        assert first_copy is not None
        first_copy.name = "Primeiro"
        # `second` read the same row before `first` committed.
        stale_copy = SqlAlchemyPatientRepository(second).get_by_id(patient_id)
        assert stale_copy is not None
        assert stale_copy.row_version == first_copy.row_version

        SqlAlchemyPatientRepository(first).save(first_copy)
        first.commit()

        stale_copy.name = "Segundo"
        with pytest.raises(ConflictError):
            SqlAlchemyPatientRepository(second).save(stale_copy)
        second.rollback()

    with session_factory() as session:
        stored = SqlAlchemyPatientRepository(session).get_by_id(patient_id)
    assert stored is not None
    assert (stored.name, stored.row_version) == ("Primeiro", 2)


def test_sequential_saves_each_bump_the_version_once(
    session_factory: sessionmaker[Session],
) -> None:
    patient_id = _new_patient(session_factory)

    for expected_version, name in ((2, "Um"), (3, "Dois")):
        with session_factory() as session:
            repository = SqlAlchemyPatientRepository(session)
            patient = repository.get_by_id(patient_id, for_update=True)
            assert patient is not None
            patient.name = name
            repository.save(patient)
            session.commit()
            assert patient.row_version == expected_version
