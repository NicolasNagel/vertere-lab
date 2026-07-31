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
from app.shared.idempotency.application.guard import IdempotencyGuard
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


def test_begin_first_call_proceeds() -> None:
    guard = IdempotencyGuard(records=FakeIdempotencyRecordRepository())

    outcome = guard.begin(
        actor_id=_ACTOR_ID,
        operation="attendances.confirm:x",
        idempotency_key="key-1",
        payload={"items": [1]},
        now=_NOW,
    )

    assert outcome.replayed_response is None


def test_complete_then_same_key_and_payload_replays() -> None:
    records = FakeIdempotencyRecordRepository()
    guard = IdempotencyGuard(records=records)
    payload = {"items": [{"exam_id": "abc", "quantity": 1}]}

    first = guard.begin(
        actor_id=_ACTOR_ID,
        operation="attendances.confirm:x",
        idempotency_key="key-2",
        payload=payload,
        now=_NOW,
    )
    guard.complete(first.record_id, status_code=200, body={"status": "CONFIRMED"}, now=_NOW)

    second = guard.begin(
        actor_id=_ACTOR_ID,
        operation="attendances.confirm:x",
        idempotency_key="key-2",
        payload=payload,
        now=_NOW,
    )

    assert second.replayed_response == (200, {"status": "CONFIRMED"})


def test_same_key_different_payload_is_conflict() -> None:
    records = FakeIdempotencyRecordRepository()
    guard = IdempotencyGuard(records=records)

    first = guard.begin(
        actor_id=_ACTOR_ID,
        operation="attendances.confirm:x",
        idempotency_key="key-3",
        payload={"items": [{"quantity": 1}]},
        now=_NOW,
    )
    guard.complete(first.record_id, status_code=200, body={}, now=_NOW)

    with pytest.raises(IdempotencyConflictError):
        guard.begin(
            actor_id=_ACTOR_ID,
            operation="attendances.confirm:x",
            idempotency_key="key-3",
            payload={"items": [{"quantity": 2}]},
            now=_NOW,
        )


def test_same_key_still_in_progress_is_conflict() -> None:
    records = FakeIdempotencyRecordRepository()
    guard = IdempotencyGuard(records=records)
    payload = {"items": [{"quantity": 1}]}

    guard.begin(
        actor_id=_ACTOR_ID,
        operation="attendances.confirm:x",
        idempotency_key="key-4",
        payload=payload,
        now=_NOW,
    )

    with pytest.raises(IdempotencyConflictError):
        guard.begin(
            actor_id=_ACTOR_ID,
            operation="attendances.confirm:x",
            idempotency_key="key-4",
            payload=payload,
            now=_NOW,
        )


def test_different_actor_same_key_does_not_collide() -> None:
    records = FakeIdempotencyRecordRepository()
    guard = IdempotencyGuard(records=records)
    payload: dict[str, list[object]] = {"items": []}

    first = guard.begin(
        actor_id=_ACTOR_ID,
        operation="attendances.confirm:x",
        idempotency_key="key-5",
        payload=payload,
        now=_NOW,
    )
    guard.complete(first.record_id, status_code=200, body={}, now=_NOW)

    other_actor_outcome = guard.begin(
        actor_id=uuid4(),
        operation="attendances.confirm:x",
        idempotency_key="key-5",
        payload=payload,
        now=_NOW,
    )

    assert other_actor_outcome.replayed_response is None


def test_different_operation_same_key_does_not_collide() -> None:
    records = FakeIdempotencyRecordRepository()
    guard = IdempotencyGuard(records=records)
    payload: dict[str, list[object]] = {"items": []}

    first = guard.begin(
        actor_id=_ACTOR_ID,
        operation="attendances.confirm:x",
        idempotency_key="key-6",
        payload=payload,
        now=_NOW,
    )
    guard.complete(first.record_id, status_code=200, body={}, now=_NOW)

    other_operation_outcome = guard.begin(
        actor_id=_ACTOR_ID,
        operation="attendances.confirm:y",
        idempotency_key="key-6",
        payload=payload,
        now=_NOW,
    )

    assert other_operation_outcome.replayed_response is None
