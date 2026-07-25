"""Application-layer DTOs — never ORM objects, never domain entities leaked
raw across the module boundary (rule: .claude/rules/backend.md)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class VeterinarianDTO:
    id: UUID
    name: str
    crmv: str
    phone: str | None
    email: str | None
    is_autonomous: bool
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
    row_version: int
