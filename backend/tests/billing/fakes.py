"""In-memory fakes for the billing module — used by unit tests for use
cases (rule: mock only at an external boundary; a fake repository backing a
pure use-case test is not the repository-under-test, so this is fine per
.claude/rules/08-testing.md)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.modules.audit.domain.entities import AuditEntry
from app.modules.billing.domain.entities import (
    ClosureCandidateItem,
    ClosureStatus,
    CompetencePeriod,
    FinancialAdjustment,
    MonthlyClosure,
)
from app.modules.clinics.domain.entities import Clinic, ClinicStatus
from app.shared.outbox.domain.entities import OutboxEvent

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


class FakeClosureCandidateLockRepository:
    """Also records calls, so a test can assert the use case actually
    associated the right attendances with the closure — the fake IS allowed
    to hold that extra assertion state precisely because it isn't the
    repository under test (`.claude/rules/08-testing.md`)."""

    def __init__(self, candidates: list[ClosureCandidateItem] | None = None) -> None:
        self._candidates = candidates or []
        self.marked_attendance_ids: set[UUID] = set()
        self.marked_closure_id: UUID | None = None
        self.released_closure_ids: list[UUID] = []

    def list_candidates_for_update(
        self, *, clinic_id: UUID, period: CompetencePeriod
    ) -> list[ClosureCandidateItem]:
        return list(self._candidates)

    def mark_associated_with_closure(self, *, attendance_ids: set[UUID], closure_id: UUID) -> None:
        self.marked_attendance_ids |= attendance_ids
        self.marked_closure_id = closure_id

    def release_from_closure(self, *, closure_id: UUID) -> None:
        self.released_closure_ids.append(closure_id)


class FakeMonthlyClosureRepository:
    def __init__(self, active: MonthlyClosure | None = None) -> None:
        self._active = active
        self.added: list[MonthlyClosure] = []
        self.lock_calls: list[tuple[UUID, int, int]] = []
        self.updated: list[MonthlyClosure] = []
        self.adjustments: list[FinancialAdjustment] = []

    def acquire_active_lock(self, *, clinic_id: UUID, year: int, month: int) -> None:
        self.lock_calls.append((clinic_id, year, month))

    def get_active_for_clinic_and_period(
        self, *, clinic_id: UUID, year: int, month: int
    ) -> MonthlyClosure | None:
        if self._active is not None and self._active.status is ClosureStatus.CLOSED:
            return self._active
        return None

    def add(self, closure: MonthlyClosure) -> None:
        self.added.append(closure)

    def get_by_id(self, closure_id: UUID) -> MonthlyClosure | None:
        candidates = [*self.added, *([self._active] if self._active is not None else [])]
        return next((closure for closure in candidates if closure.id == closure_id), None)

    def get_by_id_for_update(self, closure_id: UUID) -> MonthlyClosure | None:
        return self.get_by_id(closure_id)

    def get_latest_for_clinic_and_period(
        self, *, clinic_id: UUID, year: int, month: int
    ) -> MonthlyClosure | None:
        candidates = [
            closure
            for closure in [*self.added, *([self._active] if self._active is not None else [])]
            if closure.clinic_id == clinic_id
            and closure.competence_year == year
            and closure.competence_month == month
        ]
        return max(candidates, key=lambda closure: closure.version, default=None)

    def update_status(self, closure: MonthlyClosure) -> None:
        self.updated.append(closure)

    def add_adjustment(self, adjustment: FinancialAdjustment) -> None:
        self.adjustments.append(adjustment)

    def list_page(
        self, *, clinic_id: UUID | None, page: int, page_size: int
    ) -> tuple[list[MonthlyClosure], int]:
        return list(self.added), len(self.added)


class FakeAuditLogWriter:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def record(self, entry: AuditEntry) -> None:
        self.entries.append(entry)


class FakeOutboxEventRepository:
    def __init__(self) -> None:
        self.events: list[OutboxEvent] = []

    def add(self, event: OutboxEvent) -> None:
        self.events.append(event)


def make_clinic(*, clinic_id: UUID, status: ClinicStatus = ClinicStatus.ACTIVE) -> Clinic:
    return Clinic(
        id=clinic_id, name="Clínica Teste", status=status, created_at=_SEED_AT, updated_at=_SEED_AT
    )
