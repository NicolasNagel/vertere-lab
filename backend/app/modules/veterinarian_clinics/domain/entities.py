"""Veterinarian-clinic link domain entity.

No FastAPI/SQLAlchemy import here (rule: .claude/rules/globals.md — domain
layer). This is a pure join between two peer aggregates (`Veterinarian`,
`Clinic`) — it lives in its own module instead of inside either one so
neither `veterinarians` nor `clinics` has to depend on the other
(`docs/adr/003-veterinarios-crmv-e-layout.md` addendum).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class VeterinarianClinicLink:
    id: UUID
    veterinarian_id: UUID
    clinic_id: UUID
    primary_clinic: bool
    created_by: UUID | None
    created_at: datetime
