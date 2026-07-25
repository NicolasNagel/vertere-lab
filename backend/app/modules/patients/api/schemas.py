"""Pydantic schemas for the patients API — create/update/read/filter kept
separate; never the SQLAlchemy model (rule: .claude/rules/backend.md)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SpeciesRead(BaseModel):
    id: UUID
    name: str
    created_at: datetime


class SpeciesListResponse(BaseModel):
    items: list[SpeciesRead]
