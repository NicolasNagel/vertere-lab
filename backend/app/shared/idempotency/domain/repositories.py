"""Repository protocol — implementation lives in infrastructure (rule:
.claude/rules/02-backend.md, "interface em application/domain")."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from app.shared.idempotency.domain.entities import IdempotencyRecord


class IdempotencyRecordRepository(Protocol):
    def try_begin(self, record: IdempotencyRecord) -> bool:
        """Insert a new IN_PROGRESS record for (actor, operation, key).

        Returns ``True`` when inserted. Returns ``False`` when a record for
        that combination already exists — the caller then uses ``find`` to
        decide between replay and conflict. Never raises on a collision;
        the concurrency-safe handling (savepoint around the unique
        violation) is an infrastructure concern.
        """
        ...

    def find(
        self, *, actor_id: UUID, operation: str, idempotency_key: str
    ) -> IdempotencyRecord | None: ...

    def mark_completed(
        self,
        record_id: UUID,
        *,
        status_code: int,
        body: dict[str, Any],
        now: datetime,
    ) -> None: ...
