from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.application.create_exam_category import normalize_category_name
from app.modules.catalog.application.dtos import ExamCategoryDTO
from app.modules.catalog.application.mappers import exam_category_to_dto
from app.modules.catalog.domain.entities import ExamCategoryStatus
from app.modules.catalog.domain.errors import DuplicateExamCategoryNameError
from app.modules.catalog.domain.repositories import ExamCategoryRepository
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.application.clock import Clock
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "catalog.manage"


@dataclass(frozen=True, kw_only=True)
class UpdateExamCategoryCommand:
    actor: AuthenticatedUserDTO
    category_id: UUID
    name: str
    status: str
    expected_row_version: int


class UpdateExamCategoryUseCase:
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

    def execute(self, command: UpdateExamCategoryCommand) -> ExamCategoryDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        category = self._categories.get_by_id(command.category_id)
        if category is None:
            raise NotFoundError("Categoria não encontrada.")

        if category.row_version != command.expected_row_version:
            raise ConflictError(
                "Esta categoria foi alterada por outra pessoa. Recarregue e tente de novo."
            )

        name = normalize_category_name(command.name)
        existing = self._categories.get_by_name(name)
        if existing is not None and existing.id != category.id:
            raise DuplicateExamCategoryNameError("Categoria já cadastrada com este nome.")

        before_state = {"name": category.name, "status": category.status.value}

        category.update_details(
            name=name,
            status=ExamCategoryStatus(command.status),
            updated_by=command.actor.id,
            now=self._clock.now(),
        )
        self._categories.save(category)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="exam_categories.updated",
                entity_type="exam_category",
                entity_id=str(category.id),
                before_state=before_state,
                after_state={"name": category.name, "status": category.status.value},
            )
        )

        return exam_category_to_dto(category)
