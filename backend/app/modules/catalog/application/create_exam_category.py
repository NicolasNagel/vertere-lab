from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.application.dtos import ExamCategoryDTO
from app.modules.catalog.application.mappers import exam_category_to_dto
from app.modules.catalog.domain.entities import ExamCategory, ExamCategoryStatus
from app.modules.catalog.domain.errors import DuplicateExamCategoryNameError
from app.modules.catalog.domain.repositories import ExamCategoryRepository
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "catalog.manage"


def normalize_category_name(name: str) -> str:
    normalized = " ".join(name.split())
    if not normalized:
        raise ValueError("Nome da categoria não pode ser vazio.")
    return normalized


@dataclass(frozen=True, kw_only=True)
class CreateExamCategoryCommand:
    actor: ActorContext
    name: str


class CreateExamCategoryUseCase:
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

    def execute(self, command: CreateExamCategoryCommand) -> ExamCategoryDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        name = normalize_category_name(command.name)
        if self._categories.get_by_name(name) is not None:
            raise DuplicateExamCategoryNameError("Categoria já cadastrada com este nome.")

        now = self._clock.now()
        category = ExamCategory(
            id=uuid4(),
            name=name,
            status=ExamCategoryStatus.ACTIVE,
            created_by=command.actor.id,
            updated_by=command.actor.id,
            created_at=now,
            updated_at=now,
        )
        self._categories.add(category)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="exam_categories.created",
                entity_type="exam_category",
                entity_id=str(category.id),
                after_state={"name": category.name, "status": category.status.value},
            )
        )

        return exam_category_to_dto(category)
