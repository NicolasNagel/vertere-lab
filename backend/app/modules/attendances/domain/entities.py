"""Attendances domain entities.

No FastAPI/SQLAlchemy import here (rule: .claude/rules/globals.md — domain
layer). Mutation happens through named methods, never by callers poking at
fields directly, so invariants stay enforced in one place.

This is the smallest possible slice of `AttendanceRecord`
(`docs/03-modelo-de-dominio.md` §3): an empty `DRAFT`, referencing only
`clinic_id`/`veterinarian_id`/`patient_id`. Deliberately absent from this
slice:

- `owner_id` — `docs/03` lists it as a separate `AttendanceRecord` field,
  but ADR-004 already eliminated the `Owner` aggregate (tutor data lives
  embedded on `Patient`). The tutor is read from `Patient` at snapshot time
  (Incremento 3.2), never referenced by its own id here.
- protocol fields (`protocol_year`/`protocol_sequence`/`protocol_number`) —
  `.claude/rules/attendence.md`: "confirmação gera protocolo". A draft has
  no protocol yet.
- money fields, `AttendanceExam` items, `service_type_id`,
  `collection_method_id` — "nenhum atendimento confirmado existe sem
  item"; a draft with no items has nothing to total yet. These arrive via
  an additive migration when the confirmation slice needs them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID


class AttendanceStatus(StrEnum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ON_HOLD = "ON_HOLD"


@dataclass(kw_only=True)
class AttendanceRecord:
    id: UUID
    clinic_id: UUID
    veterinarian_id: UUID
    patient_id: UUID
    service_date: date | None = None
    notes: str | None = None
    status: AttendanceStatus = AttendanceStatus.DRAFT
    created_by: UUID | None = None
    updated_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    row_version: int = 1
