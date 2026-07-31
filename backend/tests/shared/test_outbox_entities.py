from __future__ import annotations

from app.shared.outbox.domain.entities import OutboxEvent, OutboxEventStatus


def test_outbox_event_defaults_to_pending() -> None:
    event = OutboxEvent(event_type="closures.closed", payload={"closure_id": "abc"})
    assert event.status == OutboxEventStatus.PENDING
    assert event.processed_at is None
