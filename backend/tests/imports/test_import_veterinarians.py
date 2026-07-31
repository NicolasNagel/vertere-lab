from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.clinics.domain.entities import Clinic, ClinicStatus
from app.modules.imports.application.import_veterinarians import (
    SHEET_NAME,
    ImportVeterinariansCommand,
    ImportVeterinariansUseCase,
)
from app.shared.domain.errors import ForbiddenError
from tests.imports.fakes import FakeClock, FakeImportStagingRowRepository, make_staging_row
from tests.veterinarian_clinics.fakes import (
    FakeAuditLogWriter,
    FakeClinicRepository,
    FakeVeterinarianClinicLinkRepository,
    FakeVeterinarianRepository,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _clinic(*, name: str) -> Clinic:
    return Clinic(
        id=uuid4(),
        name=name,
        status=ClinicStatus.ACTIVE,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _use_case(
    *,
    staging_rows: FakeImportStagingRowRepository,
    veterinarians: FakeVeterinarianRepository,
    clinics: FakeClinicRepository,
    links: FakeVeterinarianClinicLinkRepository,
) -> ImportVeterinariansUseCase:
    return ImportVeterinariansUseCase(
        staging_rows=staging_rows,
        veterinarians=veterinarians,
        clinics=clinics,
        links=links,
        audit=FakeAuditLogWriter(),
        clock=FakeClock(_NOW),
    )


def _stage_vet_row(
    staging_rows: FakeImportStagingRowRepository,
    batch_id: UUID,
    *,
    row_number: int,
    clinic_name: str,
    vet_name: str,
    crmv: str | None,
    status: str = "Ativo",
) -> None:
    staging_rows.add_many(
        [
            make_staging_row(
                batch_id=batch_id,
                sheet_name=SHEET_NAME,
                source_row_number=row_number,
                raw_data={
                    "A": clinic_name,
                    "B": vet_name,
                    "C": crmv,
                    "D": "(47) 99999-9999",
                    "E": "vet@exemplo.com",
                    "F": status,
                    "G": None,
                },
            )
        ]
    )


def test_import_without_permission_is_forbidden() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    clinics = FakeClinicRepository({(c := _clinic(name="Amizade")).id: c})
    _stage_vet_row(
        staging_rows,
        batch_id,
        row_number=3,
        clinic_name="Amizade",
        vet_name="Amanda Pozzi",
        crmv="11816",
    )
    use_case = _use_case(
        staging_rows=staging_rows,
        veterinarians=FakeVeterinarianRepository(),
        clinics=clinics,
        links=FakeVeterinarianClinicLinkRepository(),
    )

    with pytest.raises(ForbiddenError):
        use_case.execute(
            ImportVeterinariansCommand(
                actor_id=uuid4(), actor_permissions=frozenset(), batch_id=batch_id
            )
        )


def test_import_creates_veterinarian_and_links_to_clinic() -> None:
    batch_id = uuid4()
    clinic = _clinic(name="Amizade")
    staging_rows = FakeImportStagingRowRepository()
    _stage_vet_row(
        staging_rows,
        batch_id,
        row_number=3,
        clinic_name="Amizade",
        vet_name="Amanda Pozzi",
        crmv="11816",
    )
    veterinarians = FakeVeterinarianRepository()
    links = FakeVeterinarianClinicLinkRepository()
    use_case = _use_case(
        staging_rows=staging_rows,
        veterinarians=veterinarians,
        clinics=FakeClinicRepository({clinic.id: clinic}),
        links=links,
    )

    result = use_case.execute(
        ImportVeterinariansCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 1
    assert result.exceptions == ()
    vet = veterinarians.get_by_name("Amanda Pozzi")
    assert vet is not None
    assert vet.is_autonomous is False
    link = links.get(vet.id, clinic.id)
    assert link is not None
    assert link.primary_clinic is True


def test_import_marks_autonomous_when_clinic_is_autonomos() -> None:
    batch_id = uuid4()
    clinic = _clinic(name="Autonomos")
    staging_rows = FakeImportStagingRowRepository()
    _stage_vet_row(
        staging_rows,
        batch_id,
        row_number=3,
        clinic_name="Autonomos",
        vet_name="Amanda Freitas",
        crmv="7746",
    )
    veterinarians = FakeVeterinarianRepository()
    use_case = _use_case(
        staging_rows=staging_rows,
        veterinarians=veterinarians,
        clinics=FakeClinicRepository({clinic.id: clinic}),
        links=FakeVeterinarianClinicLinkRepository(),
    )

    use_case.execute(
        ImportVeterinariansCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    vet = veterinarians.get_by_name("Amanda Freitas")
    assert vet is not None
    assert vet.is_autonomous is True


def test_import_reports_clinic_not_found_without_stopping_other_rows() -> None:
    batch_id = uuid4()
    clinic = _clinic(name="Amizade")
    staging_rows = FakeImportStagingRowRepository()
    _stage_vet_row(
        staging_rows,
        batch_id,
        row_number=3,
        clinic_name="Clínica Inexistente",
        vet_name="Fulano",
        crmv="1",
    )
    _stage_vet_row(
        staging_rows,
        batch_id,
        row_number=4,
        clinic_name="Amizade",
        vet_name="Amanda Pozzi",
        crmv="11816",
    )
    veterinarians = FakeVeterinarianRepository()
    use_case = _use_case(
        staging_rows=staging_rows,
        veterinarians=veterinarians,
        clinics=FakeClinicRepository({clinic.id: clinic}),
        links=FakeVeterinarianClinicLinkRepository(),
    )

    result = use_case.execute(
        ImportVeterinariansCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 1
    assert len(result.exceptions) == 1
    assert result.exceptions[0].source_row_number == 3
    assert veterinarians.get_by_name("Amanda Pozzi") is not None
    assert veterinarians.get_by_name("Fulano") is None


def test_import_reports_missing_crmv_as_exception() -> None:
    batch_id = uuid4()
    clinic = _clinic(name="Amizade")
    staging_rows = FakeImportStagingRowRepository()
    _stage_vet_row(
        staging_rows, batch_id, row_number=3, clinic_name="Amizade", vet_name="Sem Crmv", crmv=None
    )
    use_case = _use_case(
        staging_rows=staging_rows,
        veterinarians=FakeVeterinarianRepository(),
        clinics=FakeClinicRepository({clinic.id: clinic}),
        links=FakeVeterinarianClinicLinkRepository(),
    )

    result = use_case.execute(
        ImportVeterinariansCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 0
    assert len(result.exceptions) == 1


def test_reimporting_same_batch_is_idempotent() -> None:
    batch_id = uuid4()
    clinic = _clinic(name="Amizade")
    staging_rows = FakeImportStagingRowRepository()
    _stage_vet_row(
        staging_rows,
        batch_id,
        row_number=3,
        clinic_name="Amizade",
        vet_name="Amanda Pozzi",
        crmv="11816",
    )
    veterinarians = FakeVeterinarianRepository()
    links = FakeVeterinarianClinicLinkRepository()
    use_case = _use_case(
        staging_rows=staging_rows,
        veterinarians=veterinarians,
        clinics=FakeClinicRepository({clinic.id: clinic}),
        links=links,
    )
    command = ImportVeterinariansCommand(
        actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
    )

    first = use_case.execute(command)
    second = use_case.execute(command)

    assert first.imported_count == 1
    assert second.imported_count == 0
    vet = veterinarians.get_by_name("Amanda Pozzi")
    assert vet is not None
    assert len(links.list_by_veterinarian(vet.id)) == 1
