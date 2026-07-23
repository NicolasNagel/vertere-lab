"""Repository protocol for audit entries.

The writer never commits — it only stages the append within whatever unit of
work the calling use case already owns (rule: repository never commits).
"""

from __future__ import annotations

from typing import Protocol

from app.modules.audit.domain.entities import AuditEntry


class AuditLogWriter(Protocol):
    def record(self, entry: AuditEntry) -> None: ...
