"""Repository protocol — implementation lives in infrastructure (rule:
.claude/rules/02-backend.md, "interface em application/domain")."""

from __future__ import annotations

from typing import Protocol

from app.shared.outbox.domain.entities import OutboxEvent


class OutboxEventRepository(Protocol):
    def add(self, event: OutboxEvent) -> None: ...
