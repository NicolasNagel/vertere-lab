"""Repository protocols for the attendances module.

Interface lives in `domain` (per .claude/rules/02-backend.md); implementation
lives in `infrastructure`. The repository never commits — the unit of work
does.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.modules.attendances.domain.entities import (
    AttendanceRecord,
    AttendanceStatus,
    OnCallFeeSetting,
    ServiceLevel,
)


class AttendanceRepository(Protocol):
    def get_by_id(self, attendance_id: UUID) -> AttendanceRecord | None: ...

    def get_by_legacy_source(
        self, *, import_batch_id: UUID, source_row_number: int
    ) -> AttendanceRecord | None:
        """Idempotency lookup for Fase 4 (`.claude/rules/10-data-migration.md`:
        "reprocessar não duplica") — a row already imported by this batch is
        found here instead of being inserted again."""
        ...

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
        service_level: ServiceLevel | None,
        protocol_number: str | None,
        owner_name: str | None,
        service_date_from: date | None,
        service_date_to: date | None,
        clinic_ids: frozenset[UUID] | None = None,
    ) -> tuple[list[AttendanceRecord], int]: ...

    def count_by_status(
        self,
        *,
        clinic_id: UUID | None,
        veterinarian_id: UUID | None,
        service_level: ServiceLevel | None,
        protocol_number: str | None,
        owner_name: str | None,
        service_date_from: date | None,
        service_date_to: date | None,
        clinic_ids: frozenset[UUID] | None = None,
    ) -> dict[AttendanceStatus, int]: ...

    def sum_billed_total(
        self,
        *,
        clinic_id: UUID | None,
        veterinarian_id: UUID | None,
        service_level: ServiceLevel | None,
        protocol_number: str | None,
        owner_name: str | None,
        service_date_from: date | None,
        service_date_to: date | None,
        clinic_ids: frozenset[UUID] | None = None,
    ) -> Decimal:
        """Sum of `grand_total` over every match, excluding DRAFT and CANCELLED
        (neither is billable). Computed in the database so the dashboard never
        adds money up in the browser."""
        ...


class AttendanceSequenceRepository(Protocol):
    """Transactional protocol sequence — `MAX + 1` is forbidden
    (`.claude/rules/03-database.md`). Implementation locks the counter row for
    the given year within the caller's transaction.
    """

    def next_sequence(self, year: int) -> int: ...


class OnCallFeeSettingRepository(Protocol):
    """Only `PLANTAO_NORMAL`/`PLANTAO_ESPECIAL` have a row — `NORMAL` has no
    configurable fee, callers must special-case it to `Decimal("0")` instead
    of calling `get_by_service_level`.
    """

    def get_by_service_level(self, service_level: ServiceLevel) -> OnCallFeeSetting | None: ...

    def list_all(self) -> list[OnCallFeeSetting]: ...

    def update(self, setting: OnCallFeeSetting) -> None: ...
