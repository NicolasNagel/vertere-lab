from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.clinics.domain.entities import ClinicStatus
from app.modules.imports.application.import_clinics import (
    SHEET_NAME,
    ImportClinicsCommand,
    ImportClinicsResult,
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


def _run(
    *rows: dict[str, str | None],
    permissions: frozenset[str] = frozenset({"imports.execute"}),
    times: int = 1,
) -> tuple[list[ImportClinicsResult], FakeClinicRepository]:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    for index, overrides in enumerate(rows):
        values: dict[str, str | None] = {"name": "Bicho Urbano", **overrides}
        _stage_clinic_row(staging_rows, batch_id, row_number=3 + index, **values)  # type: ignore[arg-type]
    clinics = FakeClinicRepository()
    use_case = _use_case(staging_rows=staging_rows, clinics=clinics)
    command = ImportClinicsCommand(
        actor_id=uuid4(), actor_permissions=permissions, batch_id=batch_id
    )
    return [use_case.execute(command) for _ in range(times)], clinics


def test_import_requires_permission_creates_clinics_and_is_idempotent() -> None:
    with pytest.raises(ForbiddenError):
        _run({}, permissions=frozenset())

    (first, second), clinics = _run({"tax_id": "21.804.204/0001-55"}, times=2)
    assert (first.imported_count, first.exceptions) == (1, ())
    assert second.imported_count == 0
    assert len(clinics.list_all_names()) == 1
    clinic = clinics.get_by_name("Bicho Urbano")
    assert clinic is not None
    assert str(clinic.tax_id) == "21804204000155"
    assert clinic.status == ClinicStatus.ACTIVE


def test_import_maps_status_and_keeps_rows_with_an_invalid_tax_id() -> None:
    (result,), clinics = _run(
        {"name": "Petsko", "tax_id": "6156243917"},  # 10 dígitos: inválido
        {"name": "Luvet", "status": "Inativo"},
    )
    assert result.imported_count == 2

    petsko = clinics.get_by_name("Petsko")
    assert petsko is not None
    assert petsko.tax_id is None
    assert "6156243917" in (petsko.notes or "")  # o valor cru fica nas notas
    luvet = clinics.get_by_name("Luvet")
    assert luvet is not None
    assert luvet.status == ClinicStatus.INACTIVE


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

    result = _use_case(staging_rows=staging_rows, clinics=clinics).execute(
        ImportClinicsCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 0
    assert clinics.get_by_name("Clínica") is None
