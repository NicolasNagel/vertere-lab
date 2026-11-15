"""Pydantic schemas for the catalog API — create/update/read/filter kept
separate; never the SQLAlchemy model (rule: .claude/rules/02-backend.md)."""

from __future__ import annotations

from datetime import date, datetime
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
    component_exam_ids: list[UUID]
    is_panel: bool
    status: ExamStatusLiteral
    created_at: datetime
    updated_at: datetime
    row_version: int
    # Omitted (null) entirely when the actor lacks `pricing.read` — never a
    # frontend-only hide (rule: .claude/rules/02-backend.md, "autoridade final
    # é o backend").
    price_base: Decimal | None
    price_valid_from: date | None
    price_valid_to: date | None


class ExamListResponse(BaseModel):
    items: list[ExamRead]
    total: int
    page: int
    page_size: int


class ExamCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    category_id: UUID
    price_base: Decimal = Field(gt=0)
    description: str | None = None
    species_ids: list[UUID] = Field(min_length=1)
    component_exam_ids: list[UUID] = Field(default_factory=list)


class ExamUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    category_id: UUID
    # Omitido = manter o preço; alterar exige `pricing.manage` e motivo.
    price_base: Decimal | None = Field(default=None, gt=0)
    description: str | None = None
    species_ids: list[UUID] = Field(min_length=1)
    component_exam_ids: list[UUID] = Field(default_factory=list)
    status: ExamStatusLiteral
    expected_row_version: int
    reason: str | None = Field(default=None, max_length=500)


class ExamImportRowErrorRead(BaseModel):
    line: int
    message: str


class ExamImportResponse(BaseModel):
    imported_count: int
    errors: list[ExamImportRowErrorRead]
