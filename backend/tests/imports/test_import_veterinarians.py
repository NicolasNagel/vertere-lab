from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.clinics.domain.entities import Clinic, ClinicStatus
from app.modules.imports.application.import_veterinarians import (
    SHEET_NAME,
    ImportVeterinariansCommand,
    ImportVeterinariansResult,
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


def _run(
    *rows: dict[str, str | None],
    clinics: tuple[str, ...] = ("Amizade",),
    permissions: frozenset[str] = frozenset({"imports.execute"}),
    times: int = 1,
) -> tuple[
    list[ImportVeterinariansResult],
    FakeVeterinarianRepository,
    FakeVeterinarianClinicLinkRepository,
    dict[str, Clinic],
]:
    """Stage `rows` (defaults: Amanda Pozzi, CRMV 11816, Amizade) and run the import `times`."""
    batch_id = uuid4()
    by_name = {name: _clinic(name=name) for name in clinics}
    staging_rows = FakeImportStagingRowRepository()
    for index, overrides in enumerate(rows):
        values: dict[str, str | None] = {
            "clinic_name": "Amizade",
            "vet_name": "Amanda Pozzi",
            "crmv": "11816",
            **overrides,
        }
        _stage_vet_row(staging_rows, batch_id, row_number=3 + index, **values)  # type: ignore[arg-type]
    veterinarians = FakeVeterinarianRepository()
    links = FakeVeterinarianClinicLinkRepository()
    use_case = _use_case(
        staging_rows=staging_rows,
        veterinarians=veterinarians,
        clinics=FakeClinicRepository({clinic.id: clinic for clinic in by_name.values()}),
        links=links,
    )
    command = ImportVeterinariansCommand(
        actor_id=uuid4(), actor_permissions=permissions, batch_id=batch_id
    )
    return [use_case.execute(command) for _ in range(times)], veterinarians, links, by_name


def test_import_requires_permission_links_to_the_clinic_and_is_idempotent() -> None:
    with pytest.raises(ForbiddenError):
        _run({}, permissions=frozenset())

    (first, second), veterinarians, links, clinics = _run({}, times=2)
    assert (first.imported_count, first.exceptions) == (1, ())
    assert second.imported_count == 0
    vet = veterinarians.get_by_name("Amanda Pozzi")
    assert vet is not None
    assert vet.is_autonomous is False
    link = links.get(vet.id, clinics["Amizade"].id)
    assert link is not None
    assert link.primary_clinic is True
    assert len(links.list_by_veterinarian(vet.id)) == 1  # reimportar não duplica o vínculo


def test_import_marks_autonomous_and_reports_bad_rows_without_stopping_the_batch() -> None:
    (result,), veterinarians, _, _ = _run(
        {"clinic_name": "Autonomos", "vet_name": "Amanda Freitas", "crmv": "7746"},
        {"clinic_name": "Clínica Inexistente", "vet_name": "Fulano", "crmv": "1"},
        {"vet_name": "Sem Crmv", "crmv": None},
        clinics=("Autonomos", "Amizade"),
    )

    assert result.imported_count == 1
    assert [row.source_row_number for row in result.exceptions] == [4, 5]
    autonomous = veterinarians.get_by_name("Amanda Freitas")
    assert autonomous is not None
    assert autonomous.is_autonomous is True
    assert veterinarians.get_by_name("Fulano") is None
    assert veterinarians.get_by_name("Sem Crmv") is None
