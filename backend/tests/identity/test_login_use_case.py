from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.identity.application.login import LoginCommand, LoginUseCase
from app.modules.identity.domain.entities import Role, RoleScope, User
from app.modules.identity.domain.errors import AccountInactiveError, InvalidCredentialsError
from app.modules.identity.domain.value_objects import Email
from tests.identity.fakes import (
    FakeAuditLogWriter,
    FakeClock,
    FakePasswordHasher,
    FakeRoleRepository,
    FakeSessionRepository,
    FakeSessionTokens,
    FakeUserRepository,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _make_use_case() -> tuple[
    LoginUseCase, FakeUserRepository, FakeRoleRepository, FakeAuditLogWriter
]:
    roles = FakeRoleRepository()
    users = FakeUserRepository(roles=roles)
    sessions = FakeSessionRepository()
    audit = FakeAuditLogWriter()
    use_case = LoginUseCase(
        users=users,
        roles=roles,
        sessions=sessions,
        password_hasher=FakePasswordHasher(),
        token_generator=FakeSessionTokens(),
        audit=audit,
        clock=FakeClock(_NOW),
        session_ttl=timedelta(minutes=30),
        session_ttl_remember_me=timedelta(days=30),
    )
    return use_case, users, roles, audit


def _add_user(
    users: FakeUserRepository, roles: FakeRoleRepository, *, is_active: bool = True
) -> User:
    role = Role(
        id=uuid4(),
        name="RECEPTION",
        scope=RoleScope.LAB,
        permission_codes=frozenset({"attendances.read"}),
    )
    roles.add(role)
    user = User(
        id=uuid4(),
        email=Email("reception@vertere.local"),
        full_name="Recepção",
        password_hash="hashed::correct-password",
        is_active=is_active,
        role_id=role.id,
        created_at=_NOW,
        updated_at=_NOW,
    )
    users.add(user)
    return user


def test_login_succeeds_for_active_user_with_correct_password() -> None:
    use_case, users, roles, audit = _make_use_case()
    _add_user(users, roles)

    result = use_case.execute(
        LoginCommand(
            login="reception@vertere.local",
            password="correct-password",
            remember_me=False,
            ip_address=None,
            user_agent=None,
            request_id=None,
        )
    )

    assert result.user.email == "reception@vertere.local"
    assert "attendances.read" in result.user.permissions
    assert audit.entries[-1].action == "auth.login_succeeded"


def test_login_rejects_unknown_user_and_wrong_password_identically() -> None:
    use_case, users, roles, _audit = _make_use_case()
    _add_user(users, roles)

    with pytest.raises(InvalidCredentialsError) as unknown_exc:
        use_case.execute(
            LoginCommand(
                login="nobody@vertere.local",
                password="whatever",
                remember_me=False,
                ip_address=None,
                user_agent=None,
                request_id=None,
            )
        )

    with pytest.raises(InvalidCredentialsError) as wrong_password_exc:
        use_case.execute(
            LoginCommand(
                login="reception@vertere.local",
                password="wrong-password",
                remember_me=False,
                ip_address=None,
                user_agent=None,
                request_id=None,
            )
        )

    assert str(unknown_exc.value) == str(wrong_password_exc.value)
    assert unknown_exc.value.code == wrong_password_exc.value.code


def test_login_rejects_inactive_user_after_password_matches() -> None:
    use_case, users, roles, audit = _make_use_case()
    _add_user(users, roles, is_active=False)

    with pytest.raises(AccountInactiveError):
        use_case.execute(
            LoginCommand(
                login="reception@vertere.local",
                password="correct-password",
                remember_me=False,
                ip_address=None,
                user_agent=None,
                request_id=None,
            )
        )

    assert audit.entries[-1].after_state == {"reason": "inactive"}
