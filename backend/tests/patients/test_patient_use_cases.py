from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.application.create_patient import (
    CreatePatientCommand,
    CreatePatientUseCase,
)
from app.modules.patients.application.deactivate_patient import (
    DeactivatePatientCommand,
    DeactivatePatientUseCase,
)
from app.modules.patients.application.get_patient import GetPatientQuery, GetPatientUseCase
from app.modules.patients.application.list_patients import (
    ListPatientsQuery,
    ListPatientsUseCase,
)
from app.modules.patients.application.update_patient import (
    UpdatePatientCommand,
    UpdatePatientUseCase,
)
from app.modules.patients.domain.entities import PatientStatus, Species
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError
from tests.patients.fakes import (
    FakeAuditLogWriter,
    FakeClock,
    FakePatientRepository,
    FakeSpeciesRepository,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_SPECIES_ID = uuid4()


def _actor(*, permissions: frozenset[str]) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        user_id=uuid4(),
        email="user@vertere.local",
        full_name="User",
        role_id=uuid4(),
        role_name="RECEPTION",
        permissions=permissions,
    )


def _species_repo() -> FakeSpeciesRepository:
    return FakeSpeciesRepository([Species(id=_SPECIES_ID, name="Cão", created_at=_NOW)])


def _create_command(**overrides: object) -> CreatePatientCommand:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"patients.manage"})),
        "name": "Rex",
        "species_id": _SPECIES_ID,
        "sex": "MALE",
        "breed": "SRD",
        "age_description": "2 anos",
        "owner_name": "Maria Souza",
        "owner_phone": "(47) 99999-0000",
        "owner_document": None,
        "notes": None,
    }
    defaults.update(overrides)
    return CreatePatientCommand(**defaults)  # type: ignore[arg-type]


def test_create_patient_succeeds_and_audits() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    use_case = CreatePatientUseCase(
        patients=patients, species=_species_repo(), audit=audit, clock=FakeClock(_NOW)
    )

    result = use_case.execute(_create_command())

    assert result.name == "Rex"
    assert result.owner_name == "Maria Souza"
    assert result.status == PatientStatus.ACTIVE.value
    assert patients.get_by_id(result.id) is not None
    assert audit.entries[0].action == "patients.created"


def test_create_patient_without_permission_is_forbidden() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    use_case = CreatePatientUseCase(
        patients=patients, species=_species_repo(), audit=audit, clock=FakeClock(_NOW)
    )

    with pytest.raises(ForbiddenError):
        use_case.execute(_create_command(actor=_actor(permissions=frozenset())))


def test_create_patient_with_unknown_species_not_found() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    use_case = CreatePatientUseCase(
        patients=patients, species=_species_repo(), audit=audit, clock=FakeClock(_NOW)
    )

    with pytest.raises(NotFoundError):
        use_case.execute(_create_command(species_id=uuid4()))


def test_create_patient_allows_duplicate_owner_and_name() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    use_case = CreatePatientUseCase(
        patients=patients, species=_species_repo(), audit=audit, clock=FakeClock(_NOW)
    )
    use_case.execute(_create_command())

    result = use_case.execute(_create_command())

    assert patients.list_page(page=1, page_size=20, status=None, search=None)[1] == 2
    assert result.owner_name == "Maria Souza"


def test_update_patient_with_stale_row_version_conflicts() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    created = CreatePatientUseCase(
        patients=patients, species=_species_repo(), audit=audit, clock=FakeClock(_NOW)
    ).execute(_create_command())

    use_case = UpdatePatientUseCase(
        patients=patients, species=_species_repo(), audit=audit, clock=FakeClock(_NOW)
    )
    with pytest.raises(ConflictError):
        use_case.execute(
            UpdatePatientCommand(
                actor=_actor(permissions=frozenset({"patients.manage"})),
                patient_id=created.id,
                name="Rex Renomeado",
                species_id=created.species_id,
                sex=created.sex,
                breed=created.breed,
                age_description=created.age_description,
                owner_name=created.owner_name,
                owner_phone=created.owner_phone,
                owner_document=created.owner_document,
                status=PatientStatus.ACTIVE.value,
                notes=None,
                expected_row_version=created.row_version + 1,
            )
        )


def test_update_patient_succeeds_and_bumps_row_version() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    created = CreatePatientUseCase(
        patients=patients, species=_species_repo(), audit=audit, clock=FakeClock(_NOW)
    ).execute(_create_command())

    use_case = UpdatePatientUseCase(
        patients=patients, species=_species_repo(), audit=audit, clock=FakeClock(_NOW)
    )
    result = use_case.execute(
        UpdatePatientCommand(
            actor=_actor(permissions=frozenset({"patients.manage"})),
            patient_id=created.id,
            name="Rex Renomeado",
            species_id=created.species_id,
            sex=created.sex,
            breed=created.breed,
            age_description=created.age_description,
            owner_name=created.owner_name,
            owner_phone=created.owner_phone,
            owner_document=created.owner_document,
            status=PatientStatus.ACTIVE.value,
            notes=None,
            expected_row_version=created.row_version,
        )
    )

    assert result.name == "Rex Renomeado"
    assert result.row_version == created.row_version + 1
    assert audit.entries[-1].action == "patients.updated"


def test_update_patient_not_found() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    use_case = UpdatePatientUseCase(
        patients=patients, species=_species_repo(), audit=audit, clock=FakeClock(_NOW)
    )

    with pytest.raises(NotFoundError):
        use_case.execute(
            UpdatePatientCommand(
                actor=_actor(permissions=frozenset({"patients.manage"})),
                patient_id=uuid4(),
                name="Fantasma",
                species_id=_SPECIES_ID,
                sex="MALE",
                breed=None,
                age_description=None,
                owner_name="Ninguém",
                owner_phone=None,
                owner_document=None,
                status=PatientStatus.ACTIVE.value,
                notes=None,
                expected_row_version=1,
            )
        )


def test_update_patient_with_unknown_species_not_found() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    created = CreatePatientUseCase(
        patients=patients, species=_species_repo(), audit=audit, clock=FakeClock(_NOW)
    ).execute(_create_command())

    use_case = UpdatePatientUseCase(
        patients=patients, species=_species_repo(), audit=audit, clock=FakeClock(_NOW)
    )
    with pytest.raises(NotFoundError):
        use_case.execute(
            UpdatePatientCommand(
                actor=_actor(permissions=frozenset({"patients.manage"})),
                patient_id=created.id,
                name=created.name,
                species_id=uuid4(),
                sex=created.sex,
                breed=created.breed,
                age_description=created.age_description,
                owner_name=created.owner_name,
                owner_phone=created.owner_phone,
                owner_document=created.owner_document,
                status=PatientStatus.ACTIVE.value,
                notes=None,
                expected_row_version=created.row_version,
            )
        )


def test_deactivate_patient_soft_deletes_and_preserves_record() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    created = CreatePatientUseCase(
        patients=patients, species=_species_repo(), audit=audit, clock=FakeClock(_NOW)
    ).execute(_create_command())

    use_case = DeactivatePatientUseCase(patients=patients, audit=audit, clock=FakeClock(_NOW))
    result = use_case.execute(
        DeactivatePatientCommand(
            actor=_actor(permissions=frozenset({"patients.manage"})), patient_id=created.id
        )
    )

    assert result.status == PatientStatus.INACTIVE.value
    stored = patients.get_by_id(created.id)
    assert stored is not None
    assert stored.name == created.name
    assert audit.entries[-1].action == "patients.deactivated"


def test_list_patients_requires_permission() -> None:
    patients = FakePatientRepository()
    use_case = ListPatientsUseCase(patients=patients)

    with pytest.raises(ForbiddenError):
        use_case.execute(
            ListPatientsQuery(actor=_actor(permissions=frozenset()), page=1, page_size=20)
        )


def test_list_patients_filters_by_search() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    CreatePatientUseCase(
        patients=patients, species=_species_repo(), audit=audit, clock=FakeClock(_NOW)
    ).execute(_create_command(name="Rex", owner_name="Maria Souza"))
    CreatePatientUseCase(
        patients=patients, species=_species_repo(), audit=audit, clock=FakeClock(_NOW)
    ).execute(_create_command(name="Bidu", owner_name="Joana Lima"))

    use_case = ListPatientsUseCase(patients=patients)
    result = use_case.execute(
        ListPatientsQuery(
            actor=_actor(permissions=frozenset({"patients.read"})),
            page=1,
            page_size=20,
            search="joana",
        )
    )

    assert result.total == 1
    assert result.items[0].name == "Bidu"


def test_get_patient_not_found() -> None:
    patients = FakePatientRepository()
    use_case = GetPatientUseCase(patients=patients)

    with pytest.raises(NotFoundError):
        use_case.execute(
            GetPatientQuery(
                actor=_actor(permissions=frozenset({"patients.read"})), patient_id=uuid4()
            )
        )


def test_clinic_actor_cannot_list_or_read_another_clinics_patient() -> None:
    own_clinic_id = uuid4()
    other_clinic_id = uuid4()
    patients = FakePatientRepository()
    created = CreatePatientUseCase(
        patients=patients,
        species=_species_repo(),
        audit=FakeAuditLogWriter(),
        clock=FakeClock(_NOW),
    ).execute(_create_command())
    stored = patients.get_by_id(created.id)
    assert stored is not None
    stored.clinic_id = other_clinic_id
    actor = AuthenticatedUserDTO(
        user_id=uuid4(),
        email="clinic@vertere.local",
        full_name="Clinic User",
        role_id=uuid4(),
        role_name="CLINIC_STAFF",
        role_scope="CLINIC",
        permissions=frozenset({"patients.read"}),
        clinic_ids=frozenset({own_clinic_id}),
    )

    page = ListPatientsUseCase(patients=patients).execute(
        ListPatientsQuery(actor=actor, page=1, page_size=20)
    )
    assert page.total == 0
    with pytest.raises(NotFoundError):
        GetPatientUseCase(patients=patients).execute(
            GetPatientQuery(actor=actor, patient_id=created.id)
        )
