"""In-memory fakes for the attendances module — used by unit tests for use
cases (rule: mock only at an external boundary; a fake repository backing a
pure use-case test is not the repository-under-test, so this is fine per
.claude/rules/08-testing.md)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.modules.attendances.application.closure_settlement import FinancialPosition
from app.modules.attendances.domain.entities import (
    AttendanceRecord,
    AttendanceStatus,
    ClinicFeeRule,
    OnCallFeeSetting,
    ServiceLevel,
    UrgencyFeeSetting,
)
from app.modules.audit.domain.entities import AuditEntry
from app.modules.catalog.domain.entities import Exam, ExamStatus
from app.modules.catalog.domain.value_objects import ExamCode
from app.modules.clinics.domain.entities import Clinic, ClinicStatus
from app.modules.patients.domain.entities import Patient, PatientSex, PatientStatus
from app.modules.veterinarian_clinics.domain.entities import VeterinarianClinicLink
from app.modules.veterinarians.domain.entities import Veterinarian, VeterinarianStatus
from app.modules.veterinarians.domain.value_objects import Crmv

_SEED_AT = datetime(2026, 1, 1, tzinfo=UTC)


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class FakeAuditLogWriter:
    """Also implements `AuditLogReader` — same in-memory store backs both
    sides in tests, unlike production where writer/reader are separate
    SQLAlchemy classes over the same table."""

    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def record(self, entry: AuditEntry) -> None:
        self.entries.append(entry)

    def list_for_entity(
        self, *, entity_type: str, entity_id: str, page: int, page_size: int
    ) -> tuple[list[AuditEntry], int]:
        matches = [
            e for e in self.entries if e.entity_type == entity_type and e.entity_id == entity_id
        ]
        matches.sort(key=lambda e: e.occurred_at, reverse=True)
        total = len(matches)
        start = (page - 1) * page_size
        return matches[start : start + page_size], total


class FakeAttendanceRepository:
    def __init__(self) -> None:
        self._attendances: dict[UUID, AttendanceRecord] = {}

    def add(self, attendance: AttendanceRecord) -> None:
        self._attendances[attendance.id] = attendance

    def update(self, attendance: AttendanceRecord) -> None:
        self._attendances[attendance.id] = attendance

    def get_by_id(self, attendance_id: UUID) -> AttendanceRecord | None:
        return self._attendances.get(attendance_id)

    def get_by_legacy_source(
        self, *, import_batch_id: UUID, source_row_number: int
    ) -> AttendanceRecord | None:
        return next(
            (
                a
                for a in self._attendances.values()
                if a.import_batch_id == import_batch_id
                and a.legacy_source_row_number == source_row_number
            ),
            None,
        )

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        clinic_id: UUID | None,
        veterinarian_id: UUID | None,
        patient_id: UUID | None,
        status: AttendanceStatus | None,
        service_level: ServiceLevel | None,
        protocol_number: str | None,
        owner_name: str | None,
        service_date_from: date | None,
        service_date_to: date | None,
        clinic_ids: frozenset[UUID] | None = None,
    ) -> tuple[list[AttendanceRecord], int]:
        items = list(self._attendances.values())
        if clinic_ids is not None:
            items = [item for item in items if item.clinic_id in clinic_ids]
        if clinic_id is not None:
            items = [a for a in items if a.clinic_id == clinic_id]
        if veterinarian_id is not None:
            items = [a for a in items if a.veterinarian_id == veterinarian_id]
        if patient_id is not None:
            items = [a for a in items if a.patient_id == patient_id]
        if status is not None:
            items = [a for a in items if a.status == status]
        if service_level is not None:
            items = [a for a in items if a.service_level == service_level]
        if protocol_number:
            items = [a for a in items if protocol_number in (a.protocol_number or "")]
        # Owner lives in the patient repository; the integration repository
        # test covers that join. This fake deliberately has no patient graph.
        if owner_name:
            items = []
        if service_date_from is not None:
            items = [
                a
                for a in items
                if a.service_date is not None and a.service_date >= service_date_from
            ]
        if service_date_to is not None:
            items = [
                a for a in items if a.service_date is not None and a.service_date <= service_date_to
            ]
        items.sort(key=lambda a: a.created_at, reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    def _filtered(
        self,
        *,
        clinic_id: UUID | None,
        veterinarian_id: UUID | None,
        service_level: ServiceLevel | None,
        protocol_number: str | None,
        owner_name: str | None,
        service_date_from: date | None,
        service_date_to: date | None,
        clinic_ids: frozenset[UUID] | None = None,
    ) -> list[AttendanceRecord]:
        items = list(self._attendances.values())
        if clinic_ids is not None:
            items = [item for item in items if item.clinic_id in clinic_ids]
        if clinic_id is not None:
            items = [a for a in items if a.clinic_id == clinic_id]
        if veterinarian_id is not None:
            items = [a for a in items if a.veterinarian_id == veterinarian_id]
        if service_level is not None:
            items = [a for a in items if a.service_level == service_level]
        if protocol_number:
            items = [a for a in items if protocol_number in (a.protocol_number or "")]
        if owner_name:
            items = []
        if service_date_from is not None:
            items = [
                a
                for a in items
                if a.service_date is not None and a.service_date >= service_date_from
            ]
        if service_date_to is not None:
            items = [
                a for a in items if a.service_date is not None and a.service_date <= service_date_to
            ]
        return items

    def count_by_status(self, **filters: Any) -> dict[AttendanceStatus, int]:
        counts: dict[AttendanceStatus, int] = {}
        for attendance in self._filtered(**filters):
            counts[attendance.status] = counts.get(attendance.status, 0) + 1
        return counts

    def sum_billed_total(self, **filters: Any) -> Decimal:
        unbilled = {AttendanceStatus.DRAFT, AttendanceStatus.CANCELLED}
        return sum(
            (a.grand_total for a in self._filtered(**filters) if a.status not in unbilled),
            Decimal("0"),
        )


class FakeClinicRepository:
    def __init__(self, clinics: list[Clinic] | None = None) -> None:
        self._clinics: dict[UUID, Clinic] = {clinic.id: clinic for clinic in (clinics or [])}

    def get_by_id(self, clinic_id: UUID) -> Clinic | None:
        return self._clinics.get(clinic_id)

    def get_by_tax_id(self, tax_id: str) -> Clinic | None:
        raise NotImplementedError

    def get_by_name(self, name: str) -> Clinic | None:
        raise NotImplementedError

    def list_all_names(self) -> dict[str, UUID]:
        raise NotImplementedError

    def add(self, clinic: Clinic) -> None:
        raise NotImplementedError

    def save(self, clinic: Clinic) -> None:
        raise NotImplementedError

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: ClinicStatus | None,
        search: str | None,
        clinic_ids: frozenset[UUID] | None = None,
    ) -> tuple[list[Clinic], int]:
        raise NotImplementedError


class FakeVeterinarianRepository:
    def __init__(self, veterinarians: list[Veterinarian] | None = None) -> None:
        self._veterinarians: dict[UUID, Veterinarian] = {
            vet.id: vet for vet in (veterinarians or [])
        }

    def get_by_id(self, veterinarian_id: UUID) -> Veterinarian | None:
        return self._veterinarians.get(veterinarian_id)

    def get_by_crmv(self, crmv: str) -> Veterinarian | None:
        raise NotImplementedError

    def get_by_name(self, name: str) -> Veterinarian | None:
        raise NotImplementedError

    def is_linked_to_any_clinic(self, veterinarian_id: UUID, clinic_ids: frozenset[UUID]) -> bool:
        raise NotImplementedError

    def add(self, veterinarian: Veterinarian) -> None:
        raise NotImplementedError

    def save(self, veterinarian: Veterinarian) -> None:
        raise NotImplementedError

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: VeterinarianStatus | None,
        is_autonomous: bool | None,
        search: str | None,
        available_for_clinic_id: UUID | None = None,
        allowed_clinic_ids: frozenset[UUID] | None = None,
    ) -> tuple[list[Veterinarian], int]:
        raise NotImplementedError


class FakeVeterinarianClinicLinkRepository:
    def __init__(self, links: set[tuple[UUID, UUID]] | None = None) -> None:
        self._links = links or set()

    def get(self, veterinarian_id: UUID, clinic_id: UUID) -> VeterinarianClinicLink | None:
        if (veterinarian_id, clinic_id) not in self._links:
            return None
        return VeterinarianClinicLink(
            id=UUID(int=0),
            veterinarian_id=veterinarian_id,
            clinic_id=clinic_id,
            primary_clinic=False,
            created_by=None,
            created_at=_SEED_AT,
        )

    def add(self, link: VeterinarianClinicLink) -> None:
        raise NotImplementedError

    def delete(self, link: VeterinarianClinicLink) -> None:
        raise NotImplementedError

    def clear_primary_for_veterinarian(self, veterinarian_id: UUID) -> None:
        raise NotImplementedError

    def mark_primary(self, link_id: UUID) -> None:
        raise NotImplementedError

    def list_by_veterinarian(self, veterinarian_id: UUID) -> list[VeterinarianClinicLink]:
        raise NotImplementedError

    def list_by_clinic(self, clinic_id: UUID) -> list[VeterinarianClinicLink]:
        raise NotImplementedError

    def count_by_veterinarian(self, veterinarian_id: UUID) -> int:
        raise NotImplementedError


class FakePatientRepository:
    def __init__(self, patients: list[Patient] | None = None) -> None:
        self._patients: dict[UUID, Patient] = {patient.id: patient for patient in (patients or [])}

    def get_by_id(self, patient_id: UUID) -> Patient | None:
        return self._patients.get(patient_id)

    def get_by_owner_and_name(self, *, owner_name: str, name: str) -> Patient | None:
        raise NotImplementedError

    def add(self, patient: Patient) -> None:
        raise NotImplementedError

    def save(self, patient: Patient) -> None:
        raise NotImplementedError

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: PatientStatus | None,
        search: str | None,
        clinic_ids: frozenset[UUID] | None = None,
        clinic_id: UUID | None = None,
    ) -> tuple[list[Patient], int]:
        raise NotImplementedError


class FakeExamRepository:
    def __init__(self, exams: list[Exam] | None = None) -> None:
        self._exams: dict[UUID, Exam] = {exam.id: exam for exam in (exams or [])}

    def get_by_id(self, exam_id: UUID) -> Exam | None:
        return self._exams.get(exam_id)

    def get_by_code(self, code: str) -> Exam | None:
        raise NotImplementedError

    def get_many_by_ids(self, exam_ids: list[UUID]) -> list[Exam]:
        return [self._exams[exam_id] for exam_id in exam_ids if exam_id in self._exams]

    def list_active_panels_containing(self, exam_id: UUID) -> list[Exam]:
        return [e for e in self._exams.values() if exam_id in e.component_ids]

    def list_all_names(self) -> dict[str, UUID]:
        return {exam.name.casefold(): exam.id for exam in self._exams.values()}

    def add(self, exam: Exam) -> None:
        raise NotImplementedError

    def save(self, exam: Exam) -> None:
        raise NotImplementedError

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: ExamStatus | None,
        category_id: UUID | None,
        species_id: UUID | None,
        search: str | None,
    ) -> tuple[list[Exam], int]:
        raise NotImplementedError


class FakeAttendanceSequenceRepository:
    def __init__(self) -> None:
        self._last_by_year: dict[int, int] = {}

    def next_sequence(self, year: int) -> int:
        self._last_by_year[year] = self._last_by_year.get(year, 0) + 1
        return self._last_by_year[year]


class FakeOnCallFeeSettingRepository:
    """Seeded with the amounts in effect before this became configurable
    (migration 0031's seed values) so existing confirm/preview tests that
    assert on `Decimal("100.00")`/`Decimal("150.00")` keep working unchanged.
    """

    def __init__(self, settings: list[OnCallFeeSetting] | None = None) -> None:
        self._settings: dict[ServiceLevel, OnCallFeeSetting] = {
            setting.service_level: setting
            for setting in (
                settings
                if settings is not None
                else [
                    make_on_call_fee_setting(
                        service_level=ServiceLevel.PLANTAO_NORMAL, fee_amount=Decimal("100.00")
                    ),
                    make_on_call_fee_setting(
                        service_level=ServiceLevel.PLANTAO_ESPECIAL, fee_amount=Decimal("150.00")
                    ),
                ]
            )
        }

    def get_by_service_level(self, service_level: ServiceLevel) -> OnCallFeeSetting | None:
        return self._settings.get(service_level)

    def list_all(self) -> list[OnCallFeeSetting]:
        return list(self._settings.values())

    def update(self, setting: OnCallFeeSetting) -> None:
        self._settings[setting.service_level] = setting


class FakeUrgencyFeeSettingRepository:
    def __init__(self, fee_amount: Decimal = Decimal("0.00")) -> None:
        self._setting: UrgencyFeeSetting | None = UrgencyFeeSetting(
            id=UUID(int=777), fee_amount=fee_amount, updated_at=_SEED_AT
        )

    def get(self) -> UrgencyFeeSetting | None:
        return self._setting

    def update(self, setting: UrgencyFeeSetting) -> None:
        self._setting = setting


class FakeClinicFeeRuleRepository:
    def __init__(self, rules: list[ClinicFeeRule] | None = None) -> None:
        self.rules: dict[UUID, ClinicFeeRule] = {rule.id: rule for rule in rules or []}

    def get_by_id(self, rule_id: UUID) -> ClinicFeeRule | None:
        return self.rules.get(rule_id)

    def list_rules(self, *, clinic_id: UUID | None, include_inactive: bool) -> list[ClinicFeeRule]:
        return [
            rule
            for rule in self.rules.values()
            if (clinic_id is None or rule.clinic_id == clinic_id)
            and (include_inactive or rule.is_active)
        ]

    def list_applicable(self, *, clinic_id: UUID, service_date: date) -> list[ClinicFeeRule]:
        return [
            rule
            for rule in self.rules.values()
            if rule.clinic_id == clinic_id and rule.applies_on(service_date)
        ]

    def add(self, rule: ClinicFeeRule) -> None:
        self.rules[rule.id] = rule

    def update(self, rule: ClinicFeeRule) -> None:
        self.rules[rule.id] = rule


def make_clinic(*, clinic_id: UUID, status: ClinicStatus = ClinicStatus.ACTIVE) -> Clinic:
    return Clinic(
        id=clinic_id, name="Clínica Teste", status=status, created_at=_SEED_AT, updated_at=_SEED_AT
    )


def make_veterinarian(
    *,
    veterinarian_id: UUID,
    is_autonomous: bool = True,
    status: VeterinarianStatus = VeterinarianStatus.ACTIVE,
) -> Veterinarian:
    return Veterinarian(
        id=veterinarian_id,
        name="Dr. Teste",
        crmv=Crmv("CRMV-SC 00001"),
        is_autonomous=is_autonomous,
        status=status,
        created_at=_SEED_AT,
        updated_at=_SEED_AT,
    )


def make_patient(*, patient_id: UUID, status: PatientStatus = PatientStatus.ACTIVE) -> Patient:
    return Patient(
        id=patient_id,
        name="Rex",
        species_id=UUID(int=1),
        sex=PatientSex.MALE,
        breed=None,
        age_description=None,
        owner_name="Maria Souza",
        owner_phone=None,
        owner_document=None,
        notes=None,
        status=status,
        created_at=_SEED_AT,
        updated_at=_SEED_AT,
    )


def make_exam(
    *,
    exam_id: UUID,
    price_base: Decimal = Decimal("100.00"),
    status: ExamStatus = ExamStatus.ACTIVE,
) -> Exam:
    return Exam(
        id=exam_id,
        code=ExamCode("EX-001"),
        name="Hemograma",
        category_id=UUID(int=2),
        price_base=price_base,
        species_ids=frozenset({UUID(int=1)}),
        status=status,
        created_at=_SEED_AT,
        updated_at=_SEED_AT,
    )


def make_on_call_fee_setting(
    *,
    service_level: ServiceLevel,
    fee_amount: Decimal,
    schedule_label: str = "",
    row_version: int = 1,
) -> OnCallFeeSetting:
    return OnCallFeeSetting(
        id=UUID(int=hash(service_level) & ((1 << 128) - 1)),
        service_level=service_level,
        fee_amount=fee_amount,
        schedule_label=schedule_label,
        updated_at=_SEED_AT,
        row_version=row_version,
    )


class FakeClosureSettlement:
    """Records settlements instead of touching a closure (billing has its own tests)."""

    def __init__(self) -> None:
        self.calls: list[tuple[UUID | None, Decimal, Decimal]] = []

    def settle(
        self,
        *,
        actor: object,
        attendance: AttendanceRecord,
        before: FinancialPosition,
        reason: str,
    ) -> None:
        self.calls.append((before.closure_id, before.grand_total, attendance.grand_total))
