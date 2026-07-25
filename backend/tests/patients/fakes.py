"""In-memory fakes for the patients module repository protocols — used by
unit tests for use cases (rule: mock only at an external boundary; a fake
repository backing a pure use-case test is not the repository-under-test,
so this is fine per .claude/rules/testing.md)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.audit.domain.entities import AuditEntry
from app.modules.patients.domain.entities import Patient, PatientStatus, Species


class FakeSpeciesRepository:
    def __init__(self, species: list[Species] | None = None) -> None:
        self._species = list(species or [])

    def list_all(self) -> list[Species]:
        return sorted(self._species, key=lambda item: item.name)


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


class FakePatientRepository:
    def __init__(self) -> None:
        self._patients: dict[UUID, Patient] = {}

    def add(self, patient: Patient) -> None:
        self._patients[patient.id] = patient

    def save(self, patient: Patient) -> None:
        patient.row_version += 1
        self._patients[patient.id] = patient

    def get_by_id(self, patient_id: UUID) -> Patient | None:
        return self._patients.get(patient_id)

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: PatientStatus | None,
        search: str | None,
    ) -> tuple[list[Patient], int]:
        patients = list(self._patients.values())
        if status is not None:
            patients = [p for p in patients if p.status == status]
        if search:
            needle = search.lower()
            patients = [
                p for p in patients if needle in p.name.lower() or needle in p.owner_name.lower()
            ]
        return patients, len(patients)
