from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.billing.application.dtos import MonthlyClosureDTO
from app.modules.billing.application.mappers import monthly_closure_to_dto
from app.modules.billing.domain.repositories import (
    ClosureCandidateLockRepository,
    MonthlyClosureRepository,
)
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError
from app.shared.outbox.domain.entities import OutboxEvent
from app.shared.outbox.domain.repositories import OutboxEventRepository

_REQUIRED_PERMISSION = "closures.reopen"


@dataclass(frozen=True, kw_only=True)
class ReopenMonthlyClosureCommand:
    actor: ActorContext
    closure_id: UUID
    reason: str


class ReopenMonthlyClosureUseCase:
    def __init__(
        self,
        *,
        closures: MonthlyClosureRepository,
        candidates: ClosureCandidateLockRepository,
        audit: AuditLogWriter,
        outbox: OutboxEventRepository,
        clock: Clock,
    ) -> None:
        self._closures = closures
        self._candidates = candidates
        self._audit = audit
        self._outbox = outbox
        self._clock = clock

    def execute(self, command: ReopenMonthlyClosureCommand) -> MonthlyClosureDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        closure = self._closures.get_by_id(command.closure_id)
        if closure is None or not command.actor.can_access_clinic(closure.clinic_id):
            raise NotFoundError("Fechamento não encontrado.")

        self._closures.acquire_active_lock(clinic_id=closure.clinic_id)
        closure = self._closures.get_by_id_for_update(command.closure_id)
        if closure is None or not command.actor.can_access_clinic(closure.clinic_id):
            raise NotFoundError("Fechamento não encontrado.")
        before_status = closure.status.value
        closure.reopen(reopened_at=self._clock.now())
        self._closures.update_status(closure)
        self._candidates.release_from_closure(closure_id=closure.id)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="closures.reopened",
                entity_type="monthly_closure",
                entity_id=str(closure.id),
                before_state={"status": before_status, "version": closure.version},
                after_state={"status": closure.status.value, "version": closure.version},
                reason=command.reason,
            )
        )
        self._outbox.add(
            OutboxEvent(
                event_type="closures.reopened",
                payload={
                    "closure_id": str(closure.id),
                    "clinic_id": str(closure.clinic_id),
                    "competence_year": closure.competence_year,
                    "competence_month": closure.competence_month,
                },
            )
        )
        return monthly_closure_to_dto(closure)
