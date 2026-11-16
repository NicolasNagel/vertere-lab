from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.application.dtos import ExamCategoryDTO
from app.modules.catalog.application.mappers import exam_category_to_dto
from app.modules.catalog.domain.repositories import ExamCategoryRepository
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "catalog.manage"


@dataclass(frozen=True, kw_only=True)
class DeactivateExamCategoryCommand:
    actor: ActorContext
    category_id: UUID


class DeactivateExamCategoryUseCase:
    """Soft delete only — inactivating a category must never erase catalog
    history (rule: .claude/rules/01-product-domain.md, "Inative em vez de
    apagar")."""

    def __init__(
        self,
        *,
        categories: ExamCategoryRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._categories = categories
        self._audit = audit
        self._clock = clock

    def execute(self, command: DeactivateExamCategoryCommand) -> ExamCategoryDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        category = self._categories.get_by_id(command.category_id)
        if category is None:
            raise NotFoundError("Categoria não encontrada.")

        before_status = category.status.value
        category.deactivate(updated_by=command.actor.id, now=self._clock.now())
        self._categories.save(category)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="exam_categories.deactivated",
                entity_type="exam_category",
                entity_id=str(category.id),
                before_state={"status": before_status},
                after_state={"status": category.status.value},
            )
        )

        return exam_category_to_dto(category)
