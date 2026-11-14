from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.application.dtos import ExamDTO
from app.modules.catalog.application.mappers import exam_to_dto
from app.modules.catalog.domain.repositories import ExamRepository
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "catalog.manage"
_PRICE_PERMISSION = "pricing.read"


@dataclass(frozen=True, kw_only=True)
class DeactivateExamCommand:
    actor: ActorContext
    exam_id: UUID


class DeactivateExamUseCase:
    """Soft delete only — inactivating an exam must never erase catalog
    history or the price a past attendance already snapshotted (rule:
    .claude/rules/01-product-domain.md, "Inative em vez de apagar")."""

    def __init__(
        self,
        *,
        exams: ExamRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._exams = exams
        self._audit = audit
        self._clock = clock

    def execute(self, command: DeactivateExamCommand) -> ExamDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        exam = self._exams.get_by_id(command.exam_id)
        if exam is None:
            raise NotFoundError("Exame não encontrado.")

        before_status = exam.status.value
        exam.deactivate(updated_by=command.actor.id, now=self._clock.now())
        self._exams.save(exam)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="exams.deactivated",
                entity_type="exam",
                entity_id=str(exam.id),
                before_state={"status": before_status},
                after_state={"status": exam.status.value},
            )
        )

        return exam_to_dto(exam, include_price=_PRICE_PERMISSION in command.actor.permissions)
