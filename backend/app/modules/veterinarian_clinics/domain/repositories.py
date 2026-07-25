"""Repository protocol for the veterinarian-clinic link module.

Interface lives in `domain` (per .claude/rules/backend.md); implementation
lives in `infrastructure`. The repository never commits — the unit of work
does.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.veterinarian_clinics.domain.entities import VeterinarianClinicLink


class VeterinarianClinicLinkRepository(Protocol):
    def get(self, veterinarian_id: UUID, clinic_id: UUID) -> VeterinarianClinicLink | None: ...

    def add(self, link: VeterinarianClinicLink) -> None: ...

    def delete(self, link: VeterinarianClinicLink) -> None: ...

    def clear_primary_for_veterinarian(self, veterinarian_id: UUID) -> None: ...

    def list_by_veterinarian(self, veterinarian_id: UUID) -> list[VeterinarianClinicLink]: ...

    def list_by_clinic(self, clinic_id: UUID) -> list[VeterinarianClinicLink]: ...

    def count_by_veterinarian(self, veterinarian_id: UUID) -> int: ...
