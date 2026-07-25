"""Pydantic schemas for the catalog API — create/update/read/filter kept
separate; never the SQLAlchemy model (rule: .claude/rules/backend.md)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ExamCategoryStatusLiteral = Literal["ACTIVE", "INACTIVE"]
ExamStatusLiteral = Literal["ACTIVE", "INACTIVE"]


class ExamCategoryRead(BaseModel):
    id: UUID
    name: str
    status: ExamCategoryStatusLiteral
    created_at: datetime
    updated_at: datetime
    row_version: int


class ExamCategoryListResponse(BaseModel):
    items: list[ExamCategoryRead]
    total: int
    page: int
    page_size: int


class ExamCategoryActiveListResponse(BaseModel):
    items: list[ExamCategoryRead]


class ExamCategoryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)


class ExamCategoryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    status: ExamCategoryStatusLiteral
    expected_row_version: int


class ExamRead(BaseModel):
    id: UUID
    code: str
    name: str
    category_id: UUID
    description: str | None
    species_ids: list[UUID]
    status: ExamStatusLiteral
    created_at: datetime
    updated_at: datetime
    row_version: int
    # Omitted (null) entirely when the actor lacks `pricing.read` — never a
    # frontend-only hide (rule: .claude/rules/backend.md, "autoridade final
    # é o backend").
    price_base: Decimal | None
    plantao_surcharge_fixed: Decimal | None
    plantao_surcharge_percent: Decimal | None


class ExamListResponse(BaseModel):
    items: list[ExamRead]
    total: int
    page: int
    page_size: int


class ExamCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category_id: UUID
    price_base: Decimal = Field(gt=0)
    description: str | None = None
    plantao_surcharge_fixed: Decimal | None = None
    plantao_surcharge_percent: Decimal | None = None
    species_ids: list[UUID] = Field(min_length=1)


class ExamUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category_id: UUID
    price_base: Decimal = Field(gt=0)
    description: str | None = None
    plantao_surcharge_fixed: Decimal | None = None
    plantao_surcharge_percent: Decimal | None = None
    species_ids: list[UUID] = Field(min_length=1)
    status: ExamStatusLiteral
    expected_row_version: int
