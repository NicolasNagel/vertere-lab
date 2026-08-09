"""Unpaginated list of active categories — feeds the category select in the
Exam form (`frontend/src/features/catalog/`), not a listing screen of its
own."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.catalog.application.dtos import ExamCategoryDTO
from app.modules.catalog.application.mappers import exam_category_to_dto
from app.modules.catalog.domain.repositories import ExamCategoryRepository
from app.shared.application.authorization import ActorContext
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "catalog.read"


@dataclass(frozen=True, kw_only=True)
class ListActiveExamCategoriesQuery:
    actor: ActorContext


class ListActiveExamCategoriesUseCase:
    def __init__(self, *, categories: ExamCategoryRepository) -> None:
        self._categories = categories

    def execute(self, query: ListActiveExamCategoriesQuery) -> list[ExamCategoryDTO]:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        return [exam_category_to_dto(category) for category in self._categories.list_all_active()]
