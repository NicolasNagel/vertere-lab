"""Veterinarians domain entities.

No FastAPI/SQLAlchemy import here (rule: .claude/rules/globals.md — domain
layer). Mutation happens through named methods, never by callers poking at
fields directly, so invariants stay enforced in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.modules.veterinarians.domain.value_objects import Crmv


class VeterinarianStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


@dataclass(kw_only=True)
class Veterinarian:
    id: UUID
    name: str
    crmv: Crmv
    phone: str | None = None
    email: str | None = None
    is_autonomous: bool = False
    status: VeterinarianStatus = VeterinarianStatus.ACTIVE
    notes: str | None = None
    created_by: UUID | None = None
    updated_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    row_version: int = 1

    def update_details(
        self,
        *,
        name: str,
        crmv: Crmv,
        phone: str | None,
        email: str | None,
        is_autonomous: bool,
        status: VeterinarianStatus,
        notes: str | None,
        updated_by: UUID | None,
        now: datetime,
    ) -> None:
        self.name = name
        self.crmv = crmv
        self.phone = phone
        self.email = email
        self.is_autonomous = is_autonomous
        self.status = status
        self.notes = notes
        self.updated_by = updated_by
        self.updated_at = now

    def deactivate(self, *, updated_by: UUID | None, now: datetime) -> None:
        if self.status == VeterinarianStatus.INACTIVE:
            return
        self.status = VeterinarianStatus.INACTIVE
        self.updated_by = updated_by
        self.updated_at = now
