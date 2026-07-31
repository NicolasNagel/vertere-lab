from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.clinics.domain.entities import Clinic, ClinicStatus
from app.modules.imports.application.link_veterinarian_clinics_from_history import (
    SHEET_NAME,
    LinkVeterinarianClinicsFromHistoryCommand,
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


def test_link_without_permission_is_forbidden() -> None:
    batch_id = uuid4()
    use_case = _use_case(
        staging_rows=FakeImportStagingRowRepository(),
        clinics=FakeClinicRepository(),
        veterinarians=FakeVeterinarianRepository(),
        links=FakeVeterinarianClinicLinkRepository(),
    )

    with pytest.raises(ForbiddenError):
        use_case.execute(
            LinkVeterinarianClinicsFromHistoryCommand(
                actor_id=uuid4(), actor_permissions=frozenset(), batch_id=batch_id
            )
        )


def test_creates_missing_link_case_insensitively_matching_clinic_name() -> None:
    batch_id = uuid4()
    clinic = _clinic(name="Bea Pet Center")
    vet = _vet(name="Larissa Tomelin", crmv="123")
    staging_rows = FakeImportStagingRowRepository()
    # "Bea pet Center" (mixed case) is exactly the kind of typo found in the
    # real Dados sheet — it must resolve to the master clinic automatically.
    _stage_history_row(
        staging_rows,
        batch_id,
        row_number=5,
        clinic_name="Bea pet Center",
        vet_name="Larissa Tomelin",
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
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.links_created_count == 1
    assert result.exceptions == ()
    link = links.get(vet.id, clinic.id)
    assert link is not None
    assert link.primary_clinic is False


def test_unknown_veterinarian_becomes_exception_not_link() -> None:
    batch_id = uuid4()
    clinic = _clinic(name="Reale")
    staging_rows = FakeImportStagingRowRepository()
    _stage_history_row(
        staging_rows, batch_id, row_number=5, clinic_name="Reale", vet_name="Vet Desconhecido"
    )
    links = FakeVeterinarianClinicLinkRepository()
    use_case = _use_case(
        staging_rows=staging_rows,
        clinics=FakeClinicRepository({clinic.id: clinic}),
        veterinarians=FakeVeterinarianRepository(),
        links=links,
    )

    result = use_case.execute(
        LinkVeterinarianClinicsFromHistoryCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.links_created_count == 0
    assert len(result.exceptions) == 1
    assert "Vet Desconhecido" in result.exceptions[0].message


def test_existing_link_is_not_duplicated() -> None:
    batch_id = uuid4()
    clinic = _clinic(name="Amizade")
    vet = _vet(name="Amanda Pozzi", crmv="11816")
    staging_rows = FakeImportStagingRowRepository()
    for row_number in (5, 6, 7):
        _stage_history_row(
            staging_rows,
            batch_id,
            row_number=row_number,
            clinic_name="Amizade",
            vet_name="Amanda Pozzi",
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
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.links_created_count == 1
    assert len(links.list_by_veterinarian(vet.id)) == 1


def test_skips_header_rows_with_no_veterinarian_column() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    _stage_history_row(staging_rows, batch_id, row_number=4, clinic_name="Clínica", vet_name=None)
    use_case = _use_case(
        staging_rows=staging_rows,
        clinics=FakeClinicRepository(),
        veterinarians=FakeVeterinarianRepository(),
        links=FakeVeterinarianClinicLinkRepository(),
    )

    result = use_case.execute(
        LinkVeterinarianClinicsFromHistoryCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.links_created_count == 0
    assert result.exceptions == ()
