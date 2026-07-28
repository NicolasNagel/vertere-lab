from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

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
from app.modules.attendances.application.list_attendances import (
    ListAttendancesQuery,
    ListAttendancesUseCase,
)
from app.modules.attendances.domain.entities import AttendanceStatus
from app.modules.catalog.domain.entities import ExamStatus
from app.modules.clinics.domain.entities import ClinicStatus
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.domain.entities import PatientStatus
from app.modules.veterinarians.domain.entities import VeterinarianStatus
from app.shared.domain.errors import ForbiddenError, NotFoundError, ValidationError
from tests.attendances.fakes import (
    FakeAttendanceRepository,
    FakeAttendanceSequenceRepository,
    FakeAuditLogWriter,
    FakeClinicRepository,
    FakeClock,
    FakeExamRepository,
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
        id=uuid4(),
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

    def confirm_use_case(self) -> ConfirmAttendanceUseCase:
        return ConfirmAttendanceUseCase(
            attendances=self.attendances,
            attendance_sequences=self.attendance_sequences,
            clinics=self.clinics,
            veterinarians=self.veterinarians,
            veterinarian_clinics=self.veterinarian_clinics,
            patients=self.patients,
            exams=self.exams,
            audit=self.audit,
            clock=FakeClock(_NOW),
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
