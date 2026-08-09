from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import cast
from uuid import uuid4

import pytest

from app.modules.identity.application import session_handlers
from app.modules.identity.application.get_current_user import ResolveSessionCommand
from app.modules.identity.application.uow import IdentityUnitOfWork
from app.shared.application.authorization import ActorContext
from tests.identity.fakes import FakeClock, FakeSessionTokens


class FakeIdentityUnitOfWork:
    def __init__(self) -> None:
        repository = object()
        self.users = repository
        self.roles = repository
        self.sessions = repository
        self.lab_memberships = repository
        self.clinic_memberships = repository
        self.login_failures = repository
        self.permissions = repository
        self.audit = repository
        self.commit_count = 0
        self.exit_exception_type: type[BaseException] | None = None

    def __enter__(self) -> FakeIdentityUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.exit_exception_type = exc_type

    def commit(self) -> None:
        self.commit_count += 1


class StubResolveSessionUseCase:
    def __init__(self, actor: ActorContext) -> None:
        self._actor = actor

    def execute(self, command: ResolveSessionCommand) -> ActorContext:
        return self._actor


class FailingResolveSessionUseCase:
    def execute(self, command: ResolveSessionCommand) -> ActorContext:
        raise RuntimeError("resolution failed")


def _call_handler(uow: FakeIdentityUnitOfWork) -> ActorContext:
    return session_handlers.handle_resolve_session(
        uow=cast(IdentityUnitOfWork, uow),
        command=ResolveSessionCommand(token="opaque-token"),
        token_generator=FakeSessionTokens(),
        clock=FakeClock(datetime(2026, 8, 9, tzinfo=UTC)),
        session_ttl=timedelta(minutes=30),
        session_ttl_remember_me=timedelta(days=30),
        renewal_threshold=timedelta(minutes=10),
    )


def test_resolve_session_commits_sliding_renewal_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = ActorContext(
        user_id=uuid4(),
        email="actor@qa.local",
        full_name="Actor",
        role_id=uuid4(),
        role_name="LAB",
        role_scope="LAB",
        permissions=frozenset(),
    )
    monkeypatch.setattr(
        session_handlers,
        "ResolveSessionUseCase",
        lambda **kwargs: StubResolveSessionUseCase(actor),
    )
    uow = FakeIdentityUnitOfWork()

    assert _call_handler(uow) is actor
    assert uow.commit_count == 1
    assert uow.exit_exception_type is None


def test_resolve_session_failure_never_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        session_handlers,
        "ResolveSessionUseCase",
        lambda **kwargs: FailingResolveSessionUseCase(),
    )
    uow = FakeIdentityUnitOfWork()

    with pytest.raises(RuntimeError, match="resolution failed"):
        _call_handler(uow)

    assert uow.commit_count == 0
    assert uow.exit_exception_type is RuntimeError
