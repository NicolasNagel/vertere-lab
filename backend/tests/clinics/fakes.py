"""In-memory fakes for the clinics repository protocol — used by unit
tests for use cases (rule: mock only at an external boundary; a fake
repository backing a pure use-case test is not the repository-under-test,
so this is fine per .claude/rules/08-testing.md)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.audit.domain.entities import AuditEntry
from app.modules.clinics.domain.entities import Clinic, ClinicStatus


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


class FakeClinicRepository:
    def __init__(self) -> None:
        self._clinics: dict[UUID, Clinic] = {}

    def add(self, clinic: Clinic) -> None:
        self._clinics[clinic.id] = clinic

    def save(self, clinic: Clinic) -> None:
        clinic.row_version += 1
        self._clinics[clinic.id] = clinic

    def get_by_id(self, clinic_id: UUID) -> Clinic | None:
        return self._clinics.get(clinic_id)

    def get_by_tax_id(self, tax_id: str) -> Clinic | None:
        for clinic in self._clinics.values():
            if clinic.tax_id is not None and str(clinic.tax_id) == tax_id:
                return clinic
        return None

    def get_by_name(self, name: str) -> Clinic | None:
        for clinic in self._clinics.values():
            if clinic.name.lower() == name.lower():
                return clinic
        return None

    def list_all_names(self) -> dict[str, UUID]:
        return {clinic.name.lower(): clinic.id for clinic in self._clinics.values()}

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: ClinicStatus | None,
        search: str | None,
        clinic_ids: frozenset[UUID] | None = None,
    ) -> tuple[list[Clinic], int]:
        clinics = list(self._clinics.values())
        if clinic_ids is not None:
            clinics = [clinic for clinic in clinics if clinic.id in clinic_ids]
        if status is not None:
            clinics = [c for c in clinics if c.status == status]
        if search:
            needle = search.lower()
            clinics = [c for c in clinics if needle in c.name.lower()]
        return clinics, len(clinics)
