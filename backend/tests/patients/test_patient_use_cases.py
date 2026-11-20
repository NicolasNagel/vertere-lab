from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.clinics.domain.entities import Clinic
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
from app.modules.patients.application.reactivate_patient import (
    ReactivatePatientCommand,
    ReactivatePatientUseCase,
)
from app.modules.patients.application.summarize_patients import (
    SummarizePatientsQuery,
    SummarizePatientsUseCase,
)
from app.modules.patients.application.update_patient import (
    UpdatePatientCommand,
    UpdatePatientUseCase,
)
from app.modules.patients.domain.entities import PatientStatus, Species
from app.shared.domain.errors import (
    ConflictError,
    ForbiddenError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError,
)
from tests.clinics.fakes import FakeClinicRepository
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


_CLINIC_A = uuid4()
_CLINIC_B = uuid4()
_MANAGER = frozenset({"patients.manage", "patients.read"})


def _clinics_repo() -> FakeClinicRepository:
    clinics = FakeClinicRepository()
    for clinic_id, name in ((_CLINIC_A, "Clínica A"), (_CLINIC_B, "Clínica B")):
        clinics.add(Clinic(id=clinic_id, name=name, created_at=_NOW, updated_at=_NOW))
    return clinics


def _clinic_actor(*clinic_ids: UUID) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        user_id=uuid4(),
        email="clinic@vertere.local",
        full_name="Clinic User",
        role_id=uuid4(),
        role_name="CLINIC_ADMIN",
        role_scope="CLINIC",
        permissions=_MANAGER,
        clinic_ids=frozenset(clinic_ids),
    )


def _patient_in_clinic(
    patients: FakePatientRepository,
    audit: FakeAuditLogWriter,
    clinic_id: UUID | None,
    **kwargs: object,
) -> PatientDTO:
    created = _create_use_case(patients, audit).execute(_create_command(**kwargs))
    stored = patients.get_by_id(created.id)
    assert stored is not None
    stored.clinic_id = clinic_id
    return created


def _update_use_case(
    patients: FakePatientRepository, audit: FakeAuditLogWriter
) -> UpdatePatientUseCase:
    return UpdatePatientUseCase(
        patients=patients,
        species=_species_repo(),
        clinics=_clinics_repo(),
        audit=audit,
        clock=FakeClock(_NOW),
    )


def _deactivate(
    patients: FakePatientRepository, audit: FakeAuditLogWriter, patient_id: UUID
) -> None:
    DeactivatePatientUseCase(patients=patients, audit=audit, clock=FakeClock(_NOW)).execute(
        DeactivatePatientCommand(actor=_actor(permissions=_MANAGER), patient_id=patient_id)
    )


def test_inactive_patient_is_read_only_until_reactivated() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    created = _patient_in_clinic(patients, audit, _CLINIC_A)
    _deactivate(patients, audit, created.id)
    entries_before = len(audit.entries)
    stored = patients.get_by_id(created.id)
    assert stored is not None
    version_before = stored.row_version

    with pytest.raises(InvalidStateTransitionError):
        _update_use_case(patients, audit).execute(
            _update_command(created, expected_row_version=version_before)
        )
    assert stored.name == "Rex"  # nothing was changed
    assert stored.row_version == version_before
    assert len(audit.entries) == entries_before  # and nothing was audited

    reactivated = ReactivatePatientUseCase(
        patients=patients, audit=audit, clock=FakeClock(_NOW)
    ).execute(ReactivatePatientCommand(actor=_actor(permissions=_MANAGER), patient_id=created.id))
    assert reactivated.status == PatientStatus.ACTIVE.value
    assert audit.entries[-1].action == "patients.reactivated"
    assert audit.entries[-1].before_state == {"status": "INACTIVE"}
    assert audit.entries[-1].after_state == {"status": "ACTIVE"}

    edited = _update_use_case(patients, audit).execute(
        _update_command(created, expected_row_version=reactivated.row_version)
    )
    assert edited.name == "Rex Renomeado"


def test_reactivation_is_permissioned_scoped_and_idempotent() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    created = _patient_in_clinic(patients, audit, _CLINIC_A)
    use_case = ReactivatePatientUseCase(patients=patients, audit=audit, clock=FakeClock(_NOW))

    def command(
        actor: AuthenticatedUserDTO, patient_id: UUID = created.id
    ) -> ReactivatePatientCommand:
        return ReactivatePatientCommand(actor=actor, patient_id=patient_id)

    with pytest.raises(ForbiddenError):
        use_case.execute(command(_actor(permissions=frozenset({"patients.read"}))))
    with pytest.raises(NotFoundError):
        use_case.execute(command(_actor(permissions=_MANAGER), patient_id=uuid4()))
    with pytest.raises(NotFoundError):
        use_case.execute(command(_clinic_actor(_CLINIC_B)))

    # Already active: nothing changes, nothing is audited.
    entries_before = len(audit.entries)
    again = use_case.execute(command(_actor(permissions=_MANAGER)))
    assert again.status == PatientStatus.ACTIVE.value
    assert len(audit.entries) == entries_before


def test_moving_a_patient_to_another_clinic_requires_a_reason_and_audits_it() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    created = _patient_in_clinic(patients, audit, _CLINIC_A)
    update = _update_use_case(patients, audit)

    for reason in (None, "", "   "):
        with pytest.raises(ValidationError):
            update.execute(_update_command(created, clinic_id=_CLINIC_B, reason=reason))
    stored = patients.get_by_id(created.id)
    assert stored is not None and stored.clinic_id == _CLINIC_A

    moved = update.execute(
        _update_command(created, clinic_id=_CLINIC_B, reason="  Tutor mudou de clínica  ")
    )
    assert moved.clinic_id == _CLINIC_B
    entry = audit.entries[-1]
    assert entry.action == "patients.updated"
    assert entry.before_state is not None
    assert entry.before_state["clinic_id"] == str(_CLINIC_A)
    assert entry.after_state is not None
    assert entry.after_state["clinic_id"] == str(_CLINIC_B)
    assert entry.after_state["reason"] == "Tutor mudou de clínica"
    # The reason has no "before" counterpart on purpose: it explains the change, it is not a field.
    assert "reason" not in entry.before_state

    # Same clinic (or none given) needs no reason and records none.
    same = update.execute(
        _update_command(
            created,
            clinic_id=_CLINIC_B,
            expected_row_version=moved.row_version,
            reason="ignored: the clinic did not change",
        )
    )
    assert same.clinic_id == _CLINIC_B
    assert audit.entries[-1].after_state is not None
    assert "reason" not in audit.entries[-1].after_state


def test_giving_a_clinic_to_a_legacy_patient_without_one_needs_no_reason() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    created = _patient_in_clinic(patients, audit, None)

    result = _update_use_case(patients, audit).execute(
        _update_command(created, clinic_id=_CLINIC_A)
    )
    assert result.clinic_id == _CLINIC_A


def test_species_and_clinic_filters_combine_with_actor_scope_and_summary_counts() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    other_species = uuid4()
    rex = _patient_in_clinic(patients, audit, _CLINIC_A, name="Rex")
    _patient_in_clinic(patients, audit, _CLINIC_B, name="Mimi")
    bidu = _patient_in_clinic(patients, audit, _CLINIC_A, name="Bidu")
    stored = patients.get_by_id(bidu.id)
    assert stored is not None
    stored.species_id = other_species
    _deactivate(patients, audit, rex.id)

    lister = ListPatientsUseCase(patients=patients)
    summarizer = SummarizePatientsUseCase(patients=patients)
    admin = _actor(permissions=_MANAGER)

    by_species = lister.execute(
        ListPatientsQuery(actor=admin, page=1, page_size=20, species_id=other_species)
    )
    assert [item.name for item in by_species.items] == ["Bidu"]

    summary = summarizer.execute(SummarizePatientsQuery(actor=admin))
    assert (summary.total, summary.active, summary.inactive) == (3, 2, 1)
    in_a = summarizer.execute(SummarizePatientsQuery(actor=admin, clinic_id=_CLINIC_A))
    assert (in_a.total, in_a.active, in_a.inactive) == (2, 1, 1)
    searched = summarizer.execute(SummarizePatientsQuery(actor=admin, search="mimi"))
    assert (searched.total, searched.active) == (1, 1)
    with pytest.raises(ForbiddenError):
        summarizer.execute(SummarizePatientsQuery(actor=_actor(permissions=frozenset())))

    # A clinic actor with two clinics filtering by one sees only that one (the filter used to be
    # ignored for clinic-scoped actors) and never counts patients of a clinic outside its scope.
    only_b = lister.execute(
        ListPatientsQuery(
            actor=_clinic_actor(_CLINIC_A, _CLINIC_B), page=1, page_size=20, clinic_id=_CLINIC_B
        )
    )
    assert [item.name for item in only_b.items] == ["Mimi"]
    assert summarizer.execute(SummarizePatientsQuery(actor=_clinic_actor(_CLINIC_A))).total == 2
    outside = SummarizePatientsQuery(actor=_clinic_actor(_CLINIC_A), clinic_id=_CLINIC_B)
    assert summarizer.execute(outside).total == 0


def test_update_audit_records_only_the_changed_fields_and_never_the_tutor_contact_values() -> None:
    patients = FakePatientRepository()
    audit = FakeAuditLogWriter()
    created = _patient_in_clinic(patients, audit, _CLINIC_A)

    _update_use_case(patients, audit).execute(
        _update_command(
            created,
            name="Rex Renomeado",
            notes="Alérgico a dipirona",
            owner_phone="+55 11 99999-0000",
            owner_document="123.456.789-09",
        )
    )

    entry = audit.entries[-1]
    assert entry.actor_user_id is not None
    assert entry.before_state is not None and entry.after_state is not None
    assert set(entry.after_state) == set(entry.before_state)
    assert entry.after_state["name"] == "Rex Renomeado"
    assert entry.after_state["notes"] == "Alérgico a dipirona"
    # Which contact data changed is recorded; the value never is (PII).
    assert entry.after_state["owner_phone"] == "[alterado]"
    assert entry.after_state["owner_document"] == "[alterado]"
    assert "+55 11 99999-0000" not in str(entry.after_state)
    # Untouched fields stay out of the record.
    assert "sex" not in entry.after_state and "clinic_id" not in entry.after_state
