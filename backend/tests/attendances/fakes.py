"""In-memory fakes for the attendances module — used by unit tests for use
cases (rule: mock only at an external boundary; a fake repository backing a
pure use-case test is not the repository-under-test, so this is fine per
.claude/rules/testing.md)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.modules.attendances.domain.entities import AttendanceRecord, AttendanceStatus
from app.modules.audit.domain.entities import AuditEntry
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
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def record(self, entry: AuditEntry) -> None:
        self.entries.append(entry)


class FakeAttendanceRepository:
    def __init__(self) -> None:
        self._attendances: dict[UUID, AttendanceRecord] = {}

    def add(self, attendance: AttendanceRecord) -> None:
        self._attendances[attendance.id] = attendance

    def get_by_id(self, attendance_id: UUID) -> AttendanceRecord | None:
        return self._attendances.get(attendance_id)

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        clinic_id: UUID | None,
        veterinarian_id: UUID | None,
        patient_id: UUID | None,
        status: AttendanceStatus | None,
    ) -> tuple[list[AttendanceRecord], int]:
        items = list(self._attendances.values())
        if clinic_id is not None:
            items = [a for a in items if a.clinic_id == clinic_id]
        if veterinarian_id is not None:
            items = [a for a in items if a.veterinarian_id == veterinarian_id]
        if patient_id is not None:
            items = [a for a in items if a.patient_id == patient_id]
        if status is not None:
            items = [a for a in items if a.status == status]
        items.sort(key=lambda a: a.created_at, reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total


class FakeClinicRepository:
    def __init__(self, clinics: list[Clinic] | None = None) -> None:
        self._clinics: dict[UUID, Clinic] = {clinic.id: clinic for clinic in (clinics or [])}

    def get_by_id(self, clinic_id: UUID) -> Clinic | None:
        return self._clinics.get(clinic_id)

    def get_by_tax_id(self, tax_id: str) -> Clinic | None:
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
    ) -> tuple[list[Patient], int]:
        raise NotImplementedError


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
