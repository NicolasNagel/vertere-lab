"""Clinics domain entities.

No FastAPI/SQLAlchemy import here (rule: .claude/rules/00-global.md — domain
layer). Mutation happens through named methods, never by callers poking at
fields directly, so invariants stay enforced in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.modules.clinics.domain.value_objects import TaxId


class ClinicStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DELINQUENT = "DELINQUENT"
    SPECIAL = "SPECIAL"


@dataclass(kw_only=True)
class Clinic:
    id: UUID
    name: str
    tax_id: TaxId | None = None
    phone: str | None = None
    email: str | None = None
    status: ClinicStatus = ClinicStatus.ACTIVE
    address_zip_code: str | None = None
    address_street: str | None = None
    address_number: str | None = None
    address_neighborhood: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_complement: str | None = None
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
        tax_id: TaxId | None,
        phone: str | None,
        email: str | None,
        status: ClinicStatus,
        address_zip_code: str | None,
        address_street: str | None,
        address_number: str | None,
        address_neighborhood: str | None,
        address_city: str | None,
        address_state: str | None,
        address_complement: str | None,
        notes: str | None,
        updated_by: UUID | None,
        now: datetime,
    ) -> None:
        self.name = name
        self.tax_id = tax_id
        self.phone = phone
        self.email = email
        self.status = status
        self.address_zip_code = address_zip_code
        self.address_street = address_street
        self.address_number = address_number
        self.address_neighborhood = address_neighborhood
        self.address_city = address_city
        self.address_state = address_state
        self.address_complement = address_complement
        self.notes = notes
        self.updated_by = updated_by
        self.updated_at = now

    def deactivate(self, *, updated_by: UUID | None, now: datetime) -> None:
        if self.status == ClinicStatus.INACTIVE:
            return
        self.status = ClinicStatus.INACTIVE
        self.updated_by = updated_by
        self.updated_at = now
