from __future__ import annotations

from app.core.security import verify_against_unknown_user


def test_unknown_user_verification_runs_with_the_real_hasher_and_never_raises() -> None:
    """The timing equalizer must not blow up on any password (a raise would be a 500 + an oracle)."""
    for password in ("", "wrong-password", "senha-com-acentuação-ção", "x" * 5000):
        verify_against_unknown_user(password)
