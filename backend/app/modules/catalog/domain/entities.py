"""Catalog domain entities (exam categories and exams).

No FastAPI/SQLAlchemy import here (rule: .claude/rules/00-global.md — domain
layer). Mutation happens through named methods, never by callers poking at
fields directly, so invariants stay enforced in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.modules.catalog.domain.value_objects import ExamCode


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
    price_valid_from: date = date(1900, 1, 1)
    price_valid_to: date | None = None
    description: str | None = None
    species_ids: frozenset[UUID] = field(default_factory=frozenset)
    # Non-empty => this exam is a panel (pacote/perfil): a closed bundle of other exams sold at
    # its own `price_base`, not at the sum of its components. A panel is still an `Exam` row, so
    # attendances, price snapshots and closures need no special case for it.
    component_ids: tuple[UUID, ...] = ()
    status: ExamStatus = ExamStatus.ACTIVE
    created_by: UUID | None = None
    updated_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    row_version: int = 1

    @property
    def is_panel(self) -> bool:
        return len(self.component_ids) > 0

    def __post_init__(self) -> None:
        self._validate_components(self.component_ids)
        if self.price_base <= 0:
            raise ValueError("Preço base do exame deve ser maior que zero.")
        if not self.species_ids:
            raise ValueError("Exame precisa de ao menos uma espécie atendida.")
        if self.price_valid_to is not None and self.price_valid_to < self.price_valid_from:
            raise ValueError("Vigência final do preço não pode anteceder a inicial.")

    def _validate_components(self, component_ids: tuple[UUID, ...]) -> None:
        if self.id in component_ids:
            raise ValueError("Um pacote não pode conter ele mesmo.")
        if len(set(component_ids)) != len(component_ids):
            raise ValueError("O pacote tem exames repetidos.")

    def has_price_on(self, service_date: date) -> bool:
        return self.price_valid_from <= service_date and (
            self.price_valid_to is None or service_date <= self.price_valid_to
        )

    def update_details(
        self,
        *,
        name: str,
        category_id: UUID,
        price_base: Decimal,
        description: str | None,
        species_ids: frozenset[UUID],
        component_ids: tuple[UUID, ...] = (),
        status: ExamStatus,
        updated_by: UUID | None,
        now: datetime,
    ) -> None:
        if (len(component_ids) > 0) != self.is_panel:
            raise ValueError("Não é possível transformar exame em pacote (ou o contrário).")
        self._validate_components(component_ids)
        if price_base <= 0:
            raise ValueError("Preço base do exame deve ser maior que zero.")
        if not species_ids:
            raise ValueError("Exame precisa de ao menos uma espécie atendida.")
        if price_base != self.price_base:
            self.price_valid_from = now.date()
            self.price_valid_to = None
        self.name = name
        self.category_id = category_id
        self.price_base = price_base
        self.description = description
        self.species_ids = species_ids
        self.component_ids = component_ids
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
        self.price_valid_from = now.date()
        self.price_valid_to = None
        self.updated_by = updated_by
        self.updated_at = now
