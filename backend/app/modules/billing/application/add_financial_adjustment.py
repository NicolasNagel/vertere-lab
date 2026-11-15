from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.billing.application.dtos import FinancialAdjustmentDTO
from app.modules.billing.application.mappers import financial_adjustment_to_dto
from app.modules.billing.domain.entities import (
    AdjustmentKind,
    ClosureStatus,
    FinancialAdjustment,
    MonthlyClosure,
)
from app.modules.billing.domain.repositories import MonthlyClosureRepository
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import (
    ForbiddenError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError,
)
from app.shared.domain.money import round_currency
from app.shared.outbox.domain.entities import OutboxEvent
from app.shared.outbox.domain.repositories import OutboxEventRepository

_REQUIRED_PERMISSION = "closures.adjust"


@dataclass(frozen=True, kw_only=True)
class AddFinancialAdjustmentCommand:
    actor: ActorContext
    closure_id: UUID
    closure_item_id: UUID | None
    kind: AdjustmentKind
    amount: Decimal
    reason: str


class AddFinancialAdjustmentUseCase:
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

    def execute(self, command: AddFinancialAdjustmentCommand) -> FinancialAdjustmentDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        closure = self._closures.get_by_id_for_update(command.closure_id)
        if closure is None or not command.actor.can_access_clinic(closure.clinic_id):
            raise NotFoundError("Fechamento não encontrado.")
        if closure.status is not ClosureStatus.CLOSED:
            raise InvalidStateTransitionError(
                "Ajustes só podem ser adicionados a um fechamento fechado."
            )
        if command.closure_item_id is not None and all(
            item.id != command.closure_item_id for item in closure.items
        ):
            raise ValidationError("O item informado não pertence a este fechamento.")

        adjustment = append_adjustment(
            closures=self._closures,
            audit=self._audit,
            outbox=self._outbox,
            clock=self._clock,
            actor=command.actor,
            closure=closure,
            closure_item_id=command.closure_item_id,
            kind=command.kind,
            amount=command.amount,
            reason=command.reason,
        )
        return financial_adjustment_to_dto(adjustment)


def append_adjustment(
    *,
    closures: MonthlyClosureRepository,
    audit: AuditLogWriter,
    outbox: OutboxEventRepository,
    clock: Clock,
    actor: ActorContext,
    closure: MonthlyClosure,
    closure_item_id: UUID | None,
    kind: AdjustmentKind,
    amount: Decimal,
    reason: str,
) -> FinancialAdjustment:
    """Append one adjustment to a `CLOSED` closure with its audit entry and outbox event.
    Shared by the manual endpoint and by corrections of closed attendances."""
    adjustment = FinancialAdjustment(
        id=uuid4(),
        monthly_closure_id=closure.id,
        monthly_closure_item_id=closure_item_id,
        kind=kind,
        amount=round_currency(amount),
        reason=reason,
        created_by=actor.id,
        created_at=clock.now(),
    )
    closures.add_adjustment(adjustment)
    audit.record(
        AuditEntry(
            actor_user_id=actor.id,
            actor_scope=ActorScope(actor.role_scope),
            action="closures.adjusted",
            entity_type="financial_adjustment",
            entity_id=str(adjustment.id),
            after_state={
                "closure_id": str(closure.id),
                "kind": adjustment.kind.value,
                "amount": str(adjustment.amount),
            },
            reason=reason,
        )
    )
    outbox.add(
        OutboxEvent(
            event_type="closures.adjusted",
            payload={
                "adjustment_id": str(adjustment.id),
                "closure_id": str(closure.id),
                "kind": adjustment.kind.value,
                "amount": str(adjustment.amount),
            },
        )
    )
    return adjustment
