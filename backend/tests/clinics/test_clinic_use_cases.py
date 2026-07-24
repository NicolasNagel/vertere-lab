from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.clinics.application.create_clinic import CreateClinicCommand, CreateClinicUseCase
from app.modules.clinics.application.deactivate_clinic import (
    DeactivateClinicCommand,
    DeactivateClinicUseCase,
)
from app.modules.clinics.application.get_clinic import GetClinicQuery, GetClinicUseCase
from app.modules.clinics.application.list_clinics import ListClinicsQuery, ListClinicsUseCase
from app.modules.clinics.application.update_clinic import UpdateClinicCommand, UpdateClinicUseCase
from app.modules.clinics.domain.entities import ClinicStatus
from app.modules.clinics.domain.errors import DuplicateTaxIdError
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError
from tests.clinics.fakes import FakeAuditLogWriter, FakeClinicRepository, FakeClock

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _actor(*, permissions: frozenset[str]) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        id=uuid4(),
        email="user@vertere.local",
        full_name="User",
        role_id=uuid4(),
        role_name="RECEPTION",
        permissions=permissions,
    )


def _create_command(**overrides: object) -> CreateClinicCommand:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"clinics.manage"})),
        "name": "Clínica Vet",
        "tax_id": "78977352000199",
        "phone": "(47) 99999-0000",
        "email": "contato@clinicavet.com.br",
        "address_zip_code": None,
        "address_street": None,
        "address_number": None,
        "address_neighborhood": None,
        "address_city": None,
        "address_state": None,
        "address_complement": None,
        "notes": None,
    }
    defaults.update(overrides)
    return CreateClinicCommand(**defaults)  # type: ignore[arg-type]


def test_create_clinic_succeeds_and_audits() -> None:
    clinics = FakeClinicRepository()
    audit = FakeAuditLogWriter()
    use_case = CreateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW))

    result = use_case.execute(_create_command())

    assert result.name == "Clínica Vet"
    assert result.status == ClinicStatus.ACTIVE.value
    assert clinics.get_by_id(result.id) is not None
    assert audit.entries[0].action == "clinics.created"


def test_create_clinic_without_permission_is_forbidden() -> None:
    clinics = FakeClinicRepository()
    audit = FakeAuditLogWriter()
    use_case = CreateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW))

    with pytest.raises(ForbiddenError):
        use_case.execute(_create_command(actor=_actor(permissions=frozenset())))


def test_create_clinic_with_duplicate_tax_id_conflicts() -> None:
    clinics = FakeClinicRepository()
    audit = FakeAuditLogWriter()
    use_case = CreateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW))
    use_case.execute(_create_command())

    with pytest.raises(DuplicateTaxIdError):
        use_case.execute(_create_command(name="Outra Clínica"))


def test_update_clinic_with_stale_row_version_conflicts() -> None:
    clinics = FakeClinicRepository()
    audit = FakeAuditLogWriter()
    created = CreateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW)).execute(
        _create_command()
    )

    use_case = UpdateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW))
    with pytest.raises(ConflictError):
        use_case.execute(
            UpdateClinicCommand(
                actor=_actor(permissions=frozenset({"clinics.manage"})),
                clinic_id=created.id,
                name="Clínica Vet Renomeada",
                tax_id=created.tax_id,
                phone=None,
                email=None,
                status=ClinicStatus.ACTIVE.value,
                address_zip_code=None,
                address_street=None,
                address_number=None,
                address_neighborhood=None,
                address_city=None,
                address_state=None,
                address_complement=None,
                notes=None,
                expected_row_version=created.row_version + 1,
            )
        )


def test_update_clinic_succeeds_and_bumps_row_version() -> None:
    clinics = FakeClinicRepository()
    audit = FakeAuditLogWriter()
    created = CreateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW)).execute(
        _create_command()
    )

    use_case = UpdateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW))
    result = use_case.execute(
        UpdateClinicCommand(
            actor=_actor(permissions=frozenset({"clinics.manage"})),
            clinic_id=created.id,
            name="Clínica Vet Renomeada",
            tax_id=created.tax_id,
            phone=None,
            email=None,
            status=ClinicStatus.SPECIAL.value,
            address_zip_code=None,
            address_street=None,
            address_number=None,
            address_neighborhood=None,
            address_city=None,
            address_state=None,
            address_complement=None,
            notes=None,
            expected_row_version=created.row_version,
        )
    )

    assert result.name == "Clínica Vet Renomeada"
    assert result.status == ClinicStatus.SPECIAL.value
    assert result.row_version == created.row_version + 1
    assert audit.entries[-1].action == "clinics.updated"


def test_update_clinic_not_found() -> None:
    clinics = FakeClinicRepository()
    audit = FakeAuditLogWriter()
    use_case = UpdateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW))

    with pytest.raises(NotFoundError):
        use_case.execute(
            UpdateClinicCommand(
                actor=_actor(permissions=frozenset({"clinics.manage"})),
                clinic_id=uuid4(),
                name="Fantasma",
                tax_id=None,
                phone=None,
                email=None,
                status=ClinicStatus.ACTIVE.value,
                address_zip_code=None,
                address_street=None,
                address_number=None,
                address_neighborhood=None,
                address_city=None,
                address_state=None,
                address_complement=None,
                notes=None,
                expected_row_version=1,
            )
        )


def test_deactivate_clinic_soft_deletes_and_preserves_record() -> None:
    clinics = FakeClinicRepository()
    audit = FakeAuditLogWriter()
    created = CreateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW)).execute(
        _create_command()
    )

    use_case = DeactivateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW))
    result = use_case.execute(
        DeactivateClinicCommand(
            actor=_actor(permissions=frozenset({"clinics.manage"})), clinic_id=created.id
        )
    )

    assert result.status == ClinicStatus.INACTIVE.value
    stored = clinics.get_by_id(created.id)
    assert stored is not None
    assert stored.name == created.name
    assert audit.entries[-1].action == "clinics.deactivated"


def test_list_clinics_requires_permission() -> None:
    clinics = FakeClinicRepository()
    use_case = ListClinicsUseCase(clinics=clinics)

    with pytest.raises(ForbiddenError):
        use_case.execute(
            ListClinicsQuery(actor=_actor(permissions=frozenset()), page=1, page_size=20)
        )


def test_list_clinics_filters_by_search() -> None:
    clinics = FakeClinicRepository()
    audit = FakeAuditLogWriter()
    CreateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW)).execute(
        _create_command(name="Schweitzer", tax_id="78977352000199")
    )
    CreateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW)).execute(
        _create_command(name="Bicho Urbano", tax_id="21804204000155")
    )

    use_case = ListClinicsUseCase(clinics=clinics)
    result = use_case.execute(
        ListClinicsQuery(
            actor=_actor(permissions=frozenset({"clinics.read"})),
            page=1,
            page_size=20,
            search="bicho",
        )
    )

    assert result.total == 1
    assert result.items[0].name == "Bicho Urbano"


def test_get_clinic_not_found() -> None:
    clinics = FakeClinicRepository()
    use_case = GetClinicUseCase(clinics=clinics)

    with pytest.raises(NotFoundError):
        use_case.execute(
            GetClinicQuery(actor=_actor(permissions=frozenset({"clinics.read"})), clinic_id=uuid4())
        )
