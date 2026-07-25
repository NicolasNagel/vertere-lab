"""List the fixed species catalog.

No permission gate beyond authentication: species started as a Patient-form
reference list gated by `patients.read`, but the Exam catalog (Fase 2,
`docs/adr/005-preco-embutido-em-exam.md`) now also needs it for a user
profile (e.g. pure `FINANCE`) that has `catalog.manage`/`pricing.read` but
not necessarily `patients.read`. It is static, non-sensitive reference
data with no independent screen or action, so gating it per-consumer
permission would just keep growing the list without protecting anything
real — any authenticated user can read it (rule:
.claude/rules/backend.md, "autorização... nunca implícita" still holds:
this is an explicit decision, not a bypass).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.application.dtos import SpeciesDTO
from app.modules.patients.application.mappers import species_to_dto
from app.modules.patients.domain.repositories import SpeciesRepository


@dataclass(frozen=True, kw_only=True)
class ListSpeciesQuery:
    actor: AuthenticatedUserDTO


class ListSpeciesUseCase:
    def __init__(self, *, species: SpeciesRepository) -> None:
        self._species = species

    def execute(self, _query: ListSpeciesQuery) -> list[SpeciesDTO]:
        return [species_to_dto(item) for item in self._species.list_all()]
