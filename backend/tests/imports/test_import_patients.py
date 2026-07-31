from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.imports.application.import_patients import (
    SHEET_NAME,
    ImportPatientsCommand,
    ImportPatientsUseCase,
)
from app.modules.patients.domain.entities import PatientSex, Species
from app.shared.domain.errors import ForbiddenError
from tests.imports.fakes import FakeClock, FakeImportStagingRowRepository, make_staging_row
from tests.patients.fakes import FakeAuditLogWriter, FakePatientRepository, FakeSpeciesRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_CANINO_ID = uuid4()
_FELINO_ID = uuid4()


def _species() -> FakeSpeciesRepository:
    return FakeSpeciesRepository(
        [
            Species(id=_CANINO_ID, name="Canino", created_at=_NOW),
            Species(id=_FELINO_ID, name="Felino", created_at=_NOW),
        ]
    )


def _use_case(
    *,
    staging_rows: FakeImportStagingRowRepository,
    patients: FakePatientRepository,
    species: FakeSpeciesRepository | None = None,
) -> ImportPatientsUseCase:
    return ImportPatientsUseCase(
        staging_rows=staging_rows,
        patients=patients,
        species=species or _species(),
        audit=FakeAuditLogWriter(),
        clock=FakeClock(_NOW),
    )


def _stage_dados_row(
    staging_rows: FakeImportStagingRowRepository,
    batch_id: UUID,
    *,
    row_number: int,
    clinic: str | None,
    date_serial: str = "46025",
    patient: str | None,
    species_name: str | None,
    breed: str | None = None,
    sex: str | None,
    age: str | None = None,
    owner: str | None,
) -> None:
    staging_rows.add_many(
        [
            make_staging_row(
                batch_id=batch_id,
                sheet_name=SHEET_NAME,
                source_row_number=row_number,
                raw_data={
                    "A": clinic,
                    "B": date_serial,
                    "I": patient,
                    "J": species_name,
                    "K": breed,
                    "L": sex,
                    "M": age,
                    "N": owner,
                },
            )
        ]
    )


def test_import_without_permission_is_forbidden() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        clinic="Amizade",
        patient="Rex",
        species_name="Canino",
        sex="Macho",
        owner="Maria",
    )
    use_case = _use_case(staging_rows=staging_rows, patients=FakePatientRepository())

    with pytest.raises(ForbiddenError):
        use_case.execute(
            ImportPatientsCommand(
                actor_id=uuid4(), actor_permissions=frozenset(), batch_id=batch_id
            )
        )


def test_import_creates_patient_with_owner_and_species() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        clinic="Amizade",
        patient="Rex",
        species_name="Canino",
        breed="SRD",
        sex="Macho",
        age="5a",
        owner="Maria",
    )
    patients = FakePatientRepository()
    use_case = _use_case(staging_rows=staging_rows, patients=patients)

    result = use_case.execute(
        ImportPatientsCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 1
    assert result.exceptions == ()
    patient = patients.get_by_owner_and_name(owner_name="Maria", name="Rex")
    assert patient is not None
    assert patient.species_id == _CANINO_ID
    assert patient.sex == PatientSex.MALE
    assert patient.breed == "SRD"
    assert patient.age_description == "5a"


def test_owner_code_in_parens_goes_to_notes_not_owner_document() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        clinic="Amizade",
        patient="Rex",
        species_name="Canino",
        sex="Macho",
        owner="Maria (15092)",
    )
    patients = FakePatientRepository()
    use_case = _use_case(staging_rows=staging_rows, patients=patients)

    use_case.execute(
        ImportPatientsCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    patient = patients.get_by_owner_and_name(owner_name="Maria", name="Rex")
    assert patient is not None
    assert patient.owner_document is None
    assert patient.notes is not None
    assert "15092" in patient.notes


def test_owner_ni_marker_notes_missing_owner_not_a_document() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        clinic="Amizade",
        patient="Rex",
        species_name="Canino",
        sex="Macho",
        owner="Priscila (NI)",
    )
    patients = FakePatientRepository()
    use_case = _use_case(staging_rows=staging_rows, patients=patients)

    use_case.execute(
        ImportPatientsCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    patient = patients.get_by_owner_and_name(owner_name="Priscila", name="Rex")
    assert patient is not None
    assert patient.owner_document is None
    assert "NI" in (patient.notes or "")


def test_species_case_insensitive_match_fixes_lowercase_typo() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        clinic="Amizade",
        patient="Mimosa",
        species_name="canino",  # lowercase typo, like the real spreadsheet's "bovino"
        sex="Fêmea",
        owner="Ana",
    )
    patients = FakePatientRepository()
    use_case = _use_case(staging_rows=staging_rows, patients=patients)

    result = use_case.execute(
        ImportPatientsCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 1
    patient = patients.get_by_owner_and_name(owner_name="Ana", name="Mimosa")
    assert patient is not None
    assert patient.species_id == _CANINO_ID


def test_repeat_visits_same_clinic_merge_using_most_recent_data() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        date_serial="46000",
        clinic="Amizade",
        patient="Rex",
        species_name="Canino",
        sex=None,  # sex unknown on the earlier visit
        owner="Maria",
    )
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=6,
        date_serial="46100",
        clinic="Amizade",
        patient="Rex",
        species_name="Canino",
        sex="Macho",  # known on the later visit
        owner="Maria",
    )
    patients = FakePatientRepository()
    use_case = _use_case(staging_rows=staging_rows, patients=patients)

    result = use_case.execute(
        ImportPatientsCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 1
    patient = patients.get_by_owner_and_name(owner_name="Maria", name="Rex")
    assert patient is not None
    assert patient.sex == PatientSex.MALE


def test_missing_sex_across_all_occurrences_becomes_exception() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        clinic="Amizade",
        patient="Rex",
        species_name="Canino",
        sex=None,
        owner="Maria",
    )
    patients = FakePatientRepository()
    use_case = _use_case(staging_rows=staging_rows, patients=patients)

    result = use_case.execute(
        ImportPatientsCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 0
    assert len(result.exceptions) == 1
    assert patients.get_by_owner_and_name(owner_name="Maria", name="Rex") is None


def test_missing_species_becomes_exception() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        clinic="Amizade",
        patient="Rex",
        species_name=None,
        sex="Macho",
        owner="Maria",
    )
    patients = FakePatientRepository()
    use_case = _use_case(staging_rows=staging_rows, patients=patients)

    result = use_case.execute(
        ImportPatientsCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 0
    assert len(result.exceptions) == 1


def test_unresolvable_species_becomes_exception() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        clinic="Amizade",
        patient="Rex",
        species_name="Dinossauro",
        sex="Macho",
        owner="Maria",
    )
    patients = FakePatientRepository()
    use_case = _use_case(staging_rows=staging_rows, patients=patients)

    result = use_case.execute(
        ImportPatientsCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 0
    assert len(result.exceptions) == 1


def test_same_owner_and_pet_name_under_different_clinic_becomes_exception_not_merge() -> None:
    # Regression built from a real finding: (owner, patient) pairs sometimes
    # recur under a *different* clinic in the source data (8 of 1526 pairs in
    # the real spreadsheet). Since `Patient` has no clinic field, this is
    # genuinely ambiguous — never silently merge or silently duplicate.
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    for row_number in (5, 6):  # two visits at the primary clinic
        _stage_dados_row(
            staging_rows,
            batch_id,
            row_number=row_number,
            clinic="Bicho Urbano",
            patient="Cookie",
            species_name="Canino",
            sex="Fêmea",
            owner="Aline",
        )
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=7,  # single visit at a different clinic
        clinic="Entrepatas",
        patient="Cookie",
        species_name="Canino",
        sex="Fêmea",
        owner="Aline",
    )
    patients = FakePatientRepository()
    use_case = _use_case(staging_rows=staging_rows, patients=patients)

    result = use_case.execute(
        ImportPatientsCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 1
    assert len(result.exceptions) == 1
    assert result.exceptions[0].source_row_number == 7
    assert patients.get_by_owner_and_name(owner_name="Aline", name="Cookie") is not None


def test_reimporting_same_batch_is_idempotent() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_dados_row(
        staging_rows,
        batch_id,
        row_number=5,
        clinic="Amizade",
        patient="Rex",
        species_name="Canino",
        sex="Macho",
        owner="Maria",
    )
    patients = FakePatientRepository()
    use_case = _use_case(staging_rows=staging_rows, patients=patients)
    command = ImportPatientsCommand(
        actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
    )

    first = use_case.execute(command)
    second = use_case.execute(command)

    assert first.imported_count == 1
    assert second.imported_count == 0
    assert second.skipped_existing_count == 1
