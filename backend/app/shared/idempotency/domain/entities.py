"""Idempotency-key domain entities — no FastAPI/SQLAlchemy import here
(rule: .claude/rules/00-global.md, domain layer).

Generic to any critical POST (`.claude/rules/02-backend.md`: "POST de
criação/confirmação/fechamento aceita Idempotency-Key"), not specific to
attendances — reused by closures later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class IdempotencyRecordStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


@dataclass(kw_only=True)
class IdempotencyRecord:
    """One row per (actor, operation, Idempotency-Key). ``payload_hash``
    detects the "same key, different payload" case, which is a client bug,
    not a retry — it must fail loudly (`IDEMPOTENCY_CONFLICT`), never
    silently replay the wrong response.
    """

    id: UUID
    actor_id: UUID
    operation: str
    idempotency_key: str
    payload_hash: str
    status: IdempotencyRecordStatus
    response_status_code: int | None = None
    response_body: dict[str, Any] | None = None
    created_at: datetime
    completed_at: datetime | None = None
