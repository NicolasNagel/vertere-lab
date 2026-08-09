"""Transactional handlers for session resolution and sliding renewal."""

from __future__ import annotations

from datetime import timedelta

from app.modules.identity.application.get_current_user import (
    ResolveSessionCommand,
    ResolveSessionUseCase,
)
from app.modules.identity.application.session_tokens import SessionTokenGenerator
from app.modules.identity.application.uow import IdentityUnitOfWork
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock


def handle_resolve_session(
    *,
    uow: IdentityUnitOfWork,
    command: ResolveSessionCommand,
    token_generator: SessionTokenGenerator,
    clock: Clock,
    session_ttl: timedelta,
    session_ttl_remember_me: timedelta,
    renewal_threshold: timedelta,
) -> ActorContext:
    with uow:
        actor = ResolveSessionUseCase(
            sessions=uow.sessions,
            users=uow.users,
            roles=uow.roles,
            memberships=uow.lab_memberships,
            clinic_memberships=uow.clinic_memberships,
            token_generator=token_generator,
            clock=clock,
            session_ttl=session_ttl,
            session_ttl_remember_me=session_ttl_remember_me,
            renewal_threshold=renewal_threshold,
        ).execute(command)
        uow.commit()
        return actor
