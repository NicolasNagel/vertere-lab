from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.identity.application.activate_user import (
    ActivateUserCommand,
    ActivateUserUseCase,
)
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.identity.domain.entities import Role, RoleScope, User
from app.modules.identity.domain.value_objects import Email
from app.shared.domain.errors import ForbiddenError, NotFoundError
from tests.identity.fakes import (
    FakeAuditLogWriter,
    FakeClock,
    FakeRoleRepository,
    FakeUserRepository,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _setup() -> tuple[FakeUserRepository, FakeRoleRepository, User, Role]:
    roles = FakeRoleRepository()
    users = FakeUserRepository(roles=roles)

    admin_role = Role(
        id=uuid4(),
        name="LAB_ADMIN",
        scope=RoleScope.LAB,
        permission_codes=frozenset({"users.activate"}),
    )
    roles.add(admin_role)

    inactive_user = User(
        id=uuid4(),
        email=Email("inactive@vertere.local"),
        full_name="Inactive User",
        password_hash="hash",
        is_active=False,
        role_id=admin_role.id,
        created_at=_NOW,
        updated_at=_NOW,
    )
    users.add(inactive_user)
    return users, roles, inactive_user, admin_role


def _actor_from(admin: User, role: Role) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        user_id=admin.id,
        email=str(admin.email),
        full_name=admin.full_name,
        role_id=role.id,
        role_name=role.name,
        permissions=role.permission_codes,
    )


def test_activate_user_reactivates_and_audits() -> None:
    users, roles, target, admin_role = _setup()
    audit = FakeAuditLogWriter()
    use_case = ActivateUserUseCase(users=users, roles=roles, audit=audit, clock=FakeClock(_NOW))
    actor = _actor_from(target, admin_role)

    result = use_case.execute(ActivateUserCommand(actor=actor, user_id=target.id))

    assert result.is_active is True
    assert users.get_by_id(target.id).is_active is True  # type: ignore[union-attr]
    assert audit.entries[0].action == "users.activated"


def test_activate_user_without_permission_is_forbidden() -> None:
    users, roles, target, _admin_role = _setup()
    powerless_role = Role(
        id=uuid4(), name="RECEPTION", scope=RoleScope.LAB, permission_codes=frozenset()
    )
    roles.add(powerless_role)
    audit = FakeAuditLogWriter()
    use_case = ActivateUserUseCase(users=users, roles=roles, audit=audit, clock=FakeClock(_NOW))
    actor = _actor_from(target, powerless_role)

    with pytest.raises(ForbiddenError):
        use_case.execute(ActivateUserCommand(actor=actor, user_id=target.id))


def test_activate_unknown_user_raises_not_found() -> None:
    users, roles, target, admin_role = _setup()
    audit = FakeAuditLogWriter()
    use_case = ActivateUserUseCase(users=users, roles=roles, audit=audit, clock=FakeClock(_NOW))
    actor = _actor_from(target, admin_role)

    with pytest.raises(NotFoundError):
        use_case.execute(ActivateUserCommand(actor=actor, user_id=uuid4()))
