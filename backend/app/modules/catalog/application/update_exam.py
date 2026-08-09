from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.application.dtos import ExamDTO
from app.modules.catalog.application.mappers import exam_to_dto
from app.modules.catalog.domain.entities import ExamStatus
from app.modules.catalog.domain.errors import DuplicateExamCodeError
from app.modules.catalog.domain.repositories import ExamCategoryRepository, ExamRepository
from app.modules.catalog.domain.value_objects import ExamCode
from app.modules.patients.domain.repositories import SpeciesRepository
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)

_REQUIRED_PERMISSION = "catalog.manage"
_PRICE_PERMISSION = "pricing.read"


@dataclass(frozen=True, kw_only=True)
class UpdateExamCommand:
    actor: ActorContext
    exam_id: UUID
    code: str
    name: str
    category_id: UUID
    price_base: Decimal
    description: str | None
    species_ids: frozenset[UUID]
    status: str
    expected_row_version: int


class UpdateExamUseCase:
    def __init__(
        self,
        *,
        exams: ExamRepository,
        categories: ExamCategoryRepository,
        species: SpeciesRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._exams = exams
        self._categories = categories
        self._species = species
        self._audit = audit
        self._clock = clock

    def execute(self, command: UpdateExamCommand) -> ExamDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        exam = self._exams.get_by_id(command.exam_id)
        if exam is None:
            raise NotFoundError("Exame não encontrado.")

        if exam.row_version != command.expected_row_version:
            raise ConflictError(
                "Este exame foi alterado por outra pessoa. Recarregue e tente de novo."
            )

        if self._categories.get_by_id(command.category_id) is None:
            raise NotFoundError("Categoria de exame não encontrada.")

        known_species_ids = {species.id for species in self._species.list_all()}
        if not command.species_ids <= known_species_ids:
            raise ValidationError("Uma ou mais espécies selecionadas não existem.")

        code = ExamCode(command.code)
        existing = self._exams.get_by_code(str(code))
        if existing is not None and existing.id != exam.id:
            raise DuplicateExamCodeError("Código de exame já cadastrado.")

        before_state = {"code": str(exam.code), "name": exam.name}

        try:
            exam.update_details(
                code=code,
                name=command.name,
                category_id=command.category_id,
                price_base=command.price_base,
                description=command.description,
                species_ids=command.species_ids,
                status=ExamStatus(command.status),
                updated_by=command.actor.id,
                now=self._clock.now(),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        self._exams.save(exam)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="exams.updated",
                entity_type="exam",
                entity_id=str(exam.id),
                before_state=before_state,
                after_state={"code": str(exam.code), "name": exam.name},
            )
        )

        return exam_to_dto(exam, include_price=_PRICE_PERMISSION in command.actor.permissions)
