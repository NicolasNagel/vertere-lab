"""Repository protocol for the patients module (species slice).

Interface lives in `domain` (per .claude/rules/02-backend.md); implementation
lives in `infrastructure`.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.patients.domain.entities import Patient, PatientStatus, Species


class SpeciesRepository(Protocol):
    def list_all(self) -> list[Species]: ...


class PatientRepository(Protocol):
    def get_by_id(self, patient_id: UUID, *, for_update: bool = False) -> Patient | None:
        """`for_update=True` locks the row until the unit of work ends: use it on every path that
        changes the patient, so concurrent writers are serialized and the version check is real."""
        ...

    def get_by_owner_and_name(self, *, owner_name: str, name: str) -> Patient | None:
        """Case-insensitive match on (owner_name, name) — the closest thing
        to a natural key this entity has, since it carries no clinic
        reference (import idempotency and cross-clinic-collision detection
        both key off this pair)."""
        ...

    def add(self, patient: Patient) -> None: ...

    def save(self, patient: Patient) -> None: ...

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: PatientStatus | None,
        search: str | None,
        clinic_ids: frozenset[UUID] | None = None,
        clinic_id: UUID | None = None,
        species_id: UUID | None = None,
    ) -> tuple[list[Patient], int]: ...

    def count_by_status(
        self,
        *,
        search: str | None,
        clinic_ids: frozenset[UUID] | None = None,
        clinic_id: UUID | None = None,
        species_id: UUID | None = None,
    ) -> tuple[int, int]:
        """Return `(active, inactive)` for the same filters `list_page` accepts."""
        ...
