"""Port for keeping closures consistent when a CONFIRMED attendance is corrected.

An attendance inside a closed closure can be edited (a mistake must be fixable), but the
closure snapshot never changes: the difference becomes an append-only financial adjustment
on that closure. The invariant that makes this work is that a closure's contribution for an
attendance always equals the attendance's live `grand_total` — snapshot plus every earlier
delta — so each correction only needs to settle `after - before`, and a move to another
clinic/competence reverses the whole `before` on the old closure and charges the whole
`after` on the new one. Implemented by the billing module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.modules.attendances.domain.entities import AttendanceRecord, AttendanceStatus
from app.shared.application.authorization import ActorContext


@dataclass(frozen=True, kw_only=True)
class FinancialPosition:
    """What an attendance weighed financially before the edit."""

    clinic_id: UUID
    service_date: date | None
    grand_total: Decimal
    closure_id: UUID | None

    @classmethod
    def of(cls, attendance: AttendanceRecord) -> FinancialPosition:
        return cls(
            clinic_id=attendance.clinic_id,
            service_date=attendance.service_date,
            grand_total=attendance.grand_total,
            closure_id=attendance.monthly_closure_id,
        )

    def needs_settlement(self, attendance: AttendanceRecord) -> bool:
        """Only a CONFIRMED attendance is billed. Settlement is needed when it sits in a
        closure, or when the edit moved it (clinic/date) — possibly into a closed period."""
        if attendance.status != AttendanceStatus.CONFIRMED:
            return False
        moved = (
            attendance.clinic_id != self.clinic_id or attendance.service_date != self.service_date
        )
        return self.closure_id is not None or moved


class ClosureSettlement(Protocol):
    def settle(
        self,
        *,
        actor: ActorContext,
        attendance: AttendanceRecord,
        before: FinancialPosition,
        reason: str,
    ) -> None:
        """Append the adjustments the edit implies and set `attendance.monthly_closure_id`
        to the closure it now belongs to (or `None`). Must run before the attendance is
        persisted."""
        ...
