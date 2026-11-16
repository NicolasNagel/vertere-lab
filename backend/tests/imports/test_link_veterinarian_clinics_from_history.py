from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.clinics.domain.entities import Clinic, ClinicStatus
from app.modules.imports.application.link_veterinarian_clinics_from_history import (
    SHEET_NAME,
    LinkVeterinarianClinicsFromHistoryCommand,
    LinkVeterinarianClinicsFromHistoryResult,
    LinkVeterinarianClinicsFromHistoryUseCase,
)
from app.modules.veterinarians.domain.entities import Veterinarian, VeterinarianStatus
from app.modules.veterinarians.domain.value_objects import Crmv
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
        id=uuid4(), name=name, status=ClinicStatus.ACTIVE, created_at=_NOW, updated_at=_NOW
    )


def _vet(*, name: str, crmv: str) -> Veterinarian:
    return Veterinarian(
        id=uuid4(),
        name=name,
        crmv=Crmv(crmv),
        is_autonomous=True,
        status=VeterinarianStatus.ACTIVE,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _stage_history_row(
    staging_rows: FakeImportStagingRowRepository,
    batch_id: UUID,
    *,
    row_number: int,
    clinic_name: str | None,
    vet_name: str | None,
) -> None:
    staging_rows.add_many(
        [
            make_staging_row(
                batch_id=batch_id,
                sheet_name=SHEET_NAME,
                source_row_number=row_number,
                raw_data={"A": clinic_name, "H": vet_name},
            )
        ]
    )


def _use_case(
    *,
    staging_rows: FakeImportStagingRowRepository,
    clinics: FakeClinicRepository,
    veterinarians: FakeVeterinarianRepository,
    links: FakeVeterinarianClinicLinkRepository,
) -> LinkVeterinarianClinicsFromHistoryUseCase:
    return LinkVeterinarianClinicsFromHistoryUseCase(
        staging_rows=staging_rows,
        clinics=clinics,
        veterinarians=veterinarians,
        links=links,
        audit=FakeAuditLogWriter(),
        clock=FakeClock(_NOW),
    )


def _run(
    *rows: tuple[str | None, str | None],
    permissions: frozenset[str] = frozenset({"imports.execute"}),
) -> tuple[
    LinkVeterinarianClinicsFromHistoryResult,
    FakeVeterinarianClinicLinkRepository,
    Clinic,
    Veterinarian,
]:
    """Stage `(clinic_name, vet_name)` history rows against one clinic and one veterinarian."""
    batch_id = uuid4()
    clinic = _clinic(name="Bea Pet Center")
    vet = _vet(name="Larissa Tomelin", crmv="123")
    staging_rows = FakeImportStagingRowRepository()
    for index, (clinic_name, vet_name) in enumerate(rows):
        _stage_history_row(
            staging_rows, batch_id, row_number=5 + index, clinic_name=clinic_name, vet_name=vet_name
        )
    links = FakeVeterinarianClinicLinkRepository()
    use_case = _use_case(
        staging_rows=staging_rows,
        clinics=FakeClinicRepository({clinic.id: clinic}),
        veterinarians=FakeVeterinarianRepository({vet.id: vet}),
        links=links,
    )
    result = use_case.execute(
        LinkVeterinarianClinicsFromHistoryCommand(
            actor_id=uuid4(), actor_permissions=permissions, batch_id=batch_id
        )
    )
    return result, links, clinic, vet


def test_link_requires_permission() -> None:
    with pytest.raises(ForbiddenError):
        _run(permissions=frozenset())


def test_link_creates_missing_links_once_and_reports_unknown_veterinarians() -> None:
    # "Bea pet Center" (caixa mista) é o tipo de erro da planilha real: resolve para a clínica
    # mestre sem intervenção. Três linhas do mesmo par geram um único vínculo.
    result, links, clinic, vet = _run(
        ("Bea pet Center", "Larissa Tomelin"),
        ("Bea Pet Center", "Larissa Tomelin"),
        ("BEA PET CENTER", "Larissa Tomelin"),
    )
    assert (result.links_created_count, result.exceptions) == (1, ())
    link = links.get(vet.id, clinic.id)
    assert link is not None
    assert link.primary_clinic is False
    assert len(links.list_by_veterinarian(vet.id)) == 1

    # Veterinário desconhecido vira exceção, não vínculo; cabeçalho sem veterinário é ignorado.
    result, links, _, _ = _run(("Bea Pet Center", "Vet Desconhecido"), ("Clínica", None))
    assert result.links_created_count == 0
    assert len(result.exceptions) == 1
    assert "Vet Desconhecido" in result.exceptions[0].message
