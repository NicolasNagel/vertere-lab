from __future__ import annotations

from app.modules.veterinarians.application.dtos import VeterinarianDTO
from app.modules.veterinarians.domain.entities import Veterinarian


def veterinarian_to_dto(veterinarian: Veterinarian) -> VeterinarianDTO:
    return VeterinarianDTO(
        id=veterinarian.id,
        name=veterinarian.name,
        crmv=str(veterinarian.crmv),
        phone=veterinarian.phone,
        email=veterinarian.email,
        is_autonomous=veterinarian.is_autonomous,
        status=veterinarian.status.value,
        notes=veterinarian.notes,
        created_at=veterinarian.created_at,
        updated_at=veterinarian.updated_at,
        row_version=veterinarian.row_version,
    )
