"""Atomic handlers for billing mutations other than period closure."""

from __future__ import annotations

from app.modules.billing.application.add_financial_adjustment import (
    AddFinancialAdjustmentCommand,
    AddFinancialAdjustmentUseCase,
)
from app.modules.billing.application.dtos import FinancialAdjustmentDTO, MonthlyClosureDTO
from app.modules.billing.application.reopen_monthly_closure import (
    ReopenMonthlyClosureCommand,
    ReopenMonthlyClosureUseCase,
)
from app.modules.billing.application.uow import BillingUnitOfWork
from app.shared.application.clock import Clock


def handle_reopen_monthly_closure(
    *,
    uow: BillingUnitOfWork,
    command: ReopenMonthlyClosureCommand,
    clock: Clock,
) -> MonthlyClosureDTO:
    with uow:
        result = ReopenMonthlyClosureUseCase(
            closures=uow.closures,
            candidates=uow.candidates,
            audit=uow.audit,
            outbox=uow.outbox,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result


def handle_add_financial_adjustment(
    *,
    uow: BillingUnitOfWork,
    command: AddFinancialAdjustmentCommand,
    clock: Clock,
) -> FinancialAdjustmentDTO:
    with uow:
        result = AddFinancialAdjustmentUseCase(
            closures=uow.closures,
            audit=uow.audit,
            outbox=uow.outbox,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result
