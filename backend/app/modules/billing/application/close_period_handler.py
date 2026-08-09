"""Atomic orchestration for closing a free-form billing period."""

from __future__ import annotations

from uuid import UUID

from app.modules.billing.application.close_monthly_period import (
    CloseMonthlyPeriodCommand,
    CloseMonthlyPeriodUseCase,
)
from app.modules.billing.application.dtos import MonthlyClosureDTO
from app.modules.billing.application.mappers import monthly_closure_to_dto
from app.modules.billing.application.uow import BillingUnitOfWork
from app.shared.application.clock import Clock
from app.shared.domain.errors import NotFoundError
from app.shared.idempotency.application.guard import IdempotencyGuard


class ClosePeriodHandler:
    def __init__(self, *, uow: BillingUnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(
        self, command: CloseMonthlyPeriodCommand, *, idempotency_key: str
    ) -> MonthlyClosureDTO:
        with self._uow:
            guard = IdempotencyGuard(records=self._uow.idempotency_records)
            outcome = guard.begin(
                actor_id=command.actor.id,
                operation=f"closures.close:access-version:{command.actor.row_version}",
                idempotency_key=idempotency_key,
                payload={
                    "clinic_id": str(command.clinic_id),
                    "period_start": command.period_start.isoformat(),
                    "period_end": command.period_end.isoformat(),
                },
                now=self._clock.now(),
            )
            if outcome.replayed_response is not None:
                _, body = outcome.replayed_response
                result = self._load_replayed_closure(body)
                self._uow.commit()
                return result

            result = CloseMonthlyPeriodUseCase(
                clinics=self._uow.clinics,
                candidates=self._uow.candidates,
                closures=self._uow.closures,
                audit=self._uow.audit,
                outbox=self._uow.outbox,
                clock=self._clock,
            ).execute(command)
            guard.complete(
                outcome.record_id,
                status_code=201,
                body={"id": str(result.id)},
                now=self._clock.now(),
            )
            self._uow.commit()
            return result

    def _load_replayed_closure(self, body: dict[str, object]) -> MonthlyClosureDTO:
        try:
            closure_id = UUID(str(body["id"]))
        except (KeyError, ValueError) as exc:
            raise NotFoundError("Resultado idempotente do fechamento não encontrado.") from exc
        closure = self._uow.closures.get_by_id(closure_id)
        if closure is None:
            raise NotFoundError("Resultado idempotente do fechamento não encontrado.")
        return monthly_closure_to_dto(closure)
