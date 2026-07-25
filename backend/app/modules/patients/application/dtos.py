"""Application-layer DTOs — never ORM objects, never domain entities leaked
raw across the module boundary (rule: .claude/rules/backend.md)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class SpeciesDTO:
    id: UUID
    name: str
    created_at: datetime
