"""Catalog domain entities (exam categories and exams).

No FastAPI/SQLAlchemy import here (rule: .claude/rules/00-global.md — domain
layer). Mutation happens through named methods, never by callers poking at
fields directly, so invariants stay enforced in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.modules.catalog.domain.value_objects import ExamCode, PlantaoSurcharge


class ExamCategoryStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


@dataclass(kw_only=True)
class ExamCategory:
    id: UUID
    name: str
    status: ExamCategoryStatus = ExamCategoryStatus.ACTIVE
    created_by: UUID | None = None
    updated_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    row_version: int = 1

    def update_details(
        self,
        *,
        name: str,
        status: ExamCategoryStatus,
        updated_by: UUID | None,
        now: datetime,
    ) -> None:
        self.name = name
        self.status = status
        self.updated_by = updated_by
        self.updated_at = now

    def deactivate(self, *, updated_by: UUID | None, now: datetime) -> None:
        if self.status == ExamCategoryStatus.INACTIVE:
            return
        self.status = ExamCategoryStatus.INACTIVE
        self.updated_by = updated_by
        self.updated_at = now


class ExamStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


@dataclass(kw_only=True)
class Exam:
    id: UUID
    code: ExamCode
    name: str
    category_id: UUID
    price_base: Decimal
    description: str | None = None
    plantao_surcharge: PlantaoSurcharge = field(default_factory=PlantaoSurcharge)
    species_ids: frozenset[UUID] = field(default_factory=frozenset)
    status: ExamStatus = ExamStatus.ACTIVE
    created_by: UUID | None = None
    updated_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    row_version: int = 1

    def __post_init__(self) -> None:
        if self.price_base <= 0:
            raise ValueError("Preço base do exame deve ser maior que zero.")
        if not self.species_ids:
            raise ValueError("Exame precisa de ao menos uma espécie atendida.")

    def update_details(
        self,
        *,
        code: ExamCode,
        name: str,
        category_id: UUID,
        price_base: Decimal,
        description: str | None,
        plantao_surcharge: PlantaoSurcharge,
        species_ids: frozenset[UUID],
        status: ExamStatus,
        updated_by: UUID | None,
        now: datetime,
    ) -> None:
        if price_base <= 0:
            raise ValueError("Preço base do exame deve ser maior que zero.")
        if not species_ids:
            raise ValueError("Exame precisa de ao menos uma espécie atendida.")
        self.code = code
        self.name = name
        self.category_id = category_id
        self.price_base = price_base
        self.description = description
        self.plantao_surcharge = plantao_surcharge
        self.species_ids = species_ids
        self.status = status
        self.updated_by = updated_by
        self.updated_at = now

    def deactivate(self, *, updated_by: UUID | None, now: datetime) -> None:
        if self.status == ExamStatus.INACTIVE:
            return
        self.status = ExamStatus.INACTIVE
        self.updated_by = updated_by
        self.updated_at = now

    def update_price_base(
        self, *, price_base: Decimal, updated_by: UUID | None, now: datetime
    ) -> None:
        """Targeted price-only update — used by the price-table import, which never touches
        code/name/category/species. `update_details` requires re-specifying every field, which
        would risk silently reverting one of those on a price-only source (never true of this
        entity: mutation only happens through a named method, so a caller can't drift it)."""
        if price_base <= 0:
            raise ValueError("Preço base do exame deve ser maior que zero.")
        self.price_base = price_base
        self.updated_by = updated_by
        self.updated_at = now
