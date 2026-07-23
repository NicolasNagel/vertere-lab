from __future__ import annotations

from app.core.security import generate_session_token, hash_session_token


class OpaqueSessionTokens:
    def generate(self) -> str:
        return generate_session_token()

    def hash(self, token: str) -> str:
        return hash_session_token(token)
