"""Repository protocols for the attendances module.

Interface lives in `domain` (per .claude/rules/backend.md); implementation
lives in `infrastructure`. The repository never commits — the unit of work
does.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.attendances.domain.entities import AttendanceRecord, AttendanceStatus


class AttendanceRepository(Protocol):
    def get_by_id(self, attendance_id: UUID) -> AttendanceRecord | None: ...

    def add(self, attendance: AttendanceRecord) -> None: ...

    def update(self, attendance: AttendanceRecord) -> None: ...

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        clinic_id: UUID | None,
        veterinarian_id: UUID | None,
        patient_id: UUID | None,
        status: AttendanceStatus | None,
    ) -> tuple[list[AttendanceRecord], int]: ...


class AttendanceSequenceRepository(Protocol):
    """Transactional protocol sequence — `MAX + 1` is forbidden
    (`.claude/rules/database.md`). Implementation locks the counter row for
    the given year within the caller's transaction.
    """

    def next_sequence(self, year: int) -> int: ...
