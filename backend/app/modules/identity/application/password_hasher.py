from __future__ import annotations

from typing import Protocol


class PasswordHasher(Protocol):
    def hash(self, plain_password: str) -> str: ...

    def verify(self, plain_password: str, password_hash: str) -> bool: ...

    def verify_against_unknown_user(self, plain_password: str) -> None:
        """Burn the same CPU as `verify` so an unknown login is not faster than a wrong password."""
        ...
