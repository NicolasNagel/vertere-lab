"""Generic transactional-outbox domain entities — no FastAPI/SQLAlchemy
import here (rule: .claude/rules/00-global.md, domain layer).

Not specific to any module: any use case that needs to trigger an effect
*after* its own commit (notification, export trigger, future worker)
writes one row here in the same transaction as its business write, instead
of calling the external system inline (`.claude/rules/02-backend.md`,
pattern table — "Domain Event": "uma ação de domínio precisa disparar
efeito posterior, fora da transação"). A worker processing this table is
out of scope here — this slice only guarantees the event is durably
recorded, never lost if the process crashes right after commit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class OutboxEventStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


@dataclass(kw_only=True)
class OutboxEvent:
    id: UUID = field(default_factory=uuid4)
    event_type: str
    payload: dict[str, Any]
    status: OutboxEventStatus = OutboxEventStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    processed_at: datetime | None = None
