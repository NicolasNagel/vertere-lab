"""Patients domain entities.

No FastAPI/SQLAlchemy import here (rule: .claude/rules/globals.md — domain
layer). Mutation happens through named methods, never by callers poking at
fields directly, so invariants stay enforced in one place.

`Owner` has no entity/module of its own: per explicit product decision
(`/planejar-fatia` for this slice — no dedicated Owners screen, "Owner é só
mais uma informação do paciente"), owner data lives as plain fields on
`Patient` (`owner_name`, `owner_phone`, `owner_document`), not as a separate
referenced aggregate. This diverges from the `OWNER --> PATIENT` edge in
`docs/03-modelo-de-dominio.md`'s dependency graph — documented as a
deliberate simplification for this slice, not an oversight, since `Owner`
is never selected/managed independently anywhere in the current UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class Species:
    id: UUID
    name: str
    created_at: datetime


class PatientSex(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class PatientStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


@dataclass(kw_only=True)
class Patient:
    id: UUID
    name: str
    species_id: UUID
    sex: PatientSex
    breed: str | None = None
    age_description: str | None = None
    owner_name: str
    owner_phone: str | None = None
    owner_document: str | None = None
    status: PatientStatus = PatientStatus.ACTIVE
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
        species_id: UUID,
        sex: PatientSex,
        breed: str | None,
        age_description: str | None,
        owner_name: str,
        owner_phone: str | None,
        owner_document: str | None,
        status: PatientStatus,
        notes: str | None,
        updated_by: UUID | None,
        now: datetime,
    ) -> None:
        self.name = name
        self.species_id = species_id
        self.sex = sex
        self.breed = breed
        self.age_description = age_description
        self.owner_name = owner_name
        self.owner_phone = owner_phone
        self.owner_document = owner_document
        self.status = status
        self.notes = notes
        self.updated_by = updated_by
        self.updated_at = now

    def deactivate(self, *, updated_by: UUID | None, now: datetime) -> None:
        if self.status == PatientStatus.INACTIVE:
            return
        self.status = PatientStatus.INACTIVE
        self.updated_by = updated_by
        self.updated_at = now
