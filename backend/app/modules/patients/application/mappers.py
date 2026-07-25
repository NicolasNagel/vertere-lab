from __future__ import annotations

from app.modules.patients.application.dtos import SpeciesDTO
from app.modules.patients.domain.entities import Species


def species_to_dto(species: Species) -> SpeciesDTO:
    return SpeciesDTO(id=species.id, name=species.name, created_at=species.created_at)
