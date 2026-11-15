from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.modules.attendances.application.cancel_attendance import (
    CancelAttendanceCommand,
    CancelAttendanceUseCase,
)
from app.modules.attendances.application.confirm_attendance import (
    ConfirmAttendanceCommand,
    ConfirmAttendanceItemInput,
    ConfirmAttendanceUseCase,
)
from app.modules.attendances.application.create_attendance_draft import (
    CreateAttendanceDraftCommand,
    CreateAttendanceDraftUseCase,
)
from app.modules.attendances.application.get_attendance import (
    GetAttendanceQuery,
    GetAttendanceUseCase,
)
from app.modules.attendances.application.get_attendance_timeline import (
    GetAttendanceTimelineQuery,
    GetAttendanceTimelineUseCase,
)
from app.modules.attendances.application.list_attendances import (
    ListAttendancesQuery,
    ListAttendancesUseCase,
)
from app.modules.attendances.application.preview_attendance import (
    PreviewAttendanceCommand,
    PreviewAttendanceUseCase,
)
from app.modules.attendances.application.update_attendance import (
    UpdateAttendanceCommand,
    UpdateAttendanceUseCase,
)
from app.modules.attendances.domain.entities import (
    AttendanceStatus,
    CollectionMethod,
    ServiceLevel,
)
from app.modules.catalog.domain.entities import ExamStatus
from app.modules.clinics.domain.entities import ClinicStatus
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.domain.entities import PatientStatus
from app.modules.veterinarians.domain.entities import VeterinarianStatus
from app.shared.domain.errors import (
    AttendanceAlreadyClosedError,
    ConflictError,
    ForbiddenError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError,
)
from tests.attendances.fakes import (
    FakeAttendanceRepository,
    FakeAttendanceSequenceRepository,
    FakeAuditLogWriter,
    FakeClinicRepository,
    FakeClock,
    FakeClosureSettlement,
    FakeExamRepository,
    FakeOnCallFeeSettingRepository,
    FakePatientRepository,
    FakeVeterinarianClinicLinkRepository,
    FakeVeterinarianRepository,
    make_clinic,
    make_exam,
    make_patient,
    make_veterinarian,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_CLINIC_ID = uuid4()
_VETERINARIAN_ID = uuid4()
_PATIENT_ID = uuid4()
_EXAM_ID = uuid4()


def _actor(*, permissions: frozenset[str]) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        user_id=uuid4(),
        email="reception@vertere.local",
        full_name="Reception",
        role_id=uuid4(),
        role_name="RECEPTION",
        permissions=permissions,
    )


def _clinic_actor(
    *, permissions: frozenset[str], clinic_ids: frozenset[UUID]
) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        user_id=uuid4(),
        email="clinic@vertere.local",
        full_name="Clinic",
        role_id=uuid4(),
        role_name="CLINIC_STAFF",
        role_scope="CLINIC",
        permissions=permissions,
        clinic_ids=clinic_ids,
    )


class _Fixture:
    def __init__(
        self,
        *,
        clinic_status: ClinicStatus = ClinicStatus.ACTIVE,
        veterinarian_is_autonomous: bool = True,
        veterinarian_status: VeterinarianStatus = VeterinarianStatus.ACTIVE,
        veterinarian_linked_to_clinic: bool = True,
        patient_status: PatientStatus = PatientStatus.ACTIVE,
    ) -> None:
        self.attendances = FakeAttendanceRepository()
        self.clinics = FakeClinicRepository(
            [make_clinic(clinic_id=_CLINIC_ID, status=clinic_status)]
        )
        self.veterinarians = FakeVeterinarianRepository(
            [
                make_veterinarian(
                    veterinarian_id=_VETERINARIAN_ID,
                    is_autonomous=veterinarian_is_autonomous,
                    status=veterinarian_status,
                )
            ]
        )
        links = {(_VETERINARIAN_ID, _CLINIC_ID)} if veterinarian_linked_to_clinic else set()
        self.veterinarian_clinics = FakeVeterinarianClinicLinkRepository(links)
        self.patients = FakePatientRepository(
            [make_patient(patient_id=_PATIENT_ID, status=patient_status)]
        )
        self.audit = FakeAuditLogWriter()
        self.on_call_fees = FakeOnCallFeeSettingRepository()
        self.closure_settlement = FakeClosureSettlement()

    def cancel_use_case(self) -> CancelAttendanceUseCase:
        return CancelAttendanceUseCase(
            attendances=self.attendances,
            audit=self.audit,
            clock=FakeClock(_NOW),
        )

    def update_use_case(self) -> UpdateAttendanceUseCase:
        return UpdateAttendanceUseCase(
            attendances=self.attendances,
            clinics=self.clinics,
            veterinarians=self.veterinarians,
            veterinarian_clinics=self.veterinarian_clinics,
            patients=self.patients,
            on_call_fees=self.on_call_fees,
            closure_settlement=self.closure_settlement,
            audit=self.audit,
            clock=FakeClock(_NOW),
        )

    def use_case(self) -> CreateAttendanceDraftUseCase:
        return CreateAttendanceDraftUseCase(
            attendances=self.attendances,
            clinics=self.clinics,
            veterinarians=self.veterinarians,
            veterinarian_clinics=self.veterinarian_clinics,
            patients=self.patients,
            audit=self.audit,
            clock=FakeClock(_NOW),
        )


def _command(**overrides: object) -> CreateAttendanceDraftCommand:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"attendances.create"})),
        "clinic_id": _CLINIC_ID,
        "veterinarian_id": _VETERINARIAN_ID,
        "patient_id": _PATIENT_ID,
        "service_date": date(2026, 1, 5),
        "notes": None,
    }
    defaults.update(overrides)
    return CreateAttendanceDraftCommand(**defaults)  # type: ignore[arg-type]


def test_create_draft_validates_references_permission_and_audits() -> None:
    fixture = _Fixture()

    with pytest.raises(ForbiddenError):
        fixture.use_case().execute(_command(actor=_actor(permissions=frozenset())))
    assert fixture.audit.entries == []

    # Cada referência inválida é recusada com o erro certo; nada é gravado.
    rejected: list[tuple[_Fixture, dict[str, object], type[Exception]]] = [
        (_Fixture(), {"clinic_id": uuid4()}, NotFoundError),
        (_Fixture(clinic_status=ClinicStatus.INACTIVE), {}, ValidationError),
        (_Fixture(), {"veterinarian_id": uuid4()}, NotFoundError),
        (_Fixture(veterinarian_status=VeterinarianStatus.INACTIVE), {}, ValidationError),
        (
            _Fixture(veterinarian_is_autonomous=False, veterinarian_linked_to_clinic=False),
            {},
            ValidationError,
        ),
        (_Fixture(), {"patient_id": uuid4()}, NotFoundError),
        (_Fixture(patient_status=PatientStatus.INACTIVE), {}, ValidationError),
    ]
    for case_fixture, overrides, expected_error in rejected:
        with pytest.raises(expected_error):
            case_fixture.use_case().execute(_command(**overrides))
        assert case_fixture.audit.entries == []

    result = fixture.use_case().execute(_command())
    assert result.status == AttendanceStatus.DRAFT.value
    assert (result.clinic_id, result.veterinarian_id, result.patient_id) == (
        _CLINIC_ID,
        _VETERINARIAN_ID,
        _PATIENT_ID,
    )
    assert fixture.attendances.get_by_id(result.id) is not None
    assert fixture.audit.entries[-1].action == "attendances.draft_created"
    assert fixture.audit.entries[-1].entity_type == "attendance"

    # Veterinário não autônomo vinculado à clínica e autônomo sem vínculo também servem.
    for allowed in (
        _Fixture(veterinarian_is_autonomous=False, veterinarian_linked_to_clinic=True),
        _Fixture(veterinarian_is_autonomous=True, veterinarian_linked_to_clinic=False),
    ):
        assert allowed.use_case().execute(_command()).status == AttendanceStatus.DRAFT.value


def test_clinic_actor_cannot_create_read_or_list_attendances_of_another_clinic() -> None:
    fixture = _Fixture()
    foreign_actor = _clinic_actor(
        permissions=frozenset({"attendances.create", "attendances.read"}),
        clinic_ids=frozenset({uuid4()}),
    )
    with pytest.raises(NotFoundError):
        fixture.use_case().execute(_command(actor=foreign_actor))

    created = fixture.use_case().execute(_command())
    with pytest.raises(NotFoundError):
        GetAttendanceUseCase(attendances=fixture.attendances).execute(
            GetAttendanceQuery(actor=foreign_actor, attendance_id=created.id)
        )
    listed = ListAttendancesUseCase(attendances=fixture.attendances).execute(
        ListAttendancesQuery(actor=foreign_actor, page=1, page_size=20)
    )
    assert listed.total == 0


def test_get_and_list_attendances_check_permission_and_filter_by_clinic() -> None:
    fixture = _Fixture()
    reader = _actor(permissions=frozenset({"attendances.read"}))
    nobody = _actor(permissions=frozenset())
    get = GetAttendanceUseCase(attendances=fixture.attendances)
    list_use_case = ListAttendancesUseCase(attendances=fixture.attendances)

    with pytest.raises(ForbiddenError):
        get.execute(GetAttendanceQuery(actor=nobody, attendance_id=uuid4()))
    with pytest.raises(NotFoundError):
        get.execute(GetAttendanceQuery(actor=reader, attendance_id=uuid4()))
    with pytest.raises(ForbiddenError):
        list_use_case.execute(ListAttendancesQuery(actor=nobody, page=1, page_size=20))

    created = fixture.use_case().execute(_command())
    assert get.execute(GetAttendanceQuery(actor=reader, attendance_id=created.id)).id == created.id

    other_clinic_id = uuid4()
    fixture.clinics = FakeClinicRepository(
        [make_clinic(clinic_id=_CLINIC_ID), make_clinic(clinic_id=other_clinic_id)]
    )
    fixture.use_case().execute(_command(clinic_id=other_clinic_id))
    result = list_use_case.execute(
        ListAttendancesQuery(actor=reader, page=1, page_size=20, clinic_id=_CLINIC_ID)
    )
    assert result.total == 1
    assert result.items[0].clinic_id == _CLINIC_ID


class _ConfirmFixture(_Fixture):
    def __init__(
        self,
        *,
        exam_price: Decimal = Decimal("100.00"),
        clinic_status: ClinicStatus = ClinicStatus.ACTIVE,
        veterinarian_is_autonomous: bool = True,
        veterinarian_status: VeterinarianStatus = VeterinarianStatus.ACTIVE,
        veterinarian_linked_to_clinic: bool = True,
        patient_status: PatientStatus = PatientStatus.ACTIVE,
    ) -> None:
        super().__init__(
            clinic_status=clinic_status,
            veterinarian_is_autonomous=veterinarian_is_autonomous,
            veterinarian_status=veterinarian_status,
            veterinarian_linked_to_clinic=veterinarian_linked_to_clinic,
            patient_status=patient_status,
        )
        self.exams = FakeExamRepository([make_exam(exam_id=_EXAM_ID, price_base=exam_price)])
        self.attendance_sequences = FakeAttendanceSequenceRepository()

    def confirm_use_case(self) -> ConfirmAttendanceUseCase:
        return ConfirmAttendanceUseCase(
            attendances=self.attendances,
            attendance_sequences=self.attendance_sequences,
            clinics=self.clinics,
            veterinarians=self.veterinarians,
            veterinarian_clinics=self.veterinarian_clinics,
            patients=self.patients,
            exams=self.exams,
            on_call_fees=self.on_call_fees,
            audit=self.audit,
            clock=FakeClock(_NOW),
        )

    def preview_use_case(self) -> PreviewAttendanceUseCase:
        return PreviewAttendanceUseCase(
            attendances=self.attendances,
            clinics=self.clinics,
            veterinarians=self.veterinarians,
            veterinarian_clinics=self.veterinarian_clinics,
            patients=self.patients,
            exams=self.exams,
            on_call_fees=self.on_call_fees,
        )


def _confirm_command(**overrides: object) -> ConfirmAttendanceCommand:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"attendances.update"})),
        "attendance_id": None,
        "items": [ConfirmAttendanceItemInput(exam_id=_EXAM_ID, quantity=2)],
    }
    defaults.update(overrides)
    return ConfirmAttendanceCommand(**defaults)  # type: ignore[arg-type]


def test_confirm_attendance_computes_totals_on_call_fee_protocol_and_audit() -> None:
    fixture = _ConfirmFixture(exam_price=Decimal("100.00"))
    draft = fixture.use_case().execute(_command())

    result = fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))

    assert result.status == AttendanceStatus.CONFIRMED.value
    assert (result.subtotal, result.grand_total) == (Decimal("200.00"), Decimal("200.00"))
    assert result.on_call_fee == Decimal("0.00")  # atendimento normal não tem taxa de plantão
    assert result.billing_competence == date(2026, 1, 1)
    assert result.protocol_number == "P000001/26"
    assert len(result.items) == 1
    assert result.items[0].total_amount == Decimal("200.00")
    assert fixture.audit.entries[-1].action == "attendances.confirmed"

    # O protocolo seguinte da mesma série anual avança em um.
    second_draft = fixture.use_case().execute(_command())
    second = fixture.confirm_use_case().execute(_confirm_command(attendance_id=second_draft.id))
    assert second.protocol_number == "P000002/26"

    # Taxa de plantão é fixa por atendimento (somada uma vez, não por exame) e a prévia
    # cobra exatamente o que a confirmação cobrará.
    for level, fee in (
        (ServiceLevel.PLANTAO_NORMAL, Decimal("100.00")),
        (ServiceLevel.PLANTAO_ESPECIAL, Decimal("150.00")),
    ):
        on_call_draft = fixture.use_case().execute(_command(service_level=level))
        preview = fixture.preview_use_case().execute(
            _preview_command(attendance_id=on_call_draft.id)
        )
        confirmed = fixture.confirm_use_case().execute(
            _confirm_command(attendance_id=on_call_draft.id)
        )
        assert preview.on_call_fee == confirmed.on_call_fee == fee
        assert preview.grand_total == confirmed.grand_total == Decimal("200.00") + fee
        assert (confirmed.subtotal, confirmed.surcharge_total) == (
            Decimal("200.00"),
            Decimal("0.00"),
        )


def test_confirm_attendance_rejects_invalid_state_and_references() -> None:
    def confirm_fails(
        expected_error: type[Exception],
        *,
        prepare: Callable[[_ConfirmFixture], None] | None = None,
        draft_overrides: dict[str, object] | None = None,
        **confirm_overrides: object,
    ) -> None:
        fixture = _ConfirmFixture()
        draft = fixture.use_case().execute(_command(**(draft_overrides or {})))
        if prepare is not None:
            prepare(fixture)
        with pytest.raises(expected_error):
            fixture.confirm_use_case().execute(
                _confirm_command(
                    attendance_id=confirm_overrides.pop("attendance_id", draft.id),
                    **confirm_overrides,
                )
            )
        assert fixture.audit.entries[-1].action != "attendances.confirmed"

    def inactive_clinic(fixture: _ConfirmFixture) -> None:
        fixture.clinics = FakeClinicRepository(
            [make_clinic(clinic_id=_CLINIC_ID, status=ClinicStatus.INACTIVE)]
        )

    def inactive_veterinarian(fixture: _ConfirmFixture) -> None:
        fixture.veterinarians = FakeVeterinarianRepository(
            [
                make_veterinarian(
                    veterinarian_id=_VETERINARIAN_ID, status=VeterinarianStatus.INACTIVE
                )
            ]
        )

    def inactive_patient(fixture: _ConfirmFixture) -> None:
        fixture.patients = FakePatientRepository(
            [make_patient(patient_id=_PATIENT_ID, status=PatientStatus.INACTIVE)]
        )

    def inactive_exam(fixture: _ConfirmFixture) -> None:
        fixture.exams = FakeExamRepository(
            [make_exam(exam_id=_EXAM_ID, status=ExamStatus.INACTIVE)]
        )

    confirm_fails(ForbiddenError, actor=_actor(permissions=frozenset()))
    confirm_fails(ValidationError, items=[])
    confirm_fails(NotFoundError, attendance_id=uuid4())
    confirm_fails(ValidationError, draft_overrides={"service_date": None})
    confirm_fails(ValidationError, prepare=inactive_clinic)
    confirm_fails(ValidationError, prepare=inactive_veterinarian)
    confirm_fails(ValidationError, prepare=inactive_patient)
    confirm_fails(ValidationError, prepare=inactive_exam)
    confirm_fails(NotFoundError, items=[ConfirmAttendanceItemInput(exam_id=uuid4())])

    # Confirmar duas vezes o mesmo atendimento é recusado.
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())
    fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))
    with pytest.raises(ValidationError):
        fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))


def test_confirm_attendance_discount_needs_override_permission_reason_and_is_totalled() -> None:
    fixture = _ConfirmFixture(exam_price=Decimal("100.00"))
    draft = fixture.use_case().execute(_command())
    override_actor = _actor(
        permissions=frozenset({"attendances.update", "attendances.override_price"})
    )

    def discounted(reason: str | None) -> list[ConfirmAttendanceItemInput]:
        return [
            ConfirmAttendanceItemInput(
                exam_id=_EXAM_ID, discount_amount=Decimal("10.00"), override_reason=reason
            )
        ]

    with pytest.raises(ForbiddenError):  # sem permissão de sobrescrever preço
        fixture.confirm_use_case().execute(
            _confirm_command(attendance_id=draft.id, items=discounted("Promo"))
        )
    with pytest.raises(ValidationError):  # desconto exige motivo
        fixture.confirm_use_case().execute(
            _confirm_command(attendance_id=draft.id, actor=override_actor, items=discounted(None))
        )

    result = fixture.confirm_use_case().execute(
        _confirm_command(attendance_id=draft.id, actor=override_actor, items=discounted("Promo"))
    )
    assert result.discount_total == Decimal("10.00")
    assert result.grand_total == Decimal("90.00")


def _preview_command(**overrides: object) -> PreviewAttendanceCommand:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"attendances.update"})),
        "attendance_id": None,
        "items": [ConfirmAttendanceItemInput(exam_id=_EXAM_ID, quantity=2)],
    }
    defaults.update(overrides)
    return PreviewAttendanceCommand(**defaults)  # type: ignore[arg-type]


def test_preview_attendance_has_no_side_effects_and_matches_what_confirm_charges() -> None:
    fixture = _ConfirmFixture(exam_price=Decimal("100.00"))
    draft = fixture.use_case().execute(_command())
    audit_entries_before_preview = len(fixture.audit.entries)

    result = fixture.preview_use_case().execute(_preview_command(attendance_id=draft.id))

    assert (result.subtotal, result.grand_total) == (Decimal("200.00"), Decimal("200.00"))
    assert result.service_date == date(2026, 1, 5)
    assert len(result.items) == 1
    stored = fixture.attendances.get_by_id(draft.id)
    assert stored is not None
    assert (stored.status, stored.items, stored.protocol_number) == (
        AttendanceStatus.DRAFT,
        [],
        None,
    )
    assert fixture.attendance_sequences.next_sequence(2026) == 1  # a prévia não consome protocolo
    assert len(fixture.audit.entries) == audit_entries_before_preview  # nem audita

    # Com valor quebrado e quantidade maior, a prévia e a confirmação cobram o mesmo.
    rounding = _ConfirmFixture(exam_price=Decimal("133.33"))
    rounding_draft = rounding.use_case().execute(_command())
    items = [ConfirmAttendanceItemInput(exam_id=_EXAM_ID, quantity=3)]
    preview = rounding.preview_use_case().execute(
        _preview_command(attendance_id=rounding_draft.id, items=items)
    )
    confirmed = rounding.confirm_use_case().execute(
        _confirm_command(attendance_id=rounding_draft.id, items=items)
    )
    assert (preview.grand_total, preview.subtotal) == (confirmed.grand_total, confirmed.subtotal)


def test_preview_attendance_rejects_invalid_requests() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())
    discount_without_override = [
        ConfirmAttendanceItemInput(
            exam_id=_EXAM_ID, discount_amount=Decimal("10.00"), override_reason="Promo"
        )
    ]
    preview = fixture.preview_use_case()

    with pytest.raises(ForbiddenError):
        preview.execute(
            _preview_command(attendance_id=draft.id, actor=_actor(permissions=frozenset()))
        )
    with pytest.raises(NotFoundError):
        preview.execute(_preview_command(attendance_id=uuid4()))
    with pytest.raises(ValidationError):
        preview.execute(_preview_command(attendance_id=draft.id, items=[]))
    with pytest.raises(NotFoundError):
        preview.execute(
            _preview_command(
                attendance_id=draft.id, items=[ConfirmAttendanceItemInput(exam_id=uuid4())]
            )
        )
    with pytest.raises(ForbiddenError):  # desconto exige permissão de sobrescrever preço
        preview.execute(_preview_command(attendance_id=draft.id, items=discount_without_override))

    fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))
    with pytest.raises(ValidationError):  # já confirmado
        preview.execute(_preview_command(attendance_id=draft.id))


def _cancel_command(**overrides: object) -> CancelAttendanceCommand:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"attendances.cancel"})),
        "attendance_id": None,
        "reason": "Cliente desistiu do exame",
    }
    defaults.update(overrides)
    return CancelAttendanceCommand(**defaults)  # type: ignore[arg-type]


def test_cancel_attendance_records_the_reason_and_blocks_invalid_transitions() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())
    confirmed_draft = fixture.use_case().execute(_command())
    confirmed = fixture.confirm_use_case().execute(
        _confirm_command(attendance_id=confirmed_draft.id)
    )
    closed_draft = fixture.use_case().execute(_command())
    closed_dto = fixture.confirm_use_case().execute(_confirm_command(attendance_id=closed_draft.id))
    closed = fixture.attendances.get_by_id(closed_dto.id)
    assert closed is not None
    closed.monthly_closure_id = uuid4()
    fixture.attendances.update(closed)
    cancel = fixture.cancel_use_case()

    with pytest.raises(ForbiddenError):
        cancel.execute(
            _cancel_command(attendance_id=draft.id, actor=_actor(permissions=frozenset()))
        )
    with pytest.raises(NotFoundError):
        cancel.execute(_cancel_command(attendance_id=uuid4()))
    with pytest.raises(ValidationError):  # motivo em branco
        cancel.execute(_cancel_command(attendance_id=draft.id, reason="   "))

    result = cancel.execute(_cancel_command(attendance_id=draft.id))
    assert result.status == AttendanceStatus.CANCELLED.value
    assert result.cancel_reason == "Cliente desistiu do exame"
    stored = fixture.attendances.get_by_id(draft.id)
    assert stored is not None
    assert stored.status == AttendanceStatus.CANCELLED
    assert fixture.audit.entries[-1].action == "attendances.cancelled"
    assert fixture.audit.entries[-1].reason == "Cliente desistiu do exame"

    with pytest.raises(InvalidStateTransitionError):  # já cancelado
        cancel.execute(_cancel_command(attendance_id=draft.id))
    # Atendimento confirmado também pode ser cancelado; um já incluído em fechamento não.
    assert (
        cancel.execute(_cancel_command(attendance_id=confirmed.id)).status
        == AttendanceStatus.CANCELLED.value
    )
    with pytest.raises(AttendanceAlreadyClosedError):
        cancel.execute(_cancel_command(attendance_id=closed.id))


def _update_command(**overrides: object) -> UpdateAttendanceCommand:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"attendances.update"})),
        "attendance_id": None,
        "expected_row_version": 1,
    }
    defaults.update(overrides)
    return UpdateAttendanceCommand(**defaults)  # type: ignore[arg-type]


def test_update_draft_attendance_changes_notes_and_clinic_and_audits() -> None:
    fixture = _Fixture()
    draft = fixture.use_case().execute(_command())
    other_clinic_id = uuid4()
    inactive_clinic_id = uuid4()
    fixture.clinics = FakeClinicRepository(
        [
            make_clinic(clinic_id=_CLINIC_ID),
            make_clinic(clinic_id=other_clinic_id),
            make_clinic(clinic_id=inactive_clinic_id, status=ClinicStatus.INACTIVE),
        ]
    )
    use_case = UpdateAttendanceUseCase(
        attendances=fixture.attendances,
        clinics=fixture.clinics,
        veterinarians=fixture.veterinarians,
        veterinarian_clinics=fixture.veterinarian_clinics,
        patients=fixture.patients,
        on_call_fees=fixture.on_call_fees,
        closure_settlement=fixture.closure_settlement,
        audit=fixture.audit,
        clock=FakeClock(_NOW),
    )

    # Sem alterações: nada muda e nada é auditado.
    entries_before = len(fixture.audit.entries)
    unchanged = use_case.execute(_update_command(attendance_id=draft.id))
    assert unchanged.notes == draft.notes
    assert len(fixture.audit.entries) == entries_before

    with pytest.raises(ValidationError):  # clínica nova inativa
        use_case.execute(_update_command(attendance_id=draft.id, clinic_id=inactive_clinic_id))

    result = use_case.execute(_update_command(attendance_id=draft.id, notes="Paciente agitado"))
    assert result.notes == "Paciente agitado"
    assert fixture.audit.entries[-1].action == "attendances.updated"
    assert fixture.audit.entries[-1].after_state == {"notes": "Paciente agitado"}

    switched = use_case.execute(
        _update_command(
            attendance_id=draft.id,
            expected_row_version=result.row_version,
            clinic_id=other_clinic_id,
        )
    )
    assert switched.clinic_id == other_clinic_id


def test_update_attendance_rejects_invalid_requests_and_frozen_states() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())
    update = fixture.update_use_case()

    with pytest.raises(ForbiddenError):
        update.execute(
            _update_command(attendance_id=draft.id, actor=_actor(permissions=frozenset()))
        )
    with pytest.raises(NotFoundError):
        update.execute(_update_command(attendance_id=uuid4()))
    with pytest.raises(ConflictError):  # versão desatualizada
        update.execute(
            _update_command(attendance_id=draft.id, expected_row_version=999, notes="Falha")
        )

    # Confirmado: qualquer correção exige motivo.
    confirmed = fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))
    with pytest.raises(ValidationError):
        update.execute(
            _update_command(
                attendance_id=confirmed.id,
                expected_row_version=confirmed.row_version,
                notes="Sem motivo",
            )
        )
    noted = update.execute(
        _update_command(
            attendance_id=confirmed.id,
            expected_row_version=confirmed.row_version,
            notes="Retorno em 7 dias",
            reason="Orientação do veterinário",
        )
    )
    assert (noted.notes, noted.status) == ("Retorno em 7 dias", AttendanceStatus.CONFIRMED.value)
    with pytest.raises(NotFoundError):  # clínica inexistente continua sendo revalidada
        update.execute(
            _update_command(
                attendance_id=confirmed.id,
                expected_row_version=noted.row_version,
                clinic_id=uuid4(),
                reason="Clínica errada",
            )
        )

    # Incluído em fechamento: continua editável, mas o ajuste passa pelo fechamento.
    stored = fixture.attendances.get_by_id(confirmed.id)
    assert stored is not None
    closure_id = uuid4()
    stored.monthly_closure_id = closure_id
    fixture.attendances.update(stored)
    closed_edit = update.execute(
        _update_command(
            attendance_id=confirmed.id,
            expected_row_version=stored.row_version,
            service_level=ServiceLevel.PLANTAO_NORMAL,
            reason="Era plantão",
        )
    )
    ((settled_closure, total_before, total_after),) = fixture.closure_settlement.calls
    assert settled_closure == closure_id
    assert total_after == total_before + Decimal("100.00") == closed_edit.grand_total
    stored = fixture.attendances.get_by_id(confirmed.id)
    assert stored is not None
    stored.monthly_closure_id = None
    fixture.attendances.update(stored)

    # Importado da planilha (COMPLETED): nunca editável por aqui.
    legacy = fixture.attendances.get_by_id(noted.id)
    assert legacy is not None
    legacy.monthly_closure_id = None
    legacy.status = AttendanceStatus.COMPLETED
    fixture.attendances.update(legacy)
    with pytest.raises(InvalidStateTransitionError):
        update.execute(
            _update_command(
                attendance_id=noted.id,
                expected_row_version=legacy.row_version,
                notes="Legado",
                reason="Tentativa",
            )
        )


def test_get_attendance_timeline_is_scoped_ordered_and_permission_checked() -> None:
    fixture = _Fixture()
    draft = fixture.use_case().execute(_command())
    other = fixture.use_case().execute(_command())
    fixture.update_use_case().execute(_update_command(attendance_id=draft.id, notes="Edição 1"))
    fixture.cancel_use_case().execute(_cancel_command(attendance_id=draft.id))
    # FakeClock devolve um único instante; escalona `occurred_at` para exercitar a ordenação,
    # como o SystemClock real faria.
    fixture.audit.entries = [
        replace(entry, occurred_at=_NOW + timedelta(seconds=i))
        for i, entry in enumerate(fixture.audit.entries)
    ]
    use_case = GetAttendanceTimelineUseCase(attendances=fixture.attendances, audit=fixture.audit)

    def timeline(attendance_id: UUID, *, permissions: frozenset[str]) -> object:
        return use_case.execute(
            GetAttendanceTimelineQuery(
                actor=_actor(permissions=permissions),
                attendance_id=attendance_id,
                page=1,
                page_size=20,
            )
        )

    reader = frozenset({"attendances.read"})
    result = use_case.execute(
        GetAttendanceTimelineQuery(
            actor=_actor(permissions=reader), attendance_id=draft.id, page=1, page_size=20
        )
    )
    assert result.total == 3
    assert [entry.action for entry in result.entries] == [
        "attendances.cancelled",
        "attendances.updated",
        "attendances.draft_created",
    ]
    assert {entry.entity_id for entry in result.entries} == {
        str(draft.id)
    }  # não mistura com `other`
    assert other.id != draft.id

    with pytest.raises(ForbiddenError):
        timeline(draft.id, permissions=frozenset())
    with pytest.raises(NotFoundError):
        timeline(uuid4(), permissions=reader)


def test_confirmed_and_cancelled_attendances_can_be_corrected_with_a_reason_and_audit_the_diff() -> (
    None
):
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())
    confirmed = fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))
    update = fixture.update_use_case()
    assert confirmed.on_call_fee == Decimal("0.00")

    # Plantão: a taxa fixa entra no total e a data move a competência; tudo vai para o diff.
    corrected = update.execute(
        _update_command(
            attendance_id=confirmed.id,
            expected_row_version=confirmed.row_version,
            service_level=ServiceLevel.PLANTAO_NORMAL,
            service_date=date(2026, 3, 5),
            collection_method=CollectionMethod.UBER,
            reason="Registrado como normal por engano; coleta foi por Uber",
        )
    )
    assert corrected.on_call_fee == Decimal("100.00")
    assert corrected.grand_total == confirmed.grand_total + Decimal("100.00")
    assert corrected.billing_competence == date(2026, 3, 1)
    assert corrected.collection_method == CollectionMethod.UBER.value
    entry = fixture.audit.entries[-1]
    assert entry.action == "attendances.updated"
    assert entry.reason == "Registrado como normal por engano; coleta foi por Uber"
    assert entry.before_state is not None and entry.after_state is not None
    assert entry.before_state["service_level"] == "NORMAL"
    assert entry.after_state["service_level"] == "PLANTAO_NORMAL"
    assert entry.after_state["on_call_fee"] == "100.00"
    assert entry.after_state["billing_competence"] == "2026-03-01"

    # Voltar para normal zera a taxa: o total volta ao valor original dos itens.
    back = update.execute(
        _update_command(
            attendance_id=confirmed.id,
            expected_row_version=corrected.row_version,
            service_level=ServiceLevel.NORMAL,
            reason="Era atendimento normal",
        )
    )
    assert (back.on_call_fee, back.grand_total) == (Decimal("0.00"), confirmed.grand_total)

    # Motivo em branco não vale.
    with pytest.raises(ValidationError):
        update.execute(
            _update_command(
                attendance_id=confirmed.id,
                expected_row_version=back.row_version,
                notes="x",
                reason="   ",
            )
        )

    # Cancelado também pode ser corrigido (dados cadastrais), com motivo.
    cancelled_draft = fixture.use_case().execute(_command())
    cancelled = fixture.cancel_use_case().execute(_cancel_command(attendance_id=cancelled_draft.id))
    fixed = update.execute(
        _update_command(
            attendance_id=cancelled.id,
            expected_row_version=cancelled.row_version,
            notes="Cancelado por engano de cadastro",
            reason="Ajuste de observação",
        )
    )
    assert fixed.notes == "Cancelado por engano de cadastro"
    assert fixed.status == AttendanceStatus.CANCELLED.value


class _FakeUserNames:
    def __init__(self, names: dict[UUID, str]) -> None:
        self._names = names

    def names_by_id(self, user_ids: object) -> dict[UUID, str]:
        return {uid: n for uid, n in self._names.items() if uid in user_ids}  # type: ignore[operator]


def test_timeline_exposes_author_names_only_to_lab_scope() -> None:
    fixture = _Fixture()
    draft = fixture.use_case().execute(_command())
    author = fixture.audit.entries[0].actor_user_id
    assert author is not None
    lookup = _FakeUserNames({author: "Ana Souza"})
    use_case = GetAttendanceTimelineUseCase(
        attendances=fixture.attendances, audit=fixture.audit, user_names=lookup
    )
    reader = frozenset({"attendances.read"})
    result = use_case.execute(
        GetAttendanceTimelineQuery(
            actor=_actor(permissions=reader), attendance_id=draft.id, page=1, page_size=20
        )
    )
    assert result.actor_names == {author: "Ana Souza"}
    clinic_actor = replace(
        _actor(permissions=reader), role_scope="CLINIC", clinic_ids=frozenset({draft.clinic_id})
    )
    result = use_case.execute(
        GetAttendanceTimelineQuery(actor=clinic_actor, attendance_id=draft.id, page=1, page_size=20)
    )
    assert result.actor_names == {}
