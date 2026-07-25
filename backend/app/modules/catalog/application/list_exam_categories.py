from __future__ import annotations

from dataclasses import dataclass

from app.modules.catalog.application.dtos import ExamCategoryDTO
from app.modules.catalog.application.mappers import exam_category_to_dto
from app.modules.catalog.domain.entities import ExamCategoryStatus
from app.modules.catalog.domain.repositories import ExamCategoryRepository
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.application.dtos import PageDTO
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "catalog.read"


@dataclass(frozen=True, kw_only=True)
class ListExamCategoriesQuery:
    actor: AuthenticatedUserDTO
    page: int
    page_size: int
    status: ExamCategoryStatus | None = None
    search: str | None = None


class ListExamCategoriesUseCase:
    def __init__(self, *, categories: ExamCategoryRepository) -> None:
        self._categories = categories

    def execute(self, query: ListExamCategoriesQuery) -> PageDTO[ExamCategoryDTO]:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        categories, total = self._categories.list_page(
            page=query.page,
            page_size=query.page_size,
            status=query.status,
            search=query.search,
        )
        return PageDTO(
            items=[exam_category_to_dto(category) for category in categories],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )
