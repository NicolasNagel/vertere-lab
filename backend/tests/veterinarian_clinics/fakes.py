"""In-memory fakes for the veterinarian-clinic link module — used by unit
tests for use cases (rule: mock only at an external boundary; a fake
repository backing a pure use-case test is not the repository-under-test,
so this is fine per .claude/rules/08-testing.md)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.audit.domain.entities import AuditEntry
from app.modules.clinics.domain.entities import Clinic
from app.modules.veterinarian_clinics.domain.entities import VeterinarianClinicLink
from app.modules.veterinarians.domain.entities import Veterinarian


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


class FakeVeterinarianRepository:
    def __init__(self, veterinarians: dict[UUID, Veterinarian] | None = None) -> None:
        self._veterinarians: dict[UUID, Veterinarian] = veterinarians or {}

    def add(self, veterinarian: Veterinarian) -> None:
        self._veterinarians[veterinarian.id] = veterinarian

    def get_by_id(self, veterinarian_id: UUID) -> Veterinarian | None:
        return self._veterinarians.get(veterinarian_id)

    def get_by_crmv(self, crmv: str) -> Veterinarian | None:
        for veterinarian in self._veterinarians.values():
            if str(veterinarian.crmv) == crmv:
                return veterinarian
        return None

    def get_by_name(self, name: str) -> Veterinarian | None:
        for veterinarian in self._veterinarians.values():
            if veterinarian.name.lower() == name.lower():
                return veterinarian
        return None

    def save(self, veterinarian: Veterinarian) -> None:
        self._veterinarians[veterinarian.id] = veterinarian

    def list_page(self, **kwargs: object) -> tuple[list[Veterinarian], int]:
        values = list(self._veterinarians.values())
        return values, len(values)


class FakeClinicRepository:
    def __init__(self, clinics: dict[UUID, Clinic] | None = None) -> None:
        self._clinics: dict[UUID, Clinic] = clinics or {}

    def add(self, clinic: Clinic) -> None:
        self._clinics[clinic.id] = clinic

    def get_by_id(self, clinic_id: UUID) -> Clinic | None:
        return self._clinics.get(clinic_id)

    def get_by_tax_id(self, tax_id: str) -> Clinic | None:
        return None

    def get_by_name(self, name: str) -> Clinic | None:
        for clinic in self._clinics.values():
            if clinic.name.lower() == name.lower():
                return clinic
        return None

    def list_all_names(self) -> dict[str, UUID]:
        return {clinic.name.lower(): clinic.id for clinic in self._clinics.values()}

    def save(self, clinic: Clinic) -> None:
        self._clinics[clinic.id] = clinic

    def list_page(self, **kwargs: object) -> tuple[list[Clinic], int]:
        values = list(self._clinics.values())
        return values, len(values)


class FakeVeterinarianClinicLinkRepository:
    def __init__(self) -> None:
        self._links: dict[UUID, VeterinarianClinicLink] = {}

    def get(self, veterinarian_id: UUID, clinic_id: UUID) -> VeterinarianClinicLink | None:
        for link in self._links.values():
            if link.veterinarian_id == veterinarian_id and link.clinic_id == clinic_id:
                return link
        return None

    def add(self, link: VeterinarianClinicLink) -> None:
        self._links[link.id] = link

    def delete(self, link: VeterinarianClinicLink) -> None:
        del self._links[link.id]

    def clear_primary_for_veterinarian(self, veterinarian_id: UUID) -> None:
        for link_id, link in list(self._links.items()):
            if link.veterinarian_id == veterinarian_id and link.primary_clinic:
                self._links[link_id] = VeterinarianClinicLink(
                    id=link.id,
                    veterinarian_id=link.veterinarian_id,
                    clinic_id=link.clinic_id,
                    primary_clinic=False,
                    created_by=link.created_by,
                    created_at=link.created_at,
                )

    def mark_primary(self, link_id: UUID) -> None:
        link = self._links[link_id]
        self._links[link_id] = VeterinarianClinicLink(
            id=link.id,
            veterinarian_id=link.veterinarian_id,
            clinic_id=link.clinic_id,
            primary_clinic=True,
            created_by=link.created_by,
            created_at=link.created_at,
        )

    def list_by_veterinarian(self, veterinarian_id: UUID) -> list[VeterinarianClinicLink]:
        return [link for link in self._links.values() if link.veterinarian_id == veterinarian_id]

    def list_by_clinic(self, clinic_id: UUID) -> list[VeterinarianClinicLink]:
        return [link for link in self._links.values() if link.clinic_id == clinic_id]

    def count_by_veterinarian(self, veterinarian_id: UUID) -> int:
        return len(self.list_by_veterinarian(veterinarian_id))
