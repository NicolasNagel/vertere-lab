"""Authentication primitives: password hashing and session tokens.

Kept deliberately small and framework-free (no FastAPI/SQLAlchemy import) so
`domain`/`application` layers can depend on the protocols in
`app.modules.identity.application.password_hasher` /
`...session_tokens` while `infrastructure` wires these concrete functions in.

Password hashing uses Argon2id (OWASP-recommended, memory-hard) via
`argon2-cffi` — see docs/adr/001-autenticacao-sessao-opaca-argon2.md.

Session tokens are opaque, high-entropy random strings. The token itself is
only ever held by the client (cookie); the server stores a SHA-256 hash of
it. SHA-256 is intentionally *not* a slow password hash here: the token
already has ~256 bits of entropy, so a fast, deterministic, indexable hash is
correct — a memory-hard hash would only add latency to every request without
adding real resistance (there is nothing to brute-force offline).
"""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_password_hasher = PasswordHasher()

SESSION_TOKEN_BYTES = 32  # 256 bits of entropy


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except VerifyMismatchError:
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
