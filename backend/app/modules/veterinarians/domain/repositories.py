"""Repository protocol for the veterinarians module.

Interface lives in `domain` (per .claude/rules/backend.md); implementation
lives in `infrastructure`. The repository never commits — the unit of work
does.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.veterinarians.domain.entities import Veterinarian, VeterinarianStatus


class VeterinarianRepository(Protocol):
    def get_by_id(self, veterinarian_id: UUID) -> Veterinarian | None: ...

    def get_by_crmv(self, crmv: str) -> Veterinarian | None: ...

    def add(self, veterinarian: Veterinarian) -> None: ...

    def save(self, veterinarian: Veterinarian) -> None: ...

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: VeterinarianStatus | None,
        is_autonomous: bool | None,
        search: str | None,
    ) -> tuple[list[Veterinarian], int]: ...
