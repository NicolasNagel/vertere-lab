from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.identity.application.dtos import SessionIssuedDTO
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
    email: str = "reception@vertere.local",
    password: str = "correct-password",
    is_active: bool = True,
    scope: RoleScope = RoleScope.LAB,
    with_lab_membership: bool = True,
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
        email=Email(email),
        full_name="Recepção",
        password_hash=f"hashed::{password}",
        is_active=is_active,
        role_id=role.id,
        created_at=_NOW,
        updated_at=_NOW,
    )
    users.add(user)
    if with_lab_membership:
        memberships.add(LabMembership(id=uuid4(), user_id=user.id, granted_at=_NOW))
    return user


def _login(
    use_case: LoginUseCase, login: str, password: str = "correct-password"
) -> SessionIssuedDTO:
    return use_case.execute(
        LoginCommand(
            login=login,
            password=password,
            remember_me=False,
            ip_address=None,
            user_agent=None,
            request_id=None,
        )
    )


def test_login_only_admits_active_users_with_the_right_membership() -> None:
    use_case, users, roles, memberships, audit = _make_use_case()
    _add_user(users, roles, memberships)
    clinic_user = _add_user(
        users,
        roles,
        memberships,
        email="clinic@vertere.local",
        scope=RoleScope.CLINIC,
        with_lab_membership=False,
    )
    clinic_id = uuid4()
    use_case._clinic_memberships.add(
        ClinicMembership(id=uuid4(), user_id=clinic_user.id, clinic_id=clinic_id, granted_at=_NOW)
    )
    _add_user(users, roles, memberships, email="nolab@vertere.local", with_lab_membership=False)
    _add_user(users, roles, memberships, email="inactive@vertere.local", is_active=False)

    lab = _login(use_case, "reception@vertere.local")
    assert lab.user.email == "reception@vertere.local"
    assert "attendances.read" in lab.user.permissions
    assert audit.entries[-1].action == "auth.login_succeeded"

    clinic = _login(use_case, "clinic@vertere.local")
    assert (clinic.user.role_scope, clinic.user.clinic_ids) == ("CLINIC", frozenset({clinic_id}))

    with pytest.raises(InvalidCredentialsError):  # usuário interno sem vínculo ativo com o lab
        _login(use_case, "nolab@vertere.local")
    assert audit.entries[-1].after_state == {"reason": "internal_access_unavailable"}

    with pytest.raises(AccountInactiveError):
        _login(use_case, "inactive@vertere.local")
    assert audit.entries[-1].after_state == {"reason": "inactive"}

    # Usuário inexistente e senha errada são indistinguíveis para quem tenta.
    with pytest.raises(InvalidCredentialsError) as unknown:
        _login(use_case, "nobody@vertere.local", "whatever")
    with pytest.raises(InvalidCredentialsError) as wrong_password:
        _login(use_case, "reception@vertere.local", "wrong-password")
    assert str(unknown.value) == str(wrong_password.value)
    assert unknown.value.code == wrong_password.value.code


def test_login_rate_limit_is_per_login_and_cleared_by_a_successful_login() -> None:
    use_case, users, roles, memberships, audit = _make_use_case(max_attempts=3)
    _add_user(users, roles, memberships, email="attacked@vertere.local")
    _add_user(users, roles, memberships, email="other@vertere.local", password="other-password")
    _add_user(users, roles, memberships, email="typo@vertere.local")

    for _ in range(3):
        with pytest.raises(InvalidCredentialsError):
            _login(use_case, "attacked@vertere.local", "wrong-password")
    with pytest.raises(RateLimitedError):  # nem a senha certa passa depois do limite
        _login(use_case, "attacked@vertere.local")
    assert audit.entries[-1].action == "auth.login_rate_limited"

    # O bloqueio é por login: outra conta continua entrando.
    assert _login(use_case, "other@vertere.local", "other-password").user.email == (
        "other@vertere.local"
    )

    # Errar abaixo do limite e acertar zera a contagem.
    for _ in range(2):
        with pytest.raises(InvalidCredentialsError):
            _login(use_case, "typo@vertere.local", "wrong-password")
    assert _login(use_case, "typo@vertere.local").user.email == "typo@vertere.local"
    for _ in range(2):
        with pytest.raises(InvalidCredentialsError):
            _login(use_case, "typo@vertere.local", "wrong-password")
    assert _login(use_case, "typo@vertere.local").user.email == "typo@vertere.local"


def test_unknown_login_spends_the_same_hash_work_as_a_wrong_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QA 2026-11-19: unknown e-mails answered ~4x faster than wrong passwords (timing oracle)."""
    calls: list[str] = []
    monkeypatch.setattr(
        FakePasswordHasher,
        "verify_against_unknown_user",
        lambda _self, plain_password: calls.append(plain_password),
    )
    use_case, users, roles, memberships, _audit = _make_use_case()
    _add_user(users, roles, memberships)

    with pytest.raises(InvalidCredentialsError):
        _login(use_case, "nobody@vertere.local", "whatever")
    assert calls == ["whatever"]

    with pytest.raises(InvalidCredentialsError):
        _login(use_case, "reception@vertere.local", "wrong-password")
    assert calls == ["whatever"]  # a real account is verified against its own hash instead
