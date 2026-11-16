from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.application.dtos import ExamDTO
from app.modules.catalog.application.mappers import exam_to_dto
from app.modules.catalog.application.panel_components import (
    ensure_not_in_active_panels,
    validate_panel_components,
)
from app.modules.catalog.domain.entities import Exam, ExamStatus
from app.modules.catalog.domain.repositories import ExamCategoryRepository, ExamRepository
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
_PRICE_MANAGE_PERMISSION = "pricing.manage"


def _audit_state(exam: Exam) -> dict[str, Any]:
    return {
        "code": str(exam.code),
        "name": exam.name,
        "category_id": str(exam.category_id),
        "price_base": str(exam.price_base),
        "status": exam.status.value,
        "species_count": len(exam.species_ids),
        "component_count": len(exam.component_ids),
    }


@dataclass(frozen=True, kw_only=True)
class UpdateExamCommand:
    actor: ActorContext
    exam_id: UUID
    name: str
    category_id: UUID
    # None = manter o preço atual (quem não gere preço nem o envia).
    price_base: Decimal | None
    description: str | None
    species_ids: frozenset[UUID]
    status: str
    expected_row_version: int
    component_exam_ids: tuple[UUID, ...] = ()
    reason: str | None = None


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

        price_base = exam.price_base if command.price_base is None else command.price_base
        price_changed = price_base != exam.price_base
        if price_changed and _PRICE_MANAGE_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_PRICE_MANAGE_PERMISSION}")
        status_changed = ExamStatus(command.status) != exam.status
        reason = (command.reason or "").strip()
        if (price_changed or status_changed) and not reason:
            raise ValidationError("Informe o motivo da alteração de preço ou de status.")

        if self._categories.get_by_id(command.category_id) is None:
            raise NotFoundError("Categoria de exame não encontrada.")

        known_species_ids = {species.id for species in self._species.list_all()}
        if not command.species_ids <= known_species_ids:
            raise ValidationError("Uma ou mais espécies selecionadas não existem.")

        component_ids = validate_panel_components(
            exams=self._exams, component_ids=command.component_exam_ids
        )
        new_status = ExamStatus(command.status)
        if new_status == ExamStatus.INACTIVE and exam.status == ExamStatus.ACTIVE:
            ensure_not_in_active_panels(exams=self._exams, exam=exam)

        before_state = _audit_state(exam)

        try:
            exam.update_details(
                name=command.name,
                category_id=command.category_id,
                price_base=price_base,
                description=command.description,
                species_ids=command.species_ids,
                component_ids=component_ids,
                status=new_status,
                updated_by=command.actor.id,
                now=self._clock.now(),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        self._exams.save(exam)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="exams.updated",
                entity_type="exam",
                entity_id=str(exam.id),
                before_state=before_state,
                after_state=_audit_state(exam),
                reason=reason or None,
            )
        )

        return exam_to_dto(exam, include_price=_PRICE_PERMISSION in command.actor.permissions)
