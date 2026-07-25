"""Repository protocol for the patients module (species slice).

Interface lives in `domain` (per .claude/rules/backend.md); implementation
lives in `infrastructure`.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.patients.domain.entities import Patient, PatientStatus, Species


class SpeciesRepository(Protocol):
    def list_all(self) -> list[Species]: ...


class PatientRepository(Protocol):
    def get_by_id(self, patient_id: UUID) -> Patient | None: ...

    def add(self, patient: Patient) -> None: ...

    def save(self, patient: Patient) -> None: ...

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: PatientStatus | None,
        search: str | None,
    ) -> tuple[list[Patient], int]: ...
