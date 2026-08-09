from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

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


def test_create_veterinarian_succeeds_and_audits() -> None:
    veterinarians = FakeVeterinarianRepository()
    audit = FakeAuditLogWriter()
    use_case = _use_case(veterinarians=veterinarians, audit=audit)

    result = use_case.execute(_create_command())

    assert result.name == "Dra. Fabianna Garcia"
    assert result.crmv == "CRMV-SC 04567"
    assert result.status == VeterinarianStatus.ACTIVE.value
    assert veterinarians.get_by_id(result.id) is not None
    assert audit.entries[0].action == "veterinarians.created"


def test_create_veterinarian_without_permission_is_forbidden() -> None:
    veterinarians = FakeVeterinarianRepository()
    audit = FakeAuditLogWriter()
    use_case = _use_case(veterinarians=veterinarians, audit=audit)

    with pytest.raises(ForbiddenError):
        use_case.execute(_create_command(actor=_actor(permissions=frozenset())))


def test_create_veterinarian_with_duplicate_crmv_conflicts() -> None:
    veterinarians = FakeVeterinarianRepository()
    audit = FakeAuditLogWriter()
    use_case = _use_case(veterinarians=veterinarians, audit=audit)
    use_case.execute(_create_command())

    with pytest.raises(DuplicateCrmvError):
        use_case.execute(_create_command(name="Outro Vet"))


def test_create_veterinarian_normalizes_crmv_before_duplicate_check() -> None:
    veterinarians = FakeVeterinarianRepository()
    audit = FakeAuditLogWriter()
    use_case = _use_case(veterinarians=veterinarians, audit=audit)
    use_case.execute(_create_command(crmv="crmv-sc 04567"))

    with pytest.raises(DuplicateCrmvError):
        use_case.execute(_create_command(name="Outro Vet", crmv="  CRMV-SC   04567  "))


def test_create_non_autonomous_veterinarian_without_clinic_is_invalid() -> None:
    """Closes the gap documented in ADR-003: a non-autonomous veterinarian
    must have at least one clinic at creation time, not only checked later
    on unlink."""
    veterinarians = FakeVeterinarianRepository()
    audit = FakeAuditLogWriter()
    use_case = _use_case(veterinarians=veterinarians, audit=audit)

    with pytest.raises(ValidationError):
        use_case.execute(_create_command(is_autonomous=False, clinic_ids=()))

    assert veterinarians.get_by_crmv("CRMV-SC 04567") is None


def test_create_non_autonomous_veterinarian_with_clinic_links_it_as_primary() -> None:
    veterinarians = FakeVeterinarianRepository()
    audit = FakeAuditLogWriter()
    clinics = FakeClinicRepository()
    links = FakeVeterinarianClinicLinkRepository()
    clinic = _clinic()
    clinics.add(clinic)
    use_case = _use_case(veterinarians=veterinarians, audit=audit, clinics=clinics, links=links)

    result = use_case.execute(_create_command(is_autonomous=False, clinic_ids=(clinic.id,)))

    linked = links.list_by_veterinarian(result.id)
    assert len(linked) == 1
    assert linked[0].clinic_id == clinic.id
    assert linked[0].primary_clinic is True
    assert audit.entries[-1].action == "veterinarian_clinics.linked"


def test_create_veterinarian_with_unknown_clinic_not_found() -> None:
    veterinarians = FakeVeterinarianRepository()
    audit = FakeAuditLogWriter()
    use_case = _use_case(veterinarians=veterinarians, audit=audit)

    with pytest.raises(NotFoundError):
        use_case.execute(_create_command(is_autonomous=False, clinic_ids=(uuid4(),)))


def test_create_veterinarian_with_primary_not_in_clinic_ids_is_invalid() -> None:
    veterinarians = FakeVeterinarianRepository()
    audit = FakeAuditLogWriter()
    clinics = FakeClinicRepository()
    clinic = _clinic()
    clinics.add(clinic)
    use_case = _use_case(veterinarians=veterinarians, audit=audit, clinics=clinics)

    with pytest.raises(ValidationError):
        use_case.execute(
            _create_command(is_autonomous=False, clinic_ids=(clinic.id,), primary_clinic_id=uuid4())
        )


def test_create_veterinarian_links_multiple_clinics_with_explicit_primary() -> None:
    veterinarians = FakeVeterinarianRepository()
    audit = FakeAuditLogWriter()
    clinics = FakeClinicRepository()
    links = FakeVeterinarianClinicLinkRepository()
    clinic_a = _clinic(name="Schweitzer")
    clinic_b = _clinic(name="Bicho Urbano")
    clinics.add(clinic_a)
    clinics.add(clinic_b)
    use_case = _use_case(veterinarians=veterinarians, audit=audit, clinics=clinics, links=links)

    result = use_case.execute(
        _create_command(
            is_autonomous=False,
            clinic_ids=(clinic_a.id, clinic_b.id),
            primary_clinic_id=clinic_b.id,
        )
    )

    linked = links.list_by_veterinarian(result.id)
    assert len(linked) == 2
    primaries = [link for link in linked if link.primary_clinic]
    assert len(primaries) == 1
    assert primaries[0].clinic_id == clinic_b.id


def test_update_veterinarian_with_stale_row_version_conflicts() -> None:
    veterinarians = FakeVeterinarianRepository()
    audit = FakeAuditLogWriter()
    created = _use_case(veterinarians=veterinarians, audit=audit).execute(_create_command())

    use_case = UpdateVeterinarianUseCase(
        veterinarians=veterinarians, audit=audit, clock=FakeClock(_NOW)
    )
    with pytest.raises(ConflictError):
        use_case.execute(
            UpdateVeterinarianCommand(
                actor=_actor(permissions=frozenset({"veterinarians.manage"})),
                veterinarian_id=created.id,
                name="Dra. Fabianna Garcia Renomeada",
                crmv=created.crmv,
                phone=None,
                email=None,
                is_autonomous=False,
                status=VeterinarianStatus.ACTIVE.value,
                notes=None,
                expected_row_version=created.row_version + 1,
            )
        )


def test_update_veterinarian_succeeds_and_bumps_row_version() -> None:
    veterinarians = FakeVeterinarianRepository()
    audit = FakeAuditLogWriter()
    created = _use_case(veterinarians=veterinarians, audit=audit).execute(_create_command())

    use_case = UpdateVeterinarianUseCase(
        veterinarians=veterinarians, audit=audit, clock=FakeClock(_NOW)
    )
    result = use_case.execute(
        UpdateVeterinarianCommand(
            actor=_actor(permissions=frozenset({"veterinarians.manage"})),
            veterinarian_id=created.id,
            name="Dra. Fabianna Garcia Renomeada",
            crmv=created.crmv,
            phone=None,
            email=None,
            is_autonomous=True,
            status=VeterinarianStatus.ACTIVE.value,
            notes=None,
            expected_row_version=created.row_version,
        )
    )

    assert result.name == "Dra. Fabianna Garcia Renomeada"
    assert result.is_autonomous is True
    assert result.row_version == created.row_version + 1
    assert audit.entries[-1].action == "veterinarians.updated"


def test_update_veterinarian_not_found() -> None:
    veterinarians = FakeVeterinarianRepository()
    audit = FakeAuditLogWriter()
    use_case = UpdateVeterinarianUseCase(
        veterinarians=veterinarians, audit=audit, clock=FakeClock(_NOW)
    )

    with pytest.raises(NotFoundError):
        use_case.execute(
            UpdateVeterinarianCommand(
                actor=_actor(permissions=frozenset({"veterinarians.manage"})),
                veterinarian_id=uuid4(),
                name="Fantasma",
                crmv="CRMV-SC 99999",
                phone=None,
                email=None,
                is_autonomous=False,
                status=VeterinarianStatus.ACTIVE.value,
                notes=None,
                expected_row_version=1,
            )
        )


def test_deactivate_veterinarian_soft_deletes_and_preserves_record() -> None:
    veterinarians = FakeVeterinarianRepository()
    audit = FakeAuditLogWriter()
    created = _use_case(veterinarians=veterinarians, audit=audit).execute(_create_command())

    use_case = DeactivateVeterinarianUseCase(
        veterinarians=veterinarians, audit=audit, clock=FakeClock(_NOW)
    )
    result = use_case.execute(
        DeactivateVeterinarianCommand(
            actor=_actor(permissions=frozenset({"veterinarians.manage"})),
            veterinarian_id=created.id,
        )
    )

    assert result.status == VeterinarianStatus.INACTIVE.value
    stored = veterinarians.get_by_id(created.id)
    assert stored is not None
    assert stored.name == created.name
    assert audit.entries[-1].action == "veterinarians.deactivated"


def test_list_veterinarians_requires_permission() -> None:
    veterinarians = FakeVeterinarianRepository()
    use_case = ListVeterinariansUseCase(veterinarians=veterinarians)

    with pytest.raises(ForbiddenError):
        use_case.execute(
            ListVeterinariansQuery(actor=_actor(permissions=frozenset()), page=1, page_size=20)
        )


def test_list_veterinarians_filters_by_search_and_autonomy() -> None:
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

    use_case = ListVeterinariansUseCase(veterinarians=veterinarians)
    result = use_case.execute(
        ListVeterinariansQuery(
            actor=_actor(permissions=frozenset({"veterinarians.read"})),
            page=1,
            page_size=20,
            is_autonomous=True,
        )
    )

    assert result.total == 1
    assert result.items[0].name == "Bicho Urbano"


def test_get_veterinarian_not_found() -> None:
    veterinarians = FakeVeterinarianRepository()
    use_case = GetVeterinarianUseCase(veterinarians=veterinarians)

    with pytest.raises(NotFoundError):
        use_case.execute(
            GetVeterinarianQuery(
                actor=_actor(permissions=frozenset({"veterinarians.read"})), veterinarian_id=uuid4()
            )
        )
