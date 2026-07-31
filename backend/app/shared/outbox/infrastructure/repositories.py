"""SQLAlchemy implementation of the outbox-event repository protocol."""

from __future__ import annotations

from sqlalchemy.orm import Session as SqlAlchemySession

from app.shared.outbox.domain.entities import OutboxEvent
from app.shared.outbox.infrastructure.models import OutboxEventModel


class SqlAlchemyOutboxEventRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def add(self, event: OutboxEvent) -> None:
        self._session.add(
            OutboxEventModel(
                id=event.id,
                event_type=event.event_type,
                payload=event.payload,
                status=event.status.value,
                created_at=event.created_at,
                processed_at=event.processed_at,
            )
        )
