from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.catalog.application.dtos import ExamDTO
from app.modules.catalog.application.mappers import exam_to_dto
from app.modules.catalog.domain.repositories import ExamRepository
from app.shared.application.authorization import ActorContext
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "catalog.read"
_PRICE_PERMISSION = "pricing.read"


@dataclass(frozen=True, kw_only=True)
class GetExamQuery:
    actor: ActorContext
    exam_id: UUID


class GetExamUseCase:
    def __init__(self, *, exams: ExamRepository) -> None:
        self._exams = exams

    def execute(self, query: GetExamQuery) -> ExamDTO:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        exam = self._exams.get_by_id(query.exam_id)
        if exam is None:
            raise NotFoundError("Exame não encontrado.")

        return exam_to_dto(exam, include_price=_PRICE_PERMISSION in query.actor.permissions)
