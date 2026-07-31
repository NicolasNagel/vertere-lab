"""Application-layer DTOs — never ORM objects, never domain entities leaked
raw across the module boundary (rule: .claude/rules/02-backend.md)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class ExamCategoryDTO:
    id: UUID
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
    row_version: int


@dataclass(frozen=True, kw_only=True)
class ExamDTO:
    id: UUID
    code: str
    name: str
    category_id: UUID
    description: str | None
    species_ids: frozenset[UUID]
    status: str
    created_at: datetime
    updated_at: datetime
    row_version: int
    # None when the actor lacks `pricing.read` — omitted from the API
    # response entirely in that case, not just masked (rule:
    # .claude/rules/02-backend.md, "404 pode ocultar recurso" applied here to
    # a field instead of a whole resource).
    price_base: Decimal | None
    plantao_surcharge_fixed: Decimal | None
    plantao_surcharge_percent: Decimal | None
