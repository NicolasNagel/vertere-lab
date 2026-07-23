"""Audit domain: append-only record of security/business-critical actions.

Shared across modules (identity today, attendances/billing later) — see
docs/03-modelo-de-dominio.md §8 and CLAUDE.md's "audit_log append-only".
Never carries a password, token, cookie or raw payload with PII.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class ActorScope(StrEnum):
    GLOBAL = "GLOBAL"
    LAB = "LAB"
    CLINIC = "CLINIC"
    ANONYMOUS = "ANONYMOUS"


@dataclass(frozen=True, kw_only=True)
class AuditEntry:
    id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    actor_user_id: UUID | None
    actor_scope: ActorScope
    action: str
    entity_type: str
    entity_id: str | None = None
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    reason: str | None = None
    ip_address: str | None = None
    request_id: str | None = None
