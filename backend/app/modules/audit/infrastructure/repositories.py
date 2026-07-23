"""SQLAlchemy implementation of `AuditLogWriter`."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.audit.domain.entities import AuditEntry
from app.modules.audit.infrastructure.models import AuditLogModel


class SqlAlchemyAuditLogWriter:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, entry: AuditEntry) -> None:
        self._session.add(
            AuditLogModel(
                id=entry.id,
                occurred_at=entry.occurred_at,
                actor_user_id=entry.actor_user_id,
                actor_scope=entry.actor_scope.value,
                action=entry.action,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                before_state=entry.before_state,
                after_state=entry.after_state,
                reason=entry.reason,
                ip_address=entry.ip_address,
                request_id=entry.request_id,
            )
        )
