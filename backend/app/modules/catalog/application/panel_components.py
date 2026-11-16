"""Validation shared by create/update/deactivate for exam panels (pacotes/perfis)."""

from __future__ import annotations

from uuid import UUID

from app.modules.catalog.domain.entities import Exam, ExamStatus
from app.modules.catalog.domain.repositories import ExamRepository
from app.shared.domain.errors import ConflictError, ValidationError


def validate_panel_components(
    *, exams: ExamRepository, component_ids: tuple[UUID, ...]
) -> tuple[UUID, ...]:
    """A panel only takes existing, active, plain exams — no nesting, no duplicates."""
    if not component_ids:
        return ()
    if len(set(component_ids)) != len(component_ids):
        raise ValidationError("O pacote tem exames repetidos.")
    found = {exam.id: exam for exam in exams.get_many_by_ids(list(component_ids))}
    if len(found) != len(component_ids):
        raise ValidationError("Um ou mais exames do pacote não existem.")
    for component_id in component_ids:
        component = found[component_id]
        if component.is_panel:
            raise ValidationError(f"{component.name} é um pacote e não pode estar dentro de outro.")
        if component.status != ExamStatus.ACTIVE:
            raise ValidationError(f"{component.name} está inativo e não pode compor um pacote.")
    return component_ids


def ensure_not_in_active_panels(*, exams: ExamRepository, exam: Exam) -> None:
    """Inactivating a component would leave an active panel selling something that can no longer
    be performed — the user has to edit those panels first."""
    panels = exams.list_active_panels_containing(exam.id)
    if panels:
        names = ", ".join(panel.name for panel in panels)
        raise ConflictError(
            f"Este exame faz parte de pacotes ativos ({names}). Retire-o deles antes de inativar."
        )
