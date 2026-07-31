"""Repository protocols for the billing module.

`ClosurePreviewRepository` stays read-only, used only by the prévia
(Incremento 4.1) — it never persists (`.claude/rules/13-monthly-closure.md`).
`ClosureCandidateLockRepository` is a separate protocol for the same
underlying query, used only by the close use case (Incremento 4.2), which
needs `SELECT ... FOR UPDATE` semantics the read-only preview must never
carry. `MonthlyClosureRepository` is the first writer in this module.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.billing.domain.entities import (
    ClosureCandidateItem,
    CompetencePeriod,
    MonthlyClosure,
)


class ClosurePreviewRepository(Protocol):
    def list_candidates(
        self, *, clinic_id: UUID, period: CompetencePeriod
    ) -> list[ClosureCandidateItem]: ...


class ClosureCandidateLockRepository(Protocol):
    def list_candidates_for_update(
        self, *, clinic_id: UUID, period: CompetencePeriod
    ) -> list[ClosureCandidateItem]:
        """Same shape as `ClosurePreviewRepository.list_candidates`, but
        takes `SELECT ... FOR UPDATE OF` the `attendances`/`attendance_exams`
        rows within the caller's transaction — `.claude/rules/13-monthly-closure.md`:
        "seleciona e bloqueia os itens elegíveis"."""
        ...

    def mark_associated_with_closure(self, *, attendance_ids: set[UUID], closure_id: UUID) -> None:
        """Sets `attendances.monthly_closure_id` for every attendance that
        contributed at least one eligible item — this is what activates the
        `AttendanceAlreadyClosedError` guard already enforced in
        `AttendanceRecord.cancel()`/`update_fields()`."""
        ...

    def release_from_closure(self, *, closure_id: UUID) -> None: ...


class MonthlyClosureRepository(Protocol):
    def acquire_active_lock(self, *, clinic_id: UUID, year: int, month: int) -> None:
        """`pg_advisory_xact_lock` scoped to this clinic+competence —
        released automatically at commit/rollback, never manually
        (`.claude/rules/03-database.md`: "fechamento usa advisory lock
        transacional... por clínica + competência")."""
        ...

    def get_active_for_clinic_and_period(
        self, *, clinic_id: UUID, year: int, month: int
    ) -> MonthlyClosure | None:
        """Only ever returns a `CLOSED` closure — there is no other status
        this slice produces (`Incremento 4.3` will add `REOPENED` handling
        here)."""
        ...

    def add(self, closure: MonthlyClosure) -> None: ...

    def get_by_id(self, closure_id: UUID) -> MonthlyClosure | None: ...

    def get_by_id_for_update(self, closure_id: UUID) -> MonthlyClosure | None: ...

    def get_latest_for_clinic_and_period(
        self, *, clinic_id: UUID, year: int, month: int
    ) -> MonthlyClosure | None: ...

    def update_status(self, closure: MonthlyClosure) -> None: ...

    def list_page(
        self, *, clinic_id: UUID | None, page: int, page_size: int
    ) -> tuple[list[MonthlyClosure], int]: ...
