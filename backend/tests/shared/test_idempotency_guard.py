"""Unit tests for `IdempotencyGuard` against an in-memory fake repository —
the SAVEPOINT/concurrency handling itself is infrastructure and is covered
by the real-Postgres concurrency test in
`tests/integration/test_attendances_api.py`
(`test_confirm_attendance_concurrent_same_key_confirms_exactly_once`)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.shared.domain.errors import IdempotencyConflictError
from app.shared.idempotency.application.guard import IdempotencyGuard, IdempotencyOutcome
from app.shared.idempotency.domain.entities import IdempotencyRecord, IdempotencyRecordStatus

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_ACTOR_ID = uuid4()


class FakeIdempotencyRecordRepository:
    def __init__(self) -> None:
        self._by_natural_key: dict[tuple[UUID, str, str], IdempotencyRecord] = {}
        self._by_id: dict[UUID, IdempotencyRecord] = {}

    def try_begin(self, record: IdempotencyRecord) -> bool:
        key = (record.actor_id, record.operation, record.idempotency_key)
        if key in self._by_natural_key:
            return False
        self._by_natural_key[key] = record
        self._by_id[record.id] = record
        return True

    def find(
        self, *, actor_id: UUID, operation: str, idempotency_key: str
    ) -> IdempotencyRecord | None:
        return self._by_natural_key.get((actor_id, operation, idempotency_key))

    def mark_completed(
        self, record_id: UUID, *, status_code: int, body: dict[str, object], now: datetime
    ) -> None:
        record = self._by_id[record_id]
        record.status = IdempotencyRecordStatus.COMPLETED
        record.response_status_code = status_code
        record.response_body = body
        record.completed_at = now


def _begin(
    guard: IdempotencyGuard,
    *,
    key: str,
    payload: dict[str, object],
    actor_id: UUID = _ACTOR_ID,
    operation: str = "attendances.confirm:x",
) -> IdempotencyOutcome:
    return guard.begin(
        actor_id=actor_id,
        operation=operation,
        idempotency_key=key,
        payload=payload,
        now=_NOW,
    )


def test_same_key_replays_the_stored_response_and_rejects_changed_or_unfinished_requests() -> None:
    guard = IdempotencyGuard(records=FakeIdempotencyRecordRepository())
    payload: dict[str, object] = {"items": [{"exam_id": "abc", "quantity": 1}]}

    first = _begin(guard, key="key-1", payload=payload)
    assert first.replayed_response is None  # primeira chamada segue adiante

    # Mesma chave ainda em andamento: conflito.
    with pytest.raises(IdempotencyConflictError):
        _begin(guard, key="key-1", payload=payload)

    guard.complete(first.record_id, status_code=200, body={"status": "CONFIRMED"}, now=_NOW)
    assert _begin(guard, key="key-1", payload=payload).replayed_response == (
        200,
        {"status": "CONFIRMED"},
    )
    # Mesma chave com payload diferente: conflito.
    with pytest.raises(IdempotencyConflictError):
        _begin(guard, key="key-1", payload={"items": [{"exam_id": "abc", "quantity": 2}]})


def test_same_key_does_not_collide_across_actors_or_operations() -> None:
    guard = IdempotencyGuard(records=FakeIdempotencyRecordRepository())
    payload: dict[str, object] = {"items": []}
    first = _begin(guard, key="key-2", payload=payload)
    guard.complete(first.record_id, status_code=200, body={}, now=_NOW)

    assert _begin(guard, key="key-2", payload=payload, actor_id=uuid4()).replayed_response is None
    assert (
        _begin(guard, key="key-2", payload=payload, operation="attendances.confirm:y")
    ).replayed_response is None
