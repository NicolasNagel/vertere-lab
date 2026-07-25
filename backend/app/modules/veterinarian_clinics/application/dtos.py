"""Application-layer DTOs — never ORM objects, never domain entities leaked
raw across the module boundary (rule: .claude/rules/backend.md)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class LinkedClinicDTO:
    clinic_id: UUID
    clinic_name: str
    primary_clinic: bool


@dataclass(frozen=True, kw_only=True)
class LinkedVeterinarianDTO:
    veterinarian_id: UUID
    veterinarian_name: str
    crmv: str
    primary_clinic: bool
