from __future__ import annotations

from datetime import UTC, date, datetime
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
from app.modules.patients.application.dtos import PatientDTO
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
from app.shared.domain.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
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


def _create_use_case(
    patients: FakePatientRepository, audit: FakeAuditLogWriter
) -> CreatePatientUseCase:
    return CreatePatientUseCase(
        patients=patients, species=_species_repo(), audit=audit, clock=FakeClock(_NOW)
    )


def _update_command(created: PatientDTO, **overrides: object) -> UpdatePatientCommand:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"patients.manage"})),
        "patient_id": created.id,
        "name": "Rex Renomeado",
        "species_id": created.species_id,
        "sex": created.sex,
        "breed": created.breed,
        "age_description": created.age_description,
        "owner_name": created.owner_name,
        "owner_phone": created.owner_phone,
        "owner_document": created.owner_document,
        "status": PatientStatus.ACTIVE.value,
        "notes": None,
        "expected_row_version": created.row_version,
    }
    defaults.update(overrides)
    return UpdatePatientCommand(**defaults)  # type: ignore[arg-type]


def test_create_patient_audits_and_validates_permission_and_species() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    use_case = _create_use_case(patients, audit)

    with pytest.raises(ForbiddenError):
        use_case.execute(_create_command(actor=_actor(permissions=frozenset())))
    with pytest.raises(NotFoundError):
        use_case.execute(_create_command(species_id=uuid4()))
    assert patients.list_page(page=1, page_size=20, status=None, search=None)[1] == 0

    result = use_case.execute(_create_command())
    assert (result.name, result.owner_name) == ("Rex", "Maria Souza")
    assert result.status == PatientStatus.ACTIVE.value
    assert patients.get_by_id(result.id) is not None
    assert audit.entries[0].action == "patients.created"

    # Mesmo tutor e mesmo nome não são duplicidade: o cadastro é permitido.
    use_case.execute(_create_command())
    assert patients.list_page(page=1, page_size=20, status=None, search=None)[1] == 2


def test_patient_update_and_deactivation_are_versioned_audited_and_preserve_history() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    created = _create_use_case(patients, audit).execute(_create_command())
    update = UpdatePatientUseCase(
        patients=patients, species=_species_repo(), audit=audit, clock=FakeClock(_NOW)
    )

    with pytest.raises(ConflictError):
        update.execute(_update_command(created, expected_row_version=created.row_version + 1))
    with pytest.raises(NotFoundError):
        update.execute(_update_command(created, patient_id=uuid4()))
    with pytest.raises(NotFoundError):
        update.execute(_update_command(created, species_id=uuid4()))
    updated = update.execute(_update_command(created))
    assert updated.name == "Rex Renomeado"
    assert updated.row_version == created.row_version + 1
    assert audit.entries[-1].action == "patients.updated"

    result = DeactivatePatientUseCase(
        patients=patients, audit=audit, clock=FakeClock(_NOW)
    ).execute(
        DeactivatePatientCommand(
            actor=_actor(permissions=frozenset({"patients.manage"})), patient_id=created.id
        )
    )
    assert result.status == PatientStatus.INACTIVE.value
    stored = patients.get_by_id(created.id)
    assert stored is not None
    assert stored.name == "Rex Renomeado"  # inativar não apaga nem reescreve
    assert audit.entries[-1].action == "patients.deactivated"


def test_list_and_get_patients_check_permission_search_missing_and_tenant_scope() -> None:
    patients = FakePatientRepository()
    create = _create_use_case(patients, FakeAuditLogWriter())
    create.execute(_create_command(name="Rex", owner_name="Maria Souza"))
    bidu = create.execute(_create_command(name="Bidu", owner_name="Joana Lima"))
    reader = _actor(permissions=frozenset({"patients.read"}))
    list_use_case = ListPatientsUseCase(patients=patients)
    get_use_case = GetPatientUseCase(patients=patients)

    with pytest.raises(ForbiddenError):
        list_use_case.execute(
            ListPatientsQuery(actor=_actor(permissions=frozenset()), page=1, page_size=20)
        )
    found = list_use_case.execute(
        ListPatientsQuery(actor=reader, page=1, page_size=20, search="joana")
    )
    assert [item.name for item in found.items] == ["Bidu"]
    with pytest.raises(NotFoundError):
        get_use_case.execute(GetPatientQuery(actor=reader, patient_id=uuid4()))

    # Ator de clínica não lista nem lê paciente de outra clínica.
    stored = patients.get_by_id(bidu.id)
    assert stored is not None
    stored.clinic_id = uuid4()
    clinic_actor = AuthenticatedUserDTO(
        user_id=uuid4(),
        email="clinic@vertere.local",
        full_name="Clinic User",
        role_id=uuid4(),
        role_name="CLINIC_STAFF",
        role_scope="CLINIC",
        permissions=frozenset({"patients.read"}),
        clinic_ids=frozenset({uuid4()}),
    )
    assert (
        list_use_case.execute(ListPatientsQuery(actor=clinic_actor, page=1, page_size=20)).total
        == 0
    )
    with pytest.raises(NotFoundError):
        get_use_case.execute(GetPatientQuery(actor=clinic_actor, patient_id=bidu.id))


def test_structured_age_is_stored_with_recorded_date_and_derives_the_description() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    use_case = _create_use_case(patients, audit)

    created = use_case.execute(
        _create_command(age_value=8, age_unit="MONTHS", age_description="texto antigo")
    )
    assert (created.age_value, created.age_unit) == (8, "MONTHS")
    assert created.age_recorded_on == _NOW.date()
    assert created.age_description == "8 meses"

    # Só o valor, ou só a unidade, é erro de validação (nunca grava meia idade).
    with pytest.raises(ValidationError):
        use_case.execute(_create_command(age_value=3, age_unit=None))
    with pytest.raises(ValidationError):
        use_case.execute(_create_command(age_value=3, age_unit="WEEKS"))

    # Sem idade estruturada, o texto livre legado continua valendo.
    legacy = use_case.execute(_create_command())
    assert (legacy.age_value, legacy.age_unit, legacy.age_recorded_on) == (None, None, None)
    assert legacy.age_description == "2 anos"


def test_update_keeps_the_recorded_date_unless_the_age_changes() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    created = _create_use_case(patients, audit).execute(
        _create_command(age_value=2, age_unit="YEARS")
    )
    later = FakeClock(datetime(2026, 6, 1, tzinfo=UTC))
    update = UpdatePatientUseCase(
        patients=patients, species=_species_repo(), audit=audit, clock=later
    )

    same_age = update.execute(
        _update_command(created, age_value=2, age_unit="YEARS", age_description=None)
    )
    assert same_age.age_recorded_on == _NOW.date()

    older = update.execute(
        _update_command(same_age, age_value=3, age_unit="YEARS", age_description=None)
    )
    assert (older.age_value, older.age_recorded_on) == (3, date(2026, 6, 1))
    assert older.age_description == "3 anos"

    cleared = update.execute(_update_command(older, age_description="adulto"))
    assert (cleared.age_value, cleared.age_unit, cleared.age_recorded_on) == (None, None, None)
    assert cleared.age_description == "adulto"
