from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.modules.identity.domain.entities import Session, User
from app.modules.identity.domain.value_objects import Email

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_session_is_valid_before_expiry_and_invalid_after() -> None:
    session = Session(
        id=uuid4(),
        user_id=uuid4(),
        token_hash="hash",
        created_at=_NOW,
        last_seen_at=_NOW,
        expires_at=_NOW + timedelta(minutes=30),
    )

    assert session.is_valid(now=_NOW)
    assert not session.is_valid(now=_NOW + timedelta(minutes=31))


def test_session_revoke_is_idempotent() -> None:
    session = Session(
        id=uuid4(),
        user_id=uuid4(),
        token_hash="hash",
        created_at=_NOW,
        last_seen_at=_NOW,
        expires_at=_NOW + timedelta(minutes=30),
    )

    session.revoke(now=_NOW + timedelta(minutes=1))
    first_revocation = session.revoked_at
    session.revoke(now=_NOW + timedelta(minutes=2))

    assert session.revoked_at == first_revocation
    assert not session.is_valid(now=_NOW + timedelta(minutes=1))


def test_user_deactivate_is_idempotent() -> None:
    user = User(
        id=uuid4(),
        email=Email("someone@vertere.local"),
        full_name="Someone",
        password_hash="hash",
        role_id=uuid4(),
        created_at=_NOW,
        updated_at=_NOW,
    )

    user.deactivate(now=_NOW + timedelta(minutes=1))
    first_updated_at = user.updated_at
    user.deactivate(now=_NOW + timedelta(minutes=2))

    assert user.is_active is False
    assert user.updated_at == first_updated_at
