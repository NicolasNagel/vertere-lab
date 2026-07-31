"""SQLAlchemy implementation of the idempotency-record repository protocol.

`try_begin` wraps the insert in a SAVEPOINT (`Session.begin_nested`) so a
unique-constraint collision only rolls back the savepoint, never the
caller's outer transaction — the caller can keep using the same session
afterward (rule: .claude/rules/03-database.md; concurrency handling stays in
infrastructure, the application layer just gets a bool back).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as SqlAlchemySession

from app.shared.idempotency.domain.entities import IdempotencyRecord, IdempotencyRecordStatus
from app.shared.idempotency.infrastructure.models import IdempotencyKeyModel


def _to_domain(model: IdempotencyKeyModel) -> IdempotencyRecord:
    return IdempotencyRecord(
        id=model.id,
        actor_id=model.actor_id,
        operation=model.operation,
        idempotency_key=model.idempotency_key,
        payload_hash=model.payload_hash,
        status=IdempotencyRecordStatus(model.status),
        response_status_code=model.response_status_code,
        response_body=model.response_body,
        created_at=model.created_at,
        completed_at=model.completed_at,
    )


class SqlAlchemyIdempotencyRecordRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def try_begin(self, record: IdempotencyRecord) -> bool:
        try:
            with self._session.begin_nested():
                self._session.add(
                    IdempotencyKeyModel(
                        id=record.id,
                        actor_id=record.actor_id,
                        operation=record.operation,
                        idempotency_key=record.idempotency_key,
                        payload_hash=record.payload_hash,
                        status=record.status.value,
                        created_at=record.created_at,
                    )
                )
                self._session.flush()
        except IntegrityError:
            return False
        return True

    def find(
        self, *, actor_id: UUID, operation: str, idempotency_key: str
    ) -> IdempotencyRecord | None:
        model = self._session.execute(
            select(IdempotencyKeyModel).where(
                IdempotencyKeyModel.actor_id == actor_id,
                IdempotencyKeyModel.operation == operation,
                IdempotencyKeyModel.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        return _to_domain(model) if model is not None else None

    def mark_completed(
        self,
        record_id: UUID,
        *,
        status_code: int,
        body: dict[str, Any],
        now: datetime,
    ) -> None:
        model = self._session.get(IdempotencyKeyModel, record_id)
        if model is None:
            raise LookupError(f"Registro de idempotência {record_id} não encontrado.")
        model.status = IdempotencyRecordStatus.COMPLETED.value
        model.response_status_code = status_code
        model.response_body = body
        model.completed_at = now
