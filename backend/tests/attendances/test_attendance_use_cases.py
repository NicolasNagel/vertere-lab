from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

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
from app.modules.attendances.domain.entities import AttendanceStatus, ServiceLevel
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


def test_create_draft_succeeds_and_audits() -> None:
    fixture = _Fixture()

    result = fixture.use_case().execute(_command())

    assert result.status == AttendanceStatus.DRAFT.value
    assert result.clinic_id == _CLINIC_ID
    assert result.veterinarian_id == _VETERINARIAN_ID
    assert result.patient_id == _PATIENT_ID
    assert fixture.attendances.get_by_id(result.id) is not None
    assert fixture.audit.entries[-1].action == "attendances.draft_created"
    assert fixture.audit.entries[-1].entity_type == "attendance"


def test_create_draft_without_permission_is_forbidden() -> None:
    fixture = _Fixture()

    with pytest.raises(ForbiddenError):
        fixture.use_case().execute(_command(actor=_actor(permissions=frozenset())))


def test_create_draft_with_unknown_clinic_is_not_found() -> None:
    fixture = _Fixture()

    with pytest.raises(NotFoundError):
        fixture.use_case().execute(_command(clinic_id=uuid4()))


def test_create_draft_with_inactive_clinic_is_invalid() -> None:
    fixture = _Fixture(clinic_status=ClinicStatus.INACTIVE)

    with pytest.raises(ValidationError):
        fixture.use_case().execute(_command())


def test_create_draft_with_unknown_veterinarian_is_not_found() -> None:
    fixture = _Fixture()

    with pytest.raises(NotFoundError):
        fixture.use_case().execute(_command(veterinarian_id=uuid4()))


def test_create_draft_with_inactive_veterinarian_is_invalid() -> None:
    fixture = _Fixture(veterinarian_status=VeterinarianStatus.INACTIVE)

    with pytest.raises(ValidationError):
        fixture.use_case().execute(_command())


def test_create_draft_with_non_autonomous_veterinarian_not_linked_to_clinic_is_invalid() -> None:
    fixture = _Fixture(veterinarian_is_autonomous=False, veterinarian_linked_to_clinic=False)

    with pytest.raises(ValidationError):
        fixture.use_case().execute(_command())


def test_create_draft_with_non_autonomous_veterinarian_linked_to_clinic_succeeds() -> None:
    fixture = _Fixture(veterinarian_is_autonomous=False, veterinarian_linked_to_clinic=True)

    result = fixture.use_case().execute(_command())

    assert result.status == AttendanceStatus.DRAFT.value


def test_create_draft_with_autonomous_veterinarian_not_linked_to_any_clinic_succeeds() -> None:
    fixture = _Fixture(veterinarian_is_autonomous=True, veterinarian_linked_to_clinic=False)

    result = fixture.use_case().execute(_command())

    assert result.status == AttendanceStatus.DRAFT.value


def test_create_draft_with_unknown_patient_is_not_found() -> None:
    fixture = _Fixture()

    with pytest.raises(NotFoundError):
        fixture.use_case().execute(_command(patient_id=uuid4()))


def test_create_draft_with_inactive_patient_is_invalid() -> None:
    fixture = _Fixture(patient_status=PatientStatus.INACTIVE)

    with pytest.raises(ValidationError):
        fixture.use_case().execute(_command())


def test_get_attendance_not_found() -> None:
    attendances = FakeAttendanceRepository()
    use_case = GetAttendanceUseCase(attendances=attendances)

    with pytest.raises(NotFoundError):
        use_case.execute(
            GetAttendanceQuery(
                actor=_actor(permissions=frozenset({"attendances.read"})),
                attendance_id=uuid4(),
            )
        )


def test_get_attendance_without_permission_is_forbidden() -> None:
    attendances = FakeAttendanceRepository()
    use_case = GetAttendanceUseCase(attendances=attendances)

    with pytest.raises(ForbiddenError):
        use_case.execute(
            GetAttendanceQuery(actor=_actor(permissions=frozenset()), attendance_id=uuid4())
        )


def test_get_attendance_succeeds() -> None:
    fixture = _Fixture()
    created = fixture.use_case().execute(_command())

    use_case = GetAttendanceUseCase(attendances=fixture.attendances)
    result = use_case.execute(
        GetAttendanceQuery(
            actor=_actor(permissions=frozenset({"attendances.read"})), attendance_id=created.id
        )
    )

    assert result.id == created.id


def test_list_attendances_requires_permission() -> None:
    attendances = FakeAttendanceRepository()
    use_case = ListAttendancesUseCase(attendances=attendances)

    with pytest.raises(ForbiddenError):
        use_case.execute(
            ListAttendancesQuery(actor=_actor(permissions=frozenset()), page=1, page_size=20)
        )


def test_list_attendances_filters_by_clinic() -> None:
    fixture = _Fixture()
    fixture.use_case().execute(_command())
    other_clinic_id = uuid4()
    fixture.clinics = FakeClinicRepository(
        [
            make_clinic(clinic_id=_CLINIC_ID),
            make_clinic(clinic_id=other_clinic_id),
        ]
    )
    fixture.use_case().execute(_command(clinic_id=other_clinic_id))

    use_case = ListAttendancesUseCase(attendances=fixture.attendances)
    result = use_case.execute(
        ListAttendancesQuery(
            actor=_actor(permissions=frozenset({"attendances.read"})),
            page=1,
            page_size=20,
            clinic_id=_CLINIC_ID,
        )
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
        self.on_call_fees = FakeOnCallFeeSettingRepository()

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


def test_confirm_attendance_succeeds_and_computes_totals() -> None:
    fixture = _ConfirmFixture(exam_price=Decimal("100.00"))
    draft = fixture.use_case().execute(_command())

    result = fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))

    assert result.status == AttendanceStatus.CONFIRMED.value
    assert result.grand_total == Decimal("200.00")
    assert result.subtotal == Decimal("200.00")
    assert result.billing_competence == date(2026, 1, 1)
    assert result.protocol_number == "2026/000001"
    assert len(result.items) == 1
    assert result.items[0].total_amount == Decimal("200.00")
    assert fixture.audit.entries[-1].action == "attendances.confirmed"


def test_confirm_attendance_with_plantao_normal_adds_flat_fee_once() -> None:
    """Taxa fixa (R$100) é somada uma única vez ao atendimento, não por
    exame — 2 itens não dobram o adicional."""
    fixture = _ConfirmFixture(exam_price=Decimal("100.00"))
    draft = fixture.use_case().execute(_command(service_level=ServiceLevel.PLANTAO_NORMAL))

    result = fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))

    assert result.subtotal == Decimal("200.00")
    assert result.surcharge_total == Decimal("0.00")
    assert result.on_call_fee == Decimal("100.00")
    assert result.grand_total == Decimal("300.00")


def test_confirm_attendance_with_plantao_especial_adds_higher_flat_fee() -> None:
    fixture = _ConfirmFixture(exam_price=Decimal("100.00"))
    draft = fixture.use_case().execute(_command(service_level=ServiceLevel.PLANTAO_ESPECIAL))

    result = fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))

    assert result.on_call_fee == Decimal("150.00")
    assert result.grand_total == Decimal("350.00")


def test_confirm_attendance_normal_has_no_on_call_fee() -> None:
    fixture = _ConfirmFixture(exam_price=Decimal("100.00"))
    draft = fixture.use_case().execute(_command(service_level=ServiceLevel.NORMAL))

    result = fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))

    assert result.on_call_fee == Decimal("0.00")
    assert result.grand_total == Decimal("200.00")


def test_preview_plantao_fee_matches_what_confirm_would_charge() -> None:
    fixture = _ConfirmFixture(exam_price=Decimal("100.00"))
    draft = fixture.use_case().execute(_command(service_level=ServiceLevel.PLANTAO_ESPECIAL))

    preview = fixture.preview_use_case().execute(_preview_command(attendance_id=draft.id))
    confirmed = fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))

    assert preview.on_call_fee == confirmed.on_call_fee == Decimal("150.00")
    assert preview.grand_total == confirmed.grand_total


def test_confirm_attendance_without_permission_is_forbidden() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())

    with pytest.raises(ForbiddenError):
        fixture.confirm_use_case().execute(
            _confirm_command(attendance_id=draft.id, actor=_actor(permissions=frozenset()))
        )


def test_confirm_attendance_without_items_is_invalid() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())

    with pytest.raises(ValidationError):
        fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id, items=[]))


def test_confirm_attendance_unknown_attendance_is_not_found() -> None:
    fixture = _ConfirmFixture()

    with pytest.raises(NotFoundError):
        fixture.confirm_use_case().execute(_confirm_command(attendance_id=uuid4()))


def test_confirm_attendance_already_confirmed_is_invalid() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())
    fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))

    with pytest.raises(ValidationError):
        fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))


def test_confirm_attendance_without_service_date_is_invalid() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command(service_date=None))

    with pytest.raises(ValidationError):
        fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))


def test_confirm_attendance_with_inactive_clinic_is_invalid() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())
    fixture.clinics = FakeClinicRepository(
        [make_clinic(clinic_id=_CLINIC_ID, status=ClinicStatus.INACTIVE)]
    )

    with pytest.raises(ValidationError):
        fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))


def test_confirm_attendance_with_inactive_veterinarian_is_invalid() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())
    fixture.veterinarians = FakeVeterinarianRepository(
        [make_veterinarian(veterinarian_id=_VETERINARIAN_ID, status=VeterinarianStatus.INACTIVE)]
    )

    with pytest.raises(ValidationError):
        fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))


def test_confirm_attendance_with_inactive_patient_is_invalid() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())
    fixture.patients = FakePatientRepository(
        [make_patient(patient_id=_PATIENT_ID, status=PatientStatus.INACTIVE)]
    )

    with pytest.raises(ValidationError):
        fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))


def test_confirm_attendance_with_unknown_exam_is_not_found() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())

    with pytest.raises(NotFoundError):
        fixture.confirm_use_case().execute(
            _confirm_command(
                attendance_id=draft.id,
                items=[ConfirmAttendanceItemInput(exam_id=uuid4())],
            )
        )


def test_confirm_attendance_with_inactive_exam_is_invalid() -> None:
    fixture = _ConfirmFixture()
    fixture.exams = FakeExamRepository([make_exam(exam_id=_EXAM_ID, status=ExamStatus.INACTIVE)])
    draft = fixture.use_case().execute(_command())

    with pytest.raises(ValidationError):
        fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))


def test_confirm_attendance_with_discount_requires_override_permission() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())

    with pytest.raises(ForbiddenError):
        fixture.confirm_use_case().execute(
            _confirm_command(
                attendance_id=draft.id,
                items=[
                    ConfirmAttendanceItemInput(
                        exam_id=_EXAM_ID, discount_amount=Decimal("10.00"), override_reason="Promo"
                    )
                ],
            )
        )


def test_confirm_attendance_with_discount_requires_reason() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())

    with pytest.raises(ValidationError):
        fixture.confirm_use_case().execute(
            _confirm_command(
                attendance_id=draft.id,
                actor=_actor(
                    permissions=frozenset({"attendances.update", "attendances.override_price"})
                ),
                items=[
                    ConfirmAttendanceItemInput(exam_id=_EXAM_ID, discount_amount=Decimal("10.00"))
                ],
            )
        )


def test_confirm_attendance_with_authorized_discount_succeeds() -> None:
    fixture = _ConfirmFixture(exam_price=Decimal("100.00"))
    draft = fixture.use_case().execute(_command())

    result = fixture.confirm_use_case().execute(
        _confirm_command(
            attendance_id=draft.id,
            actor=_actor(
                permissions=frozenset({"attendances.update", "attendances.override_price"})
            ),
            items=[
                ConfirmAttendanceItemInput(
                    exam_id=_EXAM_ID, discount_amount=Decimal("10.00"), override_reason="Promo"
                )
            ],
        )
    )

    assert result.grand_total == Decimal("90.00")
    assert result.discount_total == Decimal("10.00")


def test_confirm_attendance_protocol_sequence_increments_per_year() -> None:
    fixture = _ConfirmFixture()
    first_draft = fixture.use_case().execute(_command())
    first = fixture.confirm_use_case().execute(_confirm_command(attendance_id=first_draft.id))

    second_draft = fixture.use_case().execute(_command())
    second = fixture.confirm_use_case().execute(_confirm_command(attendance_id=second_draft.id))

    assert first.protocol_number == "2026/000001"
    assert second.protocol_number == "2026/000002"


def _preview_command(**overrides: object) -> PreviewAttendanceCommand:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"attendances.update"})),
        "attendance_id": None,
        "items": [ConfirmAttendanceItemInput(exam_id=_EXAM_ID, quantity=2)],
    }
    defaults.update(overrides)
    return PreviewAttendanceCommand(**defaults)  # type: ignore[arg-type]


def test_preview_attendance_computes_totals_without_persisting_or_consuming_protocol() -> None:
    fixture = _ConfirmFixture(exam_price=Decimal("100.00"))
    draft = fixture.use_case().execute(_command())
    audit_entries_before_preview = len(fixture.audit.entries)

    result = fixture.preview_use_case().execute(_preview_command(attendance_id=draft.id))

    assert result.grand_total == Decimal("200.00")
    assert result.subtotal == Decimal("200.00")
    assert result.service_date == date(2026, 1, 5)
    assert len(result.items) == 1

    stored = fixture.attendances.get_by_id(draft.id)
    assert stored is not None
    assert stored.status == AttendanceStatus.DRAFT
    assert stored.items == []
    assert stored.protocol_number is None
    assert fixture.attendance_sequences.next_sequence(2026) == 1  # untouched by preview
    assert len(fixture.audit.entries) == audit_entries_before_preview  # no audit for a dry run


def test_preview_attendance_matches_what_confirm_would_charge() -> None:
    fixture = _ConfirmFixture(exam_price=Decimal("133.33"))
    draft = fixture.use_case().execute(_command())

    preview = fixture.preview_use_case().execute(
        _preview_command(
            attendance_id=draft.id,
            items=[ConfirmAttendanceItemInput(exam_id=_EXAM_ID, quantity=3)],
        )
    )
    confirmed = fixture.confirm_use_case().execute(
        _confirm_command(
            attendance_id=draft.id,
            items=[ConfirmAttendanceItemInput(exam_id=_EXAM_ID, quantity=3)],
        )
    )

    assert preview.grand_total == confirmed.grand_total
    assert preview.subtotal == confirmed.subtotal


def test_preview_attendance_without_permission_is_forbidden() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())

    with pytest.raises(ForbiddenError):
        fixture.preview_use_case().execute(
            _preview_command(attendance_id=draft.id, actor=_actor(permissions=frozenset()))
        )


def test_preview_attendance_unknown_attendance_is_not_found() -> None:
    fixture = _ConfirmFixture()

    with pytest.raises(NotFoundError):
        fixture.preview_use_case().execute(_preview_command(attendance_id=uuid4()))


def test_preview_attendance_already_confirmed_is_invalid() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())
    fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))

    with pytest.raises(ValidationError):
        fixture.preview_use_case().execute(_preview_command(attendance_id=draft.id))


def test_preview_attendance_without_items_is_invalid() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())

    with pytest.raises(ValidationError):
        fixture.preview_use_case().execute(_preview_command(attendance_id=draft.id, items=[]))


def test_preview_attendance_with_unknown_exam_is_not_found() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())

    with pytest.raises(NotFoundError):
        fixture.preview_use_case().execute(
            _preview_command(
                attendance_id=draft.id,
                items=[ConfirmAttendanceItemInput(exam_id=uuid4())],
            )
        )


def test_preview_attendance_with_discount_requires_override_permission() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())

    with pytest.raises(ForbiddenError):
        fixture.preview_use_case().execute(
            _preview_command(
                attendance_id=draft.id,
                items=[
                    ConfirmAttendanceItemInput(
                        exam_id=_EXAM_ID, discount_amount=Decimal("10.00"), override_reason="Promo"
                    )
                ],
            )
        )


def _cancel_command(**overrides: object) -> CancelAttendanceCommand:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"attendances.cancel"})),
        "attendance_id": None,
        "reason": "Cliente desistiu do exame",
    }
    defaults.update(overrides)
    return CancelAttendanceCommand(**defaults)  # type: ignore[arg-type]


def test_cancel_draft_attendance_succeeds_and_audits() -> None:
    fixture = _Fixture()
    draft = fixture.use_case().execute(_command())

    result = fixture.cancel_use_case().execute(_cancel_command(attendance_id=draft.id))

    assert result.status == AttendanceStatus.CANCELLED.value
    assert result.cancel_reason == "Cliente desistiu do exame"
    stored = fixture.attendances.get_by_id(draft.id)
    assert stored is not None
    assert stored.status == AttendanceStatus.CANCELLED
    assert fixture.audit.entries[-1].action == "attendances.cancelled"
    assert fixture.audit.entries[-1].reason == "Cliente desistiu do exame"


def test_cancel_confirmed_attendance_succeeds() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())
    confirmed = fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))

    result = fixture.cancel_use_case().execute(_cancel_command(attendance_id=confirmed.id))

    assert result.status == AttendanceStatus.CANCELLED.value


def test_cancel_attendance_without_permission_is_forbidden() -> None:
    fixture = _Fixture()
    draft = fixture.use_case().execute(_command())

    with pytest.raises(ForbiddenError):
        fixture.cancel_use_case().execute(
            _cancel_command(attendance_id=draft.id, actor=_actor(permissions=frozenset()))
        )


def test_cancel_attendance_unknown_is_not_found() -> None:
    fixture = _Fixture()

    with pytest.raises(NotFoundError):
        fixture.cancel_use_case().execute(_cancel_command(attendance_id=uuid4()))


def test_cancel_attendance_without_reason_is_invalid() -> None:
    fixture = _Fixture()
    draft = fixture.use_case().execute(_command())

    with pytest.raises(ValidationError):
        fixture.cancel_use_case().execute(_cancel_command(attendance_id=draft.id, reason="   "))


def test_cancel_already_cancelled_attendance_is_invalid_transition() -> None:
    fixture = _Fixture()
    draft = fixture.use_case().execute(_command())
    fixture.cancel_use_case().execute(_cancel_command(attendance_id=draft.id))

    with pytest.raises(InvalidStateTransitionError):
        fixture.cancel_use_case().execute(_cancel_command(attendance_id=draft.id))


def test_cancel_attendance_already_in_a_closure_is_blocked() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())
    confirmed_dto = fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))
    confirmed = fixture.attendances.get_by_id(confirmed_dto.id)
    assert confirmed is not None
    confirmed.monthly_closure_id = uuid4()
    fixture.attendances.update(confirmed)

    with pytest.raises(AttendanceAlreadyClosedError):
        fixture.cancel_use_case().execute(_cancel_command(attendance_id=confirmed.id))


def _update_command(**overrides: object) -> UpdateAttendanceCommand:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"attendances.update"})),
        "attendance_id": None,
        "expected_row_version": 1,
    }
    defaults.update(overrides)
    return UpdateAttendanceCommand(**defaults)  # type: ignore[arg-type]


def test_update_draft_attendance_notes_succeeds_and_audits() -> None:
    fixture = _Fixture()
    draft = fixture.use_case().execute(_command())

    result = fixture.update_use_case().execute(
        _update_command(attendance_id=draft.id, notes="Paciente agitado")
    )

    assert result.notes == "Paciente agitado"
    assert fixture.audit.entries[-1].action == "attendances.updated"
    assert fixture.audit.entries[-1].after_state == {"notes": "Paciente agitado"}


def test_update_draft_attendance_switches_clinic_with_revalidation() -> None:
    fixture = _Fixture()
    draft = fixture.use_case().execute(_command())
    other_clinic_id = uuid4()
    fixture.clinics = FakeClinicRepository(
        [make_clinic(clinic_id=_CLINIC_ID), make_clinic(clinic_id=other_clinic_id)]
    )
    use_case = UpdateAttendanceUseCase(
        attendances=fixture.attendances,
        clinics=fixture.clinics,
        veterinarians=fixture.veterinarians,
        veterinarian_clinics=fixture.veterinarian_clinics,
        patients=fixture.patients,
        audit=fixture.audit,
        clock=FakeClock(_NOW),
    )

    result = use_case.execute(_update_command(attendance_id=draft.id, clinic_id=other_clinic_id))

    assert result.clinic_id == other_clinic_id


def test_update_draft_attendance_with_inactive_new_clinic_is_invalid() -> None:
    fixture = _Fixture()
    draft = fixture.use_case().execute(_command())
    inactive_clinic_id = uuid4()
    fixture.clinics = FakeClinicRepository(
        [
            make_clinic(clinic_id=_CLINIC_ID),
            make_clinic(clinic_id=inactive_clinic_id, status=ClinicStatus.INACTIVE),
        ]
    )
    use_case = UpdateAttendanceUseCase(
        attendances=fixture.attendances,
        clinics=fixture.clinics,
        veterinarians=fixture.veterinarians,
        veterinarian_clinics=fixture.veterinarian_clinics,
        patients=fixture.patients,
        audit=fixture.audit,
        clock=FakeClock(_NOW),
    )

    with pytest.raises(ValidationError):
        use_case.execute(_update_command(attendance_id=draft.id, clinic_id=inactive_clinic_id))


def test_update_confirmed_attendance_notes_succeeds() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())
    confirmed = fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))

    result = fixture.update_use_case().execute(
        _update_command(
            attendance_id=confirmed.id,
            expected_row_version=confirmed.row_version,
            notes="Retorno em 7 dias",
        )
    )

    assert result.notes == "Retorno em 7 dias"
    assert result.status == AttendanceStatus.CONFIRMED.value


def test_update_confirmed_attendance_clinic_is_rejected() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())
    confirmed = fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))

    with pytest.raises(ValidationError):
        fixture.update_use_case().execute(
            _update_command(
                attendance_id=confirmed.id,
                expected_row_version=confirmed.row_version,
                clinic_id=uuid4(),
            )
        )


def test_update_attendance_without_permission_is_forbidden() -> None:
    fixture = _Fixture()
    draft = fixture.use_case().execute(_command())

    with pytest.raises(ForbiddenError):
        fixture.update_use_case().execute(
            _update_command(attendance_id=draft.id, actor=_actor(permissions=frozenset()))
        )


def test_update_attendance_unknown_is_not_found() -> None:
    fixture = _Fixture()

    with pytest.raises(NotFoundError):
        fixture.update_use_case().execute(_update_command(attendance_id=uuid4()))


def test_update_attendance_wrong_row_version_is_conflict() -> None:
    fixture = _Fixture()
    draft = fixture.use_case().execute(_command())

    with pytest.raises(ConflictError):
        fixture.update_use_case().execute(
            _update_command(
                attendance_id=draft.id, expected_row_version=999, notes="Deveria falhar"
            )
        )


def test_update_attendance_with_no_changes_is_a_noop() -> None:
    fixture = _Fixture()
    draft = fixture.use_case().execute(_command())
    audit_entries_before = len(fixture.audit.entries)

    result = fixture.update_use_case().execute(_update_command(attendance_id=draft.id))

    assert result.notes == draft.notes
    assert len(fixture.audit.entries) == audit_entries_before


def test_update_cancelled_attendance_is_invalid_transition() -> None:
    fixture = _Fixture()
    draft = fixture.use_case().execute(_command())
    fixture.cancel_use_case().execute(_cancel_command(attendance_id=draft.id))

    with pytest.raises(InvalidStateTransitionError):
        fixture.update_use_case().execute(_update_command(attendance_id=draft.id))


def test_update_attendance_already_in_a_closure_is_blocked() -> None:
    fixture = _ConfirmFixture()
    draft = fixture.use_case().execute(_command())
    confirmed_dto = fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))
    confirmed = fixture.attendances.get_by_id(confirmed_dto.id)
    assert confirmed is not None
    confirmed.monthly_closure_id = uuid4()
    fixture.attendances.update(confirmed)

    with pytest.raises(AttendanceAlreadyClosedError):
        fixture.update_use_case().execute(
            _update_command(
                attendance_id=confirmed.id,
                expected_row_version=confirmed.row_version,
                notes="Não deveria passar",
            )
        )


def test_get_attendance_timeline_lists_entries_most_recent_first() -> None:
    fixture = _Fixture()
    draft = fixture.use_case().execute(_command())
    fixture.update_use_case().execute(_update_command(attendance_id=draft.id, notes="Edição 1"))
    fixture.cancel_use_case().execute(_cancel_command(attendance_id=draft.id))
    # FakeClock returns one fixed instant for the whole fixture — stagger
    # `occurred_at` here so ordering is actually exercised, mirroring real
    # `SystemClock` where each action gets a distinct timestamp.
    fixture.audit.entries = [
        replace(entry, occurred_at=_NOW + timedelta(seconds=i))
        for i, entry in enumerate(fixture.audit.entries)
    ]

    use_case = GetAttendanceTimelineUseCase(attendances=fixture.attendances, audit=fixture.audit)
    result = use_case.execute(
        GetAttendanceTimelineQuery(
            actor=_actor(permissions=frozenset({"attendances.read"})),
            attendance_id=draft.id,
            page=1,
            page_size=20,
        )
    )

    assert result.total == 3
    actions = [entry.action for entry in result.entries]
    assert actions == [
        "attendances.cancelled",
        "attendances.updated",
        "attendances.draft_created",
    ]


def test_get_attendance_timeline_only_includes_this_attendance() -> None:
    fixture = _Fixture()
    draft_a = fixture.use_case().execute(_command())
    draft_b = fixture.use_case().execute(_command())

    use_case = GetAttendanceTimelineUseCase(attendances=fixture.attendances, audit=fixture.audit)
    result = use_case.execute(
        GetAttendanceTimelineQuery(
            actor=_actor(permissions=frozenset({"attendances.read"})),
            attendance_id=draft_a.id,
            page=1,
            page_size=20,
        )
    )

    assert result.total == 1
    assert result.entries[0].entity_id == str(draft_a.id)
    assert draft_a.id != draft_b.id


def test_get_attendance_timeline_without_permission_is_forbidden() -> None:
    fixture = _Fixture()
    draft = fixture.use_case().execute(_command())

    use_case = GetAttendanceTimelineUseCase(attendances=fixture.attendances, audit=fixture.audit)
    with pytest.raises(ForbiddenError):
        use_case.execute(
            GetAttendanceTimelineQuery(
                actor=_actor(permissions=frozenset()),
                attendance_id=draft.id,
                page=1,
                page_size=20,
            )
        )


def test_get_attendance_timeline_unknown_attendance_is_not_found() -> None:
    fixture = _Fixture()
    use_case = GetAttendanceTimelineUseCase(attendances=fixture.attendances, audit=fixture.audit)

    with pytest.raises(NotFoundError):
        use_case.execute(
            GetAttendanceTimelineQuery(
                actor=_actor(permissions=frozenset({"attendances.read"})),
                attendance_id=uuid4(),
                page=1,
                page_size=20,
            )
        )
