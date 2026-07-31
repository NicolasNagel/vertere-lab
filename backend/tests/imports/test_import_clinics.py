from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.clinics.domain.entities import ClinicStatus
from app.modules.imports.application.import_clinics import (
    SHEET_NAME,
    ImportClinicsCommand,
    ImportClinicsUseCase,
)
from app.shared.domain.errors import ForbiddenError
from tests.clinics.fakes import FakeAuditLogWriter, FakeClinicRepository
from tests.imports.fakes import FakeClock, FakeImportStagingRowRepository, make_staging_row

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _use_case(
    *, staging_rows: FakeImportStagingRowRepository, clinics: FakeClinicRepository
) -> ImportClinicsUseCase:
    return ImportClinicsUseCase(
        staging_rows=staging_rows,
        clinics=clinics,
        audit=FakeAuditLogWriter(),
        clock=FakeClock(_NOW),
    )


def _stage_clinic_row(
    staging_rows: FakeImportStagingRowRepository,
    batch_id: UUID,
    *,
    row_number: int,
    name: str,
    tax_id: str | None = None,
    status: str = "Ativo",
    observation: str | None = None,
) -> None:
    staging_rows.add_many(
        [
            make_staging_row(
                batch_id=batch_id,
                sheet_name=SHEET_NAME,
                source_row_number=row_number,
                raw_data={
                    "A": name,
                    "B": tax_id,
                    "C": "Rua Exemplo, 123",
                    "D": "(47) 99999-9999",
                    "E": "contato@exemplo.com",
                    "F": status,
                    "G": observation,
                },
            )
        ]
    )


def test_import_without_permission_is_forbidden() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_clinic_row(staging_rows, batch_id, row_number=3, name="Bicho Urbano")
    use_case = _use_case(staging_rows=staging_rows, clinics=FakeClinicRepository())

    with pytest.raises(ForbiddenError):
        use_case.execute(
            ImportClinicsCommand(actor_id=uuid4(), actor_permissions=frozenset(), batch_id=batch_id)
        )


def test_import_creates_clinic_from_staging_row() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_clinic_row(
        staging_rows,
        batch_id,
        row_number=3,
        name="Bicho Urbano",
        tax_id="21.804.204/0001-55",
    )
    clinics = FakeClinicRepository()
    use_case = _use_case(staging_rows=staging_rows, clinics=clinics)

    result = use_case.execute(
        ImportClinicsCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 1
    assert result.exceptions == ()
    clinic = clinics.get_by_name("Bicho Urbano")
    assert clinic is not None
    assert str(clinic.tax_id) == "21804204000155"
    assert clinic.status == ClinicStatus.ACTIVE


def test_import_skips_title_and_header_rows() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    staging_rows.add_many(
        [
            make_staging_row(
                batch_id=batch_id,
                sheet_name=SHEET_NAME,
                source_row_number=1,
                raw_data={"A": "CADASTRO DE CLÍNICAS"},
            ),
            make_staging_row(
                batch_id=batch_id,
                sheet_name=SHEET_NAME,
                source_row_number=2,
                raw_data={"A": "Clínica", "B": "CNPJ"},
            ),
        ]
    )
    clinics = FakeClinicRepository()
    use_case = _use_case(staging_rows=staging_rows, clinics=clinics)

    result = use_case.execute(
        ImportClinicsCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 0
    assert clinics.get_by_name("Clínica") is None


def test_import_with_invalid_tax_id_keeps_row_and_notes_raw_value() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_clinic_row(
        staging_rows,
        batch_id,
        row_number=3,
        name="Petsko",
        tax_id="6156243917",  # 10 digits
    )
    clinics = FakeClinicRepository()
    use_case = _use_case(staging_rows=staging_rows, clinics=clinics)

    result = use_case.execute(
        ImportClinicsCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 1
    clinic = clinics.get_by_name("Petsko")
    assert clinic is not None
    assert clinic.tax_id is None
    assert clinic.notes is not None
    assert "6156243917" in clinic.notes


def test_import_inactive_status_maps_to_inactive_clinic() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_clinic_row(staging_rows, batch_id, row_number=3, name="Luvet", status="Inativo")
    clinics = FakeClinicRepository()
    use_case = _use_case(staging_rows=staging_rows, clinics=clinics)

    use_case.execute(
        ImportClinicsCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    clinic = clinics.get_by_name("Luvet")
    assert clinic is not None
    assert clinic.status == ClinicStatus.INACTIVE


def test_reimporting_same_name_is_idempotent() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_clinic_row(staging_rows, batch_id, row_number=3, name="Bicho Urbano")
    clinics = FakeClinicRepository()
    use_case = _use_case(staging_rows=staging_rows, clinics=clinics)
    command = ImportClinicsCommand(
        actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
    )

    first = use_case.execute(command)
    second = use_case.execute(command)

    assert first.imported_count == 1
    assert second.imported_count == 0
    assert len(clinics.list_all_names()) == 1
