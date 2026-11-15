from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.audit.domain.entities import ActorScope
from app.modules.clinics.application.create_clinic import CreateClinicCommand, CreateClinicUseCase
from app.modules.clinics.application.deactivate_clinic import (
    DeactivateClinicCommand,
    DeactivateClinicUseCase,
)
from app.modules.clinics.application.dtos import ClinicDTO
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
        user_id=uuid4(),
        email="user@vertere.local",
        full_name="User",
        role_id=uuid4(),
        role_name="RECEPTION",
        permissions=permissions,
    )


def _clinic_actor(*, clinic_ids: frozenset[UUID]) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        user_id=uuid4(),
        email="clinic@vertere.local",
        full_name="Clinic User",
        role_id=uuid4(),
        role_name="CLINIC_STAFF",
        role_scope="CLINIC",
        permissions=frozenset({"clinics.read", "clinics.manage"}),
        clinic_ids=clinic_ids,
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


def _update_command(created: ClinicDTO, **overrides: object) -> UpdateClinicCommand:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"clinics.manage"})),
        "clinic_id": created.id,
        "name": "Clínica Vet Renomeada",
        "tax_id": created.tax_id,
        "phone": None,
        "email": None,
        "status": ClinicStatus.ACTIVE.value,
        "address_zip_code": None,
        "address_street": None,
        "address_number": None,
        "address_neighborhood": None,
        "address_city": None,
        "address_state": None,
        "address_complement": None,
        "notes": None,
        "expected_row_version": created.row_version,
    }
    defaults.update(overrides)
    return UpdateClinicCommand(**defaults)  # type: ignore[arg-type]


def test_clinic_lifecycle_audits_versions_and_rejects_invalid_changes() -> None:
    clinics = FakeClinicRepository()
    audit = FakeAuditLogWriter()
    create = CreateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW))
    update = UpdateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW))
    deactivate = DeactivateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW))

    created = create.execute(_create_command())
    assert created.name == "Clínica Vet"
    assert created.status == ClinicStatus.ACTIVE.value
    with pytest.raises(DuplicateTaxIdError):
        create.execute(_create_command(name="Outra Clínica"))

    with pytest.raises(ConflictError):
        update.execute(_update_command(created, expected_row_version=created.row_version + 1))
    with pytest.raises(NotFoundError):
        update.execute(_update_command(created, clinic_id=uuid4()))
    updated = update.execute(_update_command(created, status=ClinicStatus.SPECIAL.value))
    assert (updated.name, updated.status) == ("Clínica Vet Renomeada", ClinicStatus.SPECIAL.value)
    assert updated.row_version == created.row_version + 1

    deactivated = deactivate.execute(
        DeactivateClinicCommand(
            actor=_clinic_actor(clinic_ids=frozenset({created.id})), clinic_id=created.id
        )
    )
    assert deactivated.status == ClinicStatus.INACTIVE.value
    stored = clinics.get_by_id(created.id)
    assert stored is not None
    assert stored.name == "Clínica Vet Renomeada"

    # A auditoria registra o escopo real de quem agiu, não um valor fixo.
    assert [(entry.action, entry.actor_scope) for entry in audit.entries] == [
        ("clinics.created", ActorScope.LAB),
        ("clinics.updated", ActorScope.LAB),
        ("clinics.deactivated", ActorScope.CLINIC),
    ]


def test_clinic_permissions_and_tenant_scope() -> None:
    clinics = FakeClinicRepository()
    audit = FakeAuditLogWriter()
    create = CreateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW))
    first = create.execute(_create_command(tax_id="78977352000199"))
    second = create.execute(_create_command(name="Outra", tax_id="11222333000181"))
    nobody = _actor(permissions=frozenset())
    clinic_actor = _clinic_actor(clinic_ids=frozenset({first.id}))

    with pytest.raises(ForbiddenError):
        create.execute(_create_command(actor=nobody))
    with pytest.raises(ForbiddenError):  # ator de clínica nunca cria clínica
        create.execute(_create_command(actor=_clinic_actor(clinic_ids=frozenset())))
    with pytest.raises(ForbiddenError):
        ListClinicsUseCase(clinics=clinics).execute(
            ListClinicsQuery(actor=nobody, page=1, page_size=20)
        )

    page = ListClinicsUseCase(clinics=clinics).execute(
        ListClinicsQuery(actor=clinic_actor, page=1, page_size=20)
    )
    assert [item.id for item in page.items] == [first.id]
    with pytest.raises(NotFoundError):
        GetClinicUseCase(clinics=clinics).execute(
            GetClinicQuery(actor=clinic_actor, clinic_id=second.id)
        )


def test_list_and_get_clinics() -> None:
    clinics = FakeClinicRepository()
    audit = FakeAuditLogWriter()
    create = CreateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW))
    create.execute(_create_command(name="Schweitzer", tax_id="78977352000199"))
    create.execute(_create_command(name="Bicho Urbano", tax_id="21804204000155"))
    reader = _actor(permissions=frozenset({"clinics.read"}))

    result = ListClinicsUseCase(clinics=clinics).execute(
        ListClinicsQuery(actor=reader, page=1, page_size=20, search="bicho")
    )

    assert result.total == 1
    assert result.items[0].name == "Bicho Urbano"
    with pytest.raises(NotFoundError):
        GetClinicUseCase(clinics=clinics).execute(GetClinicQuery(actor=reader, clinic_id=uuid4()))


def test_clinic_scope_cannot_set_commercial_statuses_but_can_toggle_active() -> None:
    clinics = FakeClinicRepository()
    audit = FakeAuditLogWriter()
    create = CreateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW))
    update = UpdateClinicUseCase(clinics=clinics, audit=audit, clock=FakeClock(_NOW))
    created = create.execute(_create_command())
    own = _clinic_actor(clinic_ids=frozenset({created.id}))

    with pytest.raises(ForbiddenError):
        update.execute(_update_command(created, actor=own, status=ClinicStatus.SPECIAL.value))
    with pytest.raises(ForbiddenError):
        update.execute(_update_command(created, actor=own, status=ClinicStatus.DELINQUENT.value))
    inactive = update.execute(
        _update_command(created, actor=own, status=ClinicStatus.INACTIVE.value)
    )
    assert inactive.status == ClinicStatus.INACTIVE.value

    # Quem é do laboratório marca inadimplente; a clínica não consegue sair sozinha desse estado.
    delinquent = update.execute(_update_command(inactive, status=ClinicStatus.DELINQUENT.value))
    with pytest.raises(ForbiddenError):
        update.execute(_update_command(delinquent, actor=own, status=ClinicStatus.ACTIVE.value))
