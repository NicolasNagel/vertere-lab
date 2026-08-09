from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.catalog.application.dtos import ExamCategoryDTO
from app.modules.catalog.application.mappers import exam_category_to_dto
from app.modules.catalog.domain.repositories import ExamCategoryRepository
from app.shared.application.authorization import ActorContext
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "catalog.read"


@dataclass(frozen=True, kw_only=True)
class GetExamCategoryQuery:
    actor: ActorContext
    category_id: UUID


class GetExamCategoryUseCase:
    def __init__(self, *, categories: ExamCategoryRepository) -> None:
        self._categories = categories

    def execute(self, query: GetExamCategoryQuery) -> ExamCategoryDTO:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        category = self._categories.get_by_id(query.category_id)
        if category is None:
            raise NotFoundError("Categoria não encontrada.")

        return exam_category_to_dto(category)
