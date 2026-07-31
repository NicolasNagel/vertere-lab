"""Application-layer DTOs — never ORM objects, never domain entities leaked
raw across the module boundary (rule: .claude/rules/02-backend.md)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class ClinicDTO:
    id: UUID
    name: str
    tax_id: str | None
    phone: str | None
    email: str | None
    status: str
    address_zip_code: str | None
    address_street: str | None
    address_number: str | None
    address_neighborhood: str | None
    address_city: str | None
    address_state: str | None
    address_complement: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    row_version: int
