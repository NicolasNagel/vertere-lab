"""Patients domain entities.

No FastAPI/SQLAlchemy import here (rule: .claude/rules/globals.md — domain
layer). `Species` is the only entity in this slice — `Patient` itself lands
in a later fatia; this one only builds the reference list a Patient form
will select from.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class Species:
    id: UUID
    name: str
    created_at: datetime
