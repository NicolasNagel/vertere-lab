from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.identity.application.login import LoginCommand, LoginUseCase
from app.modules.identity.domain.entities import (
    ClinicMembership,
    LabMembership,
    Role,
    RoleScope,
    User,
)
from app.modules.identity.domain.errors import AccountInactiveError, InvalidCredentialsError
from app.modules.identity.domain.value_objects import Email
from app.shared.domain.errors import RateLimitedError
from tests.identity.fakes import (
    FakeAuditLogWriter,
    FakeClinicMembershipRepository,
    FakeClock,
    FakeLabMembershipRepository,
    FakeLoginFailureRepository,
    FakePasswordHasher,
    FakeRoleRepository,
    FakeSessionRepository,
    FakeSessionTokens,
    FakeUserRepository,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _make_use_case(
    *, max_attempts: int = 5
) -> tuple[
    LoginUseCase,
    FakeUserRepository,
    FakeRoleRepository,
    FakeLabMembershipRepository,
    FakeAuditLogWriter,
]:
    roles = FakeRoleRepository()
    users = FakeUserRepository(roles=roles)
    sessions = FakeSessionRepository()
    audit = FakeAuditLogWriter()
    memberships = FakeLabMembershipRepository()
    clinic_memberships = FakeClinicMembershipRepository()
    use_case = LoginUseCase(
        users=users,
        roles=roles,
        sessions=sessions,
        memberships=memberships,
        clinic_memberships=clinic_memberships,
        login_failures=FakeLoginFailureRepository(),
        password_hasher=FakePasswordHasher(),
        token_generator=FakeSessionTokens(),
        audit=audit,
        clock=FakeClock(_NOW),
        session_ttl=timedelta(minutes=30),
        session_ttl_remember_me=timedelta(days=30),
        rate_limit_max_attempts=max_attempts,
        rate_limit_window=timedelta(minutes=15),
    )
    return use_case, users, roles, memberships, audit


def _add_user(
    users: FakeUserRepository,
    roles: FakeRoleRepository,
    memberships: FakeLabMembershipRepository,
    *,
    is_active: bool = True,
    scope: RoleScope = RoleScope.LAB,
) -> User:
    role = Role(
        id=uuid4(),
        name="RECEPTION",
        scope=scope,
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
    memberships.add(LabMembership(id=uuid4(), user_id=user.id, granted_at=_NOW))
    return user


def test_login_succeeds_for_active_user_with_correct_password() -> None:
    use_case, users, roles, memberships, audit = _make_use_case()
    _add_user(users, roles, memberships)

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


def test_login_accepts_clinic_role_with_active_clinic_membership() -> None:
    use_case, users, roles, memberships, audit = _make_use_case()
    user = _add_user(users, roles, memberships, scope=RoleScope.CLINIC)
    clinic_id = uuid4()
    use_case._clinic_memberships.add(
        ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=clinic_id, granted_at=_NOW)
    )

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
    assert result.user.role_scope == "CLINIC"
    assert result.user.clinic_ids == frozenset({clinic_id})
    assert audit.entries[-1].action == "auth.login_succeeded"


def test_login_rejects_internal_user_without_active_lab_membership() -> None:
    use_case, users, roles, memberships, audit = _make_use_case()
    _add_user(users, roles, memberships)
    memberships.memberships.clear()

    with pytest.raises(InvalidCredentialsError):
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

    assert audit.entries[-1].after_state == {"reason": "internal_access_unavailable"}


def test_login_rejects_unknown_user_and_wrong_password_identically() -> None:
    use_case, users, roles, memberships, _audit = _make_use_case()
    _add_user(users, roles, memberships)

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
    use_case, users, roles, memberships, audit = _make_use_case()
    _add_user(users, roles, memberships, is_active=False)

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


def _wrong_password_attempt(use_case: LoginUseCase, login: str) -> None:
    with pytest.raises(InvalidCredentialsError):
        use_case.execute(
            LoginCommand(
                login=login,
                password="wrong-password",
                remember_me=False,
                ip_address=None,
                user_agent=None,
                request_id=None,
            )
        )


def test_login_is_rate_limited_after_max_attempts() -> None:
    use_case, users, roles, memberships, audit = _make_use_case(max_attempts=3)
    _add_user(users, roles, memberships)

    for _ in range(3):
        _wrong_password_attempt(use_case, "reception@vertere.local")

    with pytest.raises(RateLimitedError):
        use_case.execute(
            LoginCommand(
                login="reception@vertere.local",
                password="correct-password",  # mesmo a senha certa não passa
                remember_me=False,
                ip_address=None,
                user_agent=None,
                request_id=None,
            )
        )
    assert audit.entries[-1].action == "auth.login_rate_limited"


def test_login_rate_limit_is_keyed_by_login_not_shared_globally() -> None:
    use_case, users, roles, memberships, _audit = _make_use_case(max_attempts=3)
    _add_user(users, roles, memberships)
    role = Role(id=uuid4(), name="FINANCE", scope=RoleScope.LAB, permission_codes=frozenset())
    roles.add(role)
    other_user = User(
        id=uuid4(),
        email=Email("other@vertere.local"),
        full_name="Other",
        password_hash="hashed::other-password",
        role_id=role.id,
        created_at=_NOW,
        updated_at=_NOW,
    )
    users.add(other_user)
    memberships.add(LabMembership(id=uuid4(), user_id=other_user.id, granted_at=_NOW))

    for _ in range(3):
        _wrong_password_attempt(use_case, "reception@vertere.local")

    # A conta atacada está bloqueada, mas uma conta diferente não é afetada.
    result = use_case.execute(
        LoginCommand(
            login="other@vertere.local",
            password="other-password",
            remember_me=False,
            ip_address=None,
            user_agent=None,
            request_id=None,
        )
    )
    assert result.user.email == "other@vertere.local"


def test_successful_login_clears_the_failure_count() -> None:
    use_case, users, roles, memberships, _audit = _make_use_case(max_attempts=3)
    _add_user(users, roles, memberships)

    _wrong_password_attempt(use_case, "reception@vertere.local")
    _wrong_password_attempt(use_case, "reception@vertere.local")

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

    # O contador zerou — mais uma tentativa errada não deveria já bloquear.
    _wrong_password_attempt(use_case, "reception@vertere.local")
