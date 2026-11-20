from __future__ import annotations

from app.core.security import hash_password, verify_against_unknown_user, verify_password


class Argon2PasswordHasher:
    def hash(self, plain_password: str) -> str:
        return hash_password(plain_password)

    def verify(self, plain_password: str, password_hash: str) -> bool:
        return verify_password(plain_password, password_hash)

    def verify_against_unknown_user(self, plain_password: str) -> None:
        verify_against_unknown_user(plain_password)
