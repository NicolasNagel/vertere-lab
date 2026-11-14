from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.imports.application.import_patients import (
    SHEET_NAME,
    ImportPatientsCommand,
    ImportPatientsResult,
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


def _run(
    *rows: dict[str, str | None],
    permissions: frozenset[str] = frozenset({"imports.execute"}),
    times: int = 1,
) -> tuple[list[ImportPatientsResult], FakePatientRepository]:
    """Stage `rows` (defaults: Rex/Canino/Macho/Maria at Amizade) and run the import `times`."""
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    for index, overrides in enumerate(rows):
        values: dict[str, str | None] = {
            "clinic": "Amizade",
            "patient": "Rex",
            "species_name": "Canino",
            "sex": "Macho",
            "owner": "Maria",
            **overrides,
        }
        _stage_dados_row(staging_rows, batch_id, row_number=5 + index, **values)  # type: ignore[arg-type]
    patients = FakePatientRepository()
    use_case = _use_case(staging_rows=staging_rows, patients=patients)
    command = ImportPatientsCommand(
        actor_id=uuid4(), actor_permissions=permissions, batch_id=batch_id
    )
    return [use_case.execute(command) for _ in range(times)], patients


def test_import_requires_permission_and_is_idempotent() -> None:
    with pytest.raises(ForbiddenError):
        _run({}, permissions=frozenset())

    (first, second), patients = _run({}, times=2)
    assert (first.imported_count, first.exceptions) == (1, ())
    assert (second.imported_count, second.skipped_existing_count) == (0, 1)
    assert patients.get_by_owner_and_name(owner_name="Maria", name="Rex") is not None


def test_import_maps_species_sex_owner_code_and_merges_repeat_visits() -> None:
    (result,), patients = _run(
        {"breed": "SRD", "age": "5a"},
        {"patient": "Mimosa", "species_name": "canino", "sex": "Fêmea", "owner": "Ana"},
        # Código entre parênteses vai para as notas, nunca para o documento do tutor.
        {"patient": "Bolt", "owner": "Carlos (15092)"},
        {"patient": "Luna", "owner": "Priscila (NI)"},
    )
    assert (result.imported_count, result.exceptions) == (4, ())

    rex = patients.get_by_owner_and_name(owner_name="Maria", name="Rex")
    assert rex is not None
    assert (rex.species_id, rex.sex, rex.breed, rex.age_description) == (
        _CANINO_ID,
        PatientSex.MALE,
        "SRD",
        "5a",
    )
    mimosa = patients.get_by_owner_and_name(owner_name="Ana", name="Mimosa")
    assert mimosa is not None
    assert mimosa.species_id == _CANINO_ID  # "canino" minúsculo casa com "Canino"

    bolt = patients.get_by_owner_and_name(owner_name="Carlos", name="Bolt")
    assert bolt is not None
    assert bolt.owner_document is None
    assert "15092" in (bolt.notes or "")
    luna = patients.get_by_owner_and_name(owner_name="Priscila", name="Luna")
    assert luna is not None
    assert luna.owner_document is None
    assert "NI" in (luna.notes or "")

    # Visitas repetidas na mesma clínica se fundem usando o dado mais recente.
    (merged,), merged_patients = _run(
        {"date_serial": "46000", "sex": None},  # sexo desconhecido na visita antiga
        {"date_serial": "46100", "sex": "Macho"},
    )
    assert merged.imported_count == 1
    merged_rex = merged_patients.get_by_owner_and_name(owner_name="Maria", name="Rex")
    assert merged_rex is not None
    assert merged_rex.sex == PatientSex.MALE


def test_import_turns_unresolvable_patients_into_exceptions() -> None:
    unresolvable: list[dict[str, str | None]] = [
        {"sex": None},
        {"species_name": None},
        {"species_name": "Dinossauro"},
    ]
    for overrides in unresolvable:
        (result,), patients = _run(overrides)
        assert result.imported_count == 0, overrides
        assert len(result.exceptions) == 1, overrides
        assert patients.get_by_owner_and_name(owner_name="Maria", name="Rex") is None

    # Mesmo (tutor, animal) sob outra clínica é ambíguo (Patient não tem clínica): nunca funde
    # nem duplica em silêncio. Caso real: 8 de 1526 pares na planilha.
    cookie = {"patient": "Cookie", "sex": "Fêmea", "owner": "Aline"}
    (result,), patients = _run(
        {"clinic": "Bicho Urbano", **cookie},
        {"clinic": "Bicho Urbano", **cookie},
        {"clinic": "Entrepatas", **cookie},
    )
    assert result.imported_count == 1
    assert [row.source_row_number for row in result.exceptions] == [7]
    assert patients.get_by_owner_and_name(owner_name="Aline", name="Cookie") is not None
