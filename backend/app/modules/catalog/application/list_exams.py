from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.catalog.application.dtos import ExamDTO
from app.modules.catalog.application.mappers import exam_to_dto
from app.modules.catalog.domain.entities import ExamStatus
from app.modules.catalog.domain.repositories import ExamRepository
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.application.dtos import PageDTO
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "catalog.read"
_PRICE_PERMISSION = "pricing.read"


@dataclass(frozen=True, kw_only=True)
class ListExamsQuery:
    actor: AuthenticatedUserDTO
    page: int
    page_size: int
    status: ExamStatus | None = None
    category_id: UUID | None = None
    species_id: UUID | None = None
    search: str | None = None


class ListExamsUseCase:
    def __init__(self, *, exams: ExamRepository) -> None:
        self._exams = exams

    def execute(self, query: ListExamsQuery) -> PageDTO[ExamDTO]:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        exams, total = self._exams.list_page(
            page=query.page,
            page_size=query.page_size,
            status=query.status,
            category_id=query.category_id,
            species_id=query.species_id,
            search=query.search,
        )
        include_price = _PRICE_PERMISSION in query.actor.permissions
        return PageDTO(
            items=[exam_to_dto(exam, include_price=include_price) for exam in exams],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )
