"""List the fixed species catalog.

Gated by `patients.read` rather than a dedicated `species.*` permission:
species is a read-only reference list seeded once (ADR pending if a real
management screen is ever needed), consumed only by the Patient form —
there is no independent screen or action for it, so it does not warrant
its own permission code beyond what `docs/07-nucleo-v1.md` §2.2 reserved.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.application.dtos import SpeciesDTO
from app.modules.patients.application.mappers import species_to_dto
from app.modules.patients.domain.repositories import SpeciesRepository
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "patients.read"


@dataclass(frozen=True, kw_only=True)
class ListSpeciesQuery:
    actor: AuthenticatedUserDTO


class ListSpeciesUseCase:
    def __init__(self, *, species: SpeciesRepository) -> None:
        self._species = species

    def execute(self, query: ListSpeciesQuery) -> list[SpeciesDTO]:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        return [species_to_dto(item) for item in self._species.list_all()]
