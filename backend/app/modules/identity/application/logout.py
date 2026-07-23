from __future__ import annotations

from dataclasses import dataclass

from app.modules.identity.application.session_tokens import SessionTokenGenerator
from app.modules.identity.domain.repositories import SessionRepository
from app.shared.application.clock import Clock


@dataclass(frozen=True, kw_only=True)
class LogoutCommand:
    token: str


class LogoutUseCase:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        token_generator: SessionTokenGenerator,
        clock: Clock,
    ) -> None:
        self._sessions = sessions
        self._token_generator = token_generator
        self._clock = clock

    def execute(self, command: LogoutCommand) -> None:
        token_hash = self._token_generator.hash(command.token)
        session = self._sessions.get_by_token_hash(token_hash)
        if session is None:
            return
        session.revoke(now=self._clock.now())
        self._sessions.save(session)
