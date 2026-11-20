"""In-memory fakes for the veterinarians repository protocol — used by unit
tests for use cases (rule: mock only at an external boundary; a fake
repository backing a pure use-case test is not the repository-under-test,
so this is fine per .claude/rules/08-testing.md)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.audit.domain.entities import AuditEntry
from app.modules.veterinarians.domain.entities import Veterinarian, VeterinarianStatus


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
    def __init__(self) -> None:
        self._veterinarians: dict[UUID, Veterinarian] = {}
        self.linked_clinics: dict[UUID, set[UUID]] = {}

    def linked_clinic_ids(self, veterinarian_id: UUID) -> frozenset[UUID]:
        return frozenset(self.linked_clinics.get(veterinarian_id, set()))

    def is_linked_to_any_clinic(self, veterinarian_id: UUID, clinic_ids: frozenset[UUID]) -> bool:
        return bool(self.linked_clinics.get(veterinarian_id, set()) & clinic_ids)

    def add(self, veterinarian: Veterinarian) -> None:
        self._veterinarians[veterinarian.id] = veterinarian

    def save(self, veterinarian: Veterinarian) -> None:
        veterinarian.row_version += 1
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
        veterinarians = list(self._veterinarians.values())
        if status is not None:
            veterinarians = [v for v in veterinarians if v.status == status]
        if is_autonomous is not None:
            veterinarians = [v for v in veterinarians if v.is_autonomous == is_autonomous]
        if search:
            needle = search.lower()
            veterinarians = [v for v in veterinarians if needle in v.name.lower()]
        # `available_for_clinic_id`/`allowed_clinic_ids` não são modelados
        # neste fake (não há vínculos de clínica aqui) — cobertura real do
        # filtro fica para o teste de integração com Postgres real.
        return veterinarians, len(veterinarians)
