from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.identity.application.assign_role import AssignRoleCommand, AssignRoleUseCase
from app.modules.identity.application.deactivate_user import (
    DeactivateUserCommand,
    DeactivateUserUseCase,
)
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.identity.domain.constants import CONTROL_PERMISSIONS
from app.modules.identity.domain.entities import Role, RoleScope, User
from app.modules.identity.domain.errors import SelfLockoutError
from app.modules.identity.domain.value_objects import Email
from tests.identity.fakes import (
    FakeAuditLogWriter,
    FakeClock,
    FakeRoleRepository,
    FakeSessionRepository,
    FakeUserRepository,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_ADMIN_PERMISSIONS = CONTROL_PERMISSIONS


def _setup_single_admin() -> tuple[FakeUserRepository, FakeRoleRepository, User, Role, Role]:
    roles = FakeRoleRepository()
    users = FakeUserRepository(roles=roles)

    admin_role = Role(
        id=uuid4(), name="LAB_ADMIN", scope=RoleScope.LAB, permission_codes=_ADMIN_PERMISSIONS
    )
    powerless_role = Role(
        id=uuid4(), name="RECEPTION", scope=RoleScope.LAB, permission_codes=frozenset()
    )
    roles.add(admin_role)
    roles.add(powerless_role)

    admin = User(
        id=uuid4(),
        email=Email("admin@vertere.local"),
        full_name="Admin",
        password_hash="hash",
        role_id=admin_role.id,
        created_at=_NOW,
        updated_at=_NOW,
    )
    users.add(admin)
    return users, roles, admin, admin_role, powerless_role


def test_the_only_admin_cannot_demote_or_deactivate_themselves_unless_another_admin_exists() -> (
    None
):
    users, roles, admin, admin_role, powerless_role = _setup_single_admin()
    sessions = FakeSessionRepository()
    audit = FakeAuditLogWriter()
    assign = AssignRoleUseCase(
        users=users, roles=roles, sessions=sessions, audit=audit, clock=FakeClock(_NOW)
    )
    deactivate = DeactivateUserUseCase(
        users=users, roles=roles, sessions=sessions, audit=audit, clock=FakeClock(_NOW)
    )
    actor = AuthenticatedUserDTO(
        user_id=admin.id,
        email=str(admin.email),
        full_name=admin.full_name,
        role_id=admin_role.id,
        role_name=admin_role.name,
        permissions=admin_role.permission_codes,
    )

    with pytest.raises(SelfLockoutError):
        assign.execute(
            AssignRoleCommand(actor=actor, user_id=admin.id, new_role_id=powerless_role.id)
        )
    with pytest.raises(SelfLockoutError):
        deactivate.execute(DeactivateUserCommand(actor=actor, user_id=admin.id))
    stored = users.get_by_id(admin.id)
    assert stored is not None
    assert (stored.role_id, stored.is_active) == (admin_role.id, True)

    users.add(
        User(
            id=uuid4(),
            email=Email("second-admin@vertere.local"),
            full_name="Second Admin",
            password_hash="hash",
            role_id=admin_role.id,
            created_at=_NOW,
            updated_at=_NOW,
        )
    )
    result = assign.execute(
        AssignRoleCommand(actor=actor, user_id=admin.id, new_role_id=powerless_role.id)
    )
    assert result.role_id == powerless_role.id
