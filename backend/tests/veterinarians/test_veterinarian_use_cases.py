from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.clinics.domain.entities import Clinic, ClinicStatus
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.veterinarians.application.create_veterinarian import (
    CreateVeterinarianCommand,
    CreateVeterinarianUseCase,
)
from app.modules.veterinarians.application.deactivate_veterinarian import (
    DeactivateVeterinarianCommand,
    DeactivateVeterinarianUseCase,
)
from app.modules.veterinarians.application.dtos import VeterinarianDTO
from app.modules.veterinarians.application.get_veterinarian import (
    GetVeterinarianQuery,
    GetVeterinarianUseCase,
)
from app.modules.veterinarians.application.list_veterinarians import (
    ListVeterinariansQuery,
    ListVeterinariansUseCase,
)
from app.modules.veterinarians.application.update_veterinarian import (
    UpdateVeterinarianCommand,
    UpdateVeterinarianUseCase,
)
from app.modules.veterinarians.domain.entities import VeterinarianStatus
from app.modules.veterinarians.domain.errors import DuplicateCrmvError
from app.shared.domain.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from tests.veterinarian_clinics.fakes import (
    FakeClinicRepository,
    FakeVeterinarianClinicLinkRepository,
)
from tests.veterinarians.fakes import FakeAuditLogWriter, FakeClock, FakeVeterinarianRepository

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


def _clinic(*, name: str = "Schweitzer") -> Clinic:
    return Clinic(
        id=uuid4(), name=name, status=ClinicStatus.ACTIVE, created_at=_NOW, updated_at=_NOW
    )


def _create_command(**overrides: object) -> CreateVeterinarianCommand:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"veterinarians.manage"})),
        "name": "Dra. Fabianna Garcia",
        "crmv": "CRMV-SC 04567",
        "phone": "(47) 99999-0000",
        "email": "fabianna@vertere.local",
        # Autonomous by default so most tests don't need to think about the
        # clinic requirement — tests that care about it override explicitly.
        "is_autonomous": True,
        "notes": None,
    }
    defaults.update(overrides)
    return CreateVeterinarianCommand(**defaults)  # type: ignore[arg-type]


def _use_case(
    *,
    veterinarians: FakeVeterinarianRepository,
    audit: FakeAuditLogWriter,
    clinics: FakeClinicRepository | None = None,
    links: FakeVeterinarianClinicLinkRepository | None = None,
) -> CreateVeterinarianUseCase:
    return CreateVeterinarianUseCase(
        veterinarians=veterinarians,
        clinics=clinics or FakeClinicRepository(),
        links=links or FakeVeterinarianClinicLinkRepository(),
        audit=audit,
        clock=FakeClock(_NOW),
    )


def _update_command(created: VeterinarianDTO, **overrides: object) -> UpdateVeterinarianCommand:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"veterinarians.manage"})),
        "veterinarian_id": created.id,
        "name": "Dra. Fabianna Garcia Renomeada",
        "crmv": created.crmv,
        "phone": None,
        "email": None,
        "is_autonomous": True,
        "status": VeterinarianStatus.ACTIVE.value,
        "notes": None,
        "expected_row_version": created.row_version,
    }
    defaults.update(overrides)
    return UpdateVeterinarianCommand(**defaults)  # type: ignore[arg-type]


def _clinic_actor(
    *, clinic_ids: frozenset[UUID], permissions: frozenset[str]
) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        user_id=uuid4(),
        email="clinic@vertere.local",
        full_name="Clinic User",
        role_id=uuid4(),
        role_name="CLINIC_STAFF",
        role_scope="CLINIC",
        permissions=permissions,
        clinic_ids=clinic_ids,
    )


def _stored_veterinarian(
    veterinarians: FakeVeterinarianRepository, *, is_autonomous: bool, linked_to: set[UUID]
) -> UUID:
    created = _use_case(veterinarians=veterinarians, audit=FakeAuditLogWriter()).execute(
        _create_command(is_autonomous=True, crmv=f"CRMV-SC {uuid4().hex[:5]}")
    )
    stored = veterinarians.get_by_id(created.id)
    assert stored is not None
    stored.is_autonomous = is_autonomous
    veterinarians.linked_clinics[created.id] = linked_to
    return created.id


def test_create_veterinarian_enforces_permission_uniqueness_and_clinic_requirement() -> None:
    veterinarians = FakeVeterinarianRepository()
    audit = FakeAuditLogWriter()
    use_case = _use_case(veterinarians=veterinarians, audit=audit)

    with pytest.raises(ForbiddenError):
        use_case.execute(_create_command(actor=_actor(permissions=frozenset())))
    # Não autônomo exige ao menos uma clínica já na criação (ADR-003) e nada é gravado.
    with pytest.raises(ValidationError):
        use_case.execute(_create_command(is_autonomous=False, clinic_ids=()))
    assert veterinarians.get_by_crmv("CRMV-SC 04567") is None

    result = use_case.execute(_create_command(crmv="crmv-sc 04567"))
    assert result.name == "Dra. Fabianna Garcia"
    assert result.crmv == "CRMV-SC 04567"  # normalizado antes de gravar
    assert result.status == VeterinarianStatus.ACTIVE.value
    assert veterinarians.get_by_id(result.id) is not None
    assert audit.entries[0].action == "veterinarians.created"
    with pytest.raises(DuplicateCrmvError):  # a duplicidade vale após a normalização
        use_case.execute(_create_command(name="Outro Vet", crmv="  CRMV-SC   04567  "))


def test_create_veterinarian_links_clinics_and_validates_the_primary() -> None:
    veterinarians = FakeVeterinarianRepository()
    audit = FakeAuditLogWriter()
    clinics = FakeClinicRepository()
    links = FakeVeterinarianClinicLinkRepository()
    clinic_a = _clinic(name="Schweitzer")
    clinic_b = _clinic(name="Bicho Urbano")
    clinics.add(clinic_a)
    clinics.add(clinic_b)
    use_case = _use_case(veterinarians=veterinarians, audit=audit, clinics=clinics, links=links)

    with pytest.raises(NotFoundError):
        use_case.execute(_create_command(is_autonomous=False, clinic_ids=(uuid4(),)))
    with pytest.raises(ValidationError):
        use_case.execute(
            _create_command(
                is_autonomous=False, clinic_ids=(clinic_a.id,), primary_clinic_id=uuid4()
            )
        )

    single = use_case.execute(
        _create_command(crmv="CRMV-SC 00001", is_autonomous=False, clinic_ids=(clinic_a.id,))
    )
    [only_link] = links.list_by_veterinarian(single.id)
    assert (only_link.clinic_id, only_link.primary_clinic) == (clinic_a.id, True)
    assert audit.entries[-1].action == "veterinarian_clinics.linked"

    multiple = use_case.execute(
        _create_command(
            crmv="CRMV-SC 00002",
            is_autonomous=False,
            clinic_ids=(clinic_a.id, clinic_b.id),
            primary_clinic_id=clinic_b.id,
        )
    )
    linked = links.list_by_veterinarian(multiple.id)
    assert {link.clinic_id for link in linked} == {clinic_a.id, clinic_b.id}
    assert [link.clinic_id for link in linked if link.primary_clinic] == [clinic_b.id]


def test_veterinarian_update_and_deactivation_are_versioned_audited_and_preserve_history() -> None:
    veterinarians = FakeVeterinarianRepository()
    audit = FakeAuditLogWriter()
    created = _use_case(veterinarians=veterinarians, audit=audit).execute(_create_command())
    update = UpdateVeterinarianUseCase(
        veterinarians=veterinarians, audit=audit, clock=FakeClock(_NOW)
    )
    deactivate = DeactivateVeterinarianUseCase(
        veterinarians=veterinarians, audit=audit, clock=FakeClock(_NOW)
    )

    with pytest.raises(ConflictError):
        update.execute(_update_command(created, expected_row_version=created.row_version + 1))
    with pytest.raises(NotFoundError):
        update.execute(_update_command(created, veterinarian_id=uuid4()))
    updated = update.execute(_update_command(created))
    assert updated.name == "Dra. Fabianna Garcia Renomeada"
    assert updated.row_version == created.row_version + 1
    assert audit.entries[-1].action == "veterinarians.updated"

    result = deactivate.execute(
        DeactivateVeterinarianCommand(
            actor=_actor(permissions=frozenset({"veterinarians.manage"})),
            veterinarian_id=created.id,
        )
    )
    assert result.status == VeterinarianStatus.INACTIVE.value
    stored = veterinarians.get_by_id(created.id)
    assert stored is not None
    assert stored.name == "Dra. Fabianna Garcia Renomeada"  # inativar não apaga nem reescreve
    assert audit.entries[-1].action == "veterinarians.deactivated"


def test_list_and_get_veterinarians_check_permission_filters_and_missing_records() -> None:
    veterinarians = FakeVeterinarianRepository()
    audit = FakeAuditLogWriter()
    clinics = FakeClinicRepository()
    clinic = _clinic()
    clinics.add(clinic)
    _use_case(veterinarians=veterinarians, audit=audit, clinics=clinics).execute(
        _create_command(
            name="Schweitzer Vet",
            crmv="CRMV-SC 00001",
            is_autonomous=False,
            clinic_ids=(clinic.id,),
        )
    )
    _use_case(veterinarians=veterinarians, audit=audit).execute(
        _create_command(name="Bicho Urbano", crmv="CRMV-SC 00002", is_autonomous=True)
    )
    reader = _actor(permissions=frozenset({"veterinarians.read"}))
    list_use_case = ListVeterinariansUseCase(veterinarians=veterinarians)

    with pytest.raises(ForbiddenError):
        list_use_case.execute(
            ListVeterinariansQuery(actor=_actor(permissions=frozenset()), page=1, page_size=20)
        )
    result = list_use_case.execute(
        ListVeterinariansQuery(actor=reader, page=1, page_size=20, is_autonomous=True)
    )
    assert result.total == 1
    assert result.items[0].name == "Bicho Urbano"
    with pytest.raises(NotFoundError):
        GetVeterinarianUseCase(veterinarians=veterinarians).execute(
            GetVeterinarianQuery(actor=reader, veterinarian_id=uuid4())
        )


def test_clinic_actor_only_reaches_own_clinic_and_autonomous_veterinarians() -> None:
    veterinarians = FakeVeterinarianRepository()
    own_clinic_id, other_clinic_id = uuid4(), uuid4()
    foreign_id = _stored_veterinarian(
        veterinarians, is_autonomous=False, linked_to={other_clinic_id}
    )
    linked_id = _stored_veterinarian(veterinarians, is_autonomous=False, linked_to={own_clinic_id})
    autonomous_id = _stored_veterinarian(veterinarians, is_autonomous=True, linked_to=set())
    actor = _clinic_actor(
        clinic_ids=frozenset({own_clinic_id}),
        permissions=frozenset({"veterinarians.read", "veterinarians.manage"}),
    )
    get = GetVeterinarianUseCase(veterinarians=veterinarians)

    # Visíveis: o vinculado à clínica do ator e o autônomo.
    for visible_id in (linked_id, autonomous_id):
        assert get.execute(GetVeterinarianQuery(actor=actor, veterinarian_id=visible_id)).id == (
            visible_id
        )

    # Veterinário de outra clínica: leitura, edição e inativação respondem "não encontrado".
    foreign = veterinarians.get_by_id(foreign_id)
    assert foreign is not None
    with pytest.raises(NotFoundError):
        get.execute(GetVeterinarianQuery(actor=actor, veterinarian_id=foreign_id))
    with pytest.raises(NotFoundError):
        UpdateVeterinarianUseCase(
            veterinarians=veterinarians, audit=FakeAuditLogWriter(), clock=FakeClock(_NOW)
        ).execute(
            UpdateVeterinarianCommand(
                actor=actor,
                veterinarian_id=foreign_id,
                name="Alterado",
                crmv="CRMV-SC 99999",
                phone=None,
                email=None,
                is_autonomous=False,
                status="ACTIVE",
                notes=None,
                expected_row_version=foreign.row_version,
            )
        )
    with pytest.raises(NotFoundError):
        DeactivateVeterinarianUseCase(
            veterinarians=veterinarians, audit=FakeAuditLogWriter(), clock=FakeClock(_NOW)
        ).execute(DeactivateVeterinarianCommand(actor=actor, veterinarian_id=foreign_id))
    assert foreign.status == VeterinarianStatus.ACTIVE
    assert foreign.name != "Alterado"
