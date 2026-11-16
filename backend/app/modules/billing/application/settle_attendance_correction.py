"""Billing side of `attendances.application.closure_settlement`.

`CREDIT` lowers what the clinic owes for the closure, `DEBIT` raises it. Every adjustment is
appended to a `CLOSED` closure (never edits its snapshot), audited with the correction's reason
and announced through the outbox, exactly like a manual adjustment.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.modules.attendances.application.closure_settlement import FinancialPosition
from app.modules.attendances.domain.entities import AttendanceRecord
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.billing.application.add_financial_adjustment import append_adjustment
from app.modules.billing.domain.entities import AdjustmentKind, ClosureStatus, MonthlyClosure
from app.modules.billing.domain.repositories import MonthlyClosureRepository
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.outbox.domain.repositories import OutboxEventRepository


class AttendanceCorrectionSettlement:
    def __init__(
        self,
        *,
        closures: MonthlyClosureRepository,
        audit: AuditLogWriter,
        outbox: OutboxEventRepository,
        clock: Clock,
    ) -> None:
        self._closures = closures
        self._audit = audit
        self._outbox = outbox
        self._clock = clock

    def settle(
        self,
        *,
        actor: ActorContext,
        attendance: AttendanceRecord,
        before: FinancialPosition,
        reason: str,
    ) -> None:
        label = f"Correção do atendimento {attendance.protocol_number}: {reason}"
        old = self._locked_closed(before.closure_id)

        if old is not None and not _moved_out_of(old, attendance):
            self._post(actor, old, attendance.grand_total - before.grand_total, label)
            return

        if old is not None:
            self._post(actor, old, -before.grand_total, f"{label} (saiu deste fechamento)")
        target = self._covering_closure(attendance)
        attendance.monthly_closure_id = target.id if target is not None else None
        if target is not None:
            self._post(actor, target, attendance.grand_total, f"{label} (entrou neste fechamento)")

    def _locked_closed(self, closure_id: UUID | None) -> MonthlyClosure | None:
        if closure_id is None:
            return None
        closure = self._closures.get_by_id_for_update(closure_id)
        if closure is None or closure.status is not ClosureStatus.CLOSED:
            return None
        return closure

    def _covering_closure(self, attendance: AttendanceRecord) -> MonthlyClosure | None:
        if attendance.service_date is None:
            return None
        found = self._closures.get_active_for_clinic_and_period(
            clinic_id=attendance.clinic_id,
            period_start=attendance.service_date,
            period_end=attendance.service_date,
        )
        return self._locked_closed(found.id) if found is not None else None

    def _post(
        self, actor: ActorContext, closure: MonthlyClosure, delta: Decimal, reason: str
    ) -> None:
        if delta == 0:
            return
        append_adjustment(
            closures=self._closures,
            audit=self._audit,
            outbox=self._outbox,
            clock=self._clock,
            actor=actor,
            closure=closure,
            closure_item_id=None,
            kind=AdjustmentKind.DEBIT if delta > 0 else AdjustmentKind.CREDIT,
            amount=abs(delta),
            reason=reason,
        )


def _moved_out_of(closure: MonthlyClosure, attendance: AttendanceRecord) -> bool:
    date_ = attendance.service_date
    return (
        attendance.clinic_id != closure.clinic_id
        or date_ is None
        or not (closure.period_start <= date_ <= closure.period_end)
    )
