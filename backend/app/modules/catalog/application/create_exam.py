"""Create an Exam.

Price is only visible in the returned DTO when the actor has `pricing.read`
(spec's "VIEW_EXAM_PRICES", mapped to the real permission catalog — see
ADR-005). Category and species existence are validated against their own
repositories before persisting, same pattern as
`app/modules/veterinarian_clinics/application/link_veterinarian_to_clinic.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.application.dtos import ExamDTO
from app.modules.catalog.application.exam_code_generator import (
    ExamCodeGenerator,
    generate_exam_code,
)
from app.modules.catalog.application.mappers import exam_to_dto
from app.modules.catalog.application.panel_components import validate_panel_components
from app.modules.catalog.domain.entities import Exam, ExamStatus
from app.modules.catalog.domain.errors import DuplicateExamCodeError
from app.modules.catalog.domain.repositories import ExamCategoryRepository, ExamRepository
from app.modules.catalog.domain.value_objects import ExamCode
from app.modules.patients.domain.repositories import SpeciesRepository
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError, ValidationError

_REQUIRED_PERMISSION = "catalog.manage"
_PRICE_MANAGE_PERMISSION = "pricing.manage"
_PRICE_PERMISSION = "pricing.read"


@dataclass(frozen=True, kw_only=True)
class CreateExamCommand:
    actor: ActorContext
    name: str
    category_id: UUID
    price_base: Decimal
    description: str | None
    species_ids: frozenset[UUID]
    component_exam_ids: tuple[UUID, ...] = ()


class CreateExamUseCase:
    def __init__(
        self,
        *,
        exams: ExamRepository,
        categories: ExamCategoryRepository,
        species: SpeciesRepository,
        audit: AuditLogWriter,
        clock: Clock,
        code_generator: ExamCodeGenerator = generate_exam_code,
    ) -> None:
        self._exams = exams
        self._categories = categories
        self._species = species
        self._audit = audit
        self._clock = clock
        self._code_generator = code_generator

    def execute(self, command: CreateExamCommand) -> ExamDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")
        if _PRICE_MANAGE_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_PRICE_MANAGE_PERMISSION}")

        if self._categories.get_by_id(command.category_id) is None:
            raise NotFoundError("Categoria de exame não encontrada.")

        known_species_ids = {species.id for species in self._species.list_all()}
        if not command.species_ids <= known_species_ids:
            raise ValidationError("Uma ou mais espécies selecionadas não existem.")

        component_ids = validate_panel_components(
            exams=self._exams, component_ids=command.component_exam_ids
        )

        code = self._next_available_code()
        now = self._clock.now()
        try:
            exam = Exam(
                id=uuid4(),
                code=code,
                name=command.name,
                category_id=command.category_id,
                price_base=command.price_base,
                description=command.description,
                species_ids=command.species_ids,
                component_ids=component_ids,
                status=ExamStatus.ACTIVE,
                created_by=command.actor.id,
                updated_by=command.actor.id,
                created_at=now,
                updated_at=now,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        self._exams.add(exam)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="exams.created",
                entity_type="exam",
                entity_id=str(exam.id),
                after_state={
                    "code": str(exam.code),
                    "name": exam.name,
                    "component_count": len(exam.component_ids),
                },
            )
        )

        return exam_to_dto(exam, include_price=_PRICE_PERMISSION in command.actor.permissions)

    def _next_available_code(self) -> ExamCode:
        for _attempt in range(10):
            code = ExamCode(self._code_generator())
            if self._exams.get_by_code(str(code)) is None:
                return code
        raise DuplicateExamCodeError("Não foi possível gerar um código único para o exame.")
