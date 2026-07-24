"""Repository protocol for the clinics module.

Interface lives in `domain` (per .claude/rules/backend.md); implementation
lives in `infrastructure`. The repository never commits — the unit of work
does.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.clinics.domain.entities import Clinic, ClinicStatus


class ClinicRepository(Protocol):
    def get_by_id(self, clinic_id: UUID) -> Clinic | None: ...

    def get_by_tax_id(self, tax_id: str) -> Clinic | None: ...

    def add(self, clinic: Clinic) -> None: ...

    def save(self, clinic: Clinic) -> None: ...

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: ClinicStatus | None,
        search: str | None,
    ) -> tuple[list[Clinic], int]: ...
