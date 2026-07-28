"""In-memory fakes for the billing module — used by unit tests for use
cases (rule: mock only at an external boundary; a fake repository backing a
pure use-case test is not the repository-under-test, so this is fine per
.claude/rules/testing.md)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.modules.billing.domain.entities import ClosureCandidateItem, CompetencePeriod
from app.modules.clinics.domain.entities import Clinic, ClinicStatus

_SEED_AT = datetime(2026, 1, 1, tzinfo=UTC)


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


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
    ) -> tuple[list[Clinic], int]:
        raise NotImplementedError


class FakeClosurePreviewRepository:
    def __init__(self, candidates: list[ClosureCandidateItem] | None = None) -> None:
        self._candidates = candidates or []

    def list_candidates(
        self, *, clinic_id: UUID, period: CompetencePeriod
    ) -> list[ClosureCandidateItem]:
        return list(self._candidates)


def make_clinic(*, clinic_id: UUID, status: ClinicStatus = ClinicStatus.ACTIVE) -> Clinic:
    return Clinic(
        id=clinic_id, name="Clínica Teste", status=status, created_at=_SEED_AT, updated_at=_SEED_AT
    )
