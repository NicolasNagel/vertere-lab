from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.identity.application.update_role_permissions import (
    UpdateRolePermissionsCommand,
    UpdateRolePermissionsUseCase,
)
from app.modules.identity.domain.entities import Role, RoleScope, User
from app.modules.identity.domain.errors import SelfLockoutError
from app.modules.identity.domain.value_objects import Email
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from tests.identity.fakes import (
    FakeAuditLogWriter,
    FakePermissionRepository,
    FakeRoleRepository,
    FakeUserRepository,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _setup() -> tuple[FakeRoleRepository, FakePermissionRepository, FakeUserRepository, Role]:
    roles = FakeRoleRepository()
    users = FakeUserRepository(roles=roles)
    permissions = FakePermissionRepository(
        codes=frozenset(
            {"clinics.read", "clinics.manage", "roles.manage", "attendances.view_prices"}
        )
    )
    role = Role(
        id=uuid4(),
        name="RECEPTION",
        scope=RoleScope.LAB,
        permission_codes=frozenset({"clinics.read"}),
        row_version=1,
    )
    roles.add(role)
    return roles, permissions, users, role


def _actor(permission_codes: frozenset[str]) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        user_id=uuid4(),
        email="actor@vertere.local",
        full_name="Actor",
        role_id=uuid4(),
        role_name="LAB_ADMIN",
        permissions=permission_codes,
    )


def test_update_role_permissions_succeeds_and_bumps_row_version() -> None:
    roles, permissions, users, role = _setup()
    audit = FakeAuditLogWriter()
    use_case = UpdateRolePermissionsUseCase(
        roles=roles, permissions=permissions, users=users, audit=audit
    )
    actor = _actor(frozenset({"roles.manage"}))

    result = use_case.execute(
        UpdateRolePermissionsCommand(
            actor=actor,
            role_id=role.id,
            permission_codes=frozenset({"clinics.read", "clinics.manage"}),
            expected_row_version=1,
        )
    )

    assert result.permissions == frozenset({"clinics.read", "clinics.manage"})
    assert result.row_version == 2
    assert audit.entries[0].action == "roles.permissions_updated"


def test_update_role_permissions_without_permission_is_forbidden() -> None:
    roles, permissions, users, role = _setup()
    use_case = UpdateRolePermissionsUseCase(
        roles=roles, permissions=permissions, users=users, audit=FakeAuditLogWriter()
    )
    actor = _actor(frozenset())

    with pytest.raises(ForbiddenError):
        use_case.execute(
            UpdateRolePermissionsCommand(
                actor=actor,
                role_id=role.id,
                permission_codes=frozenset({"clinics.read"}),
                expected_row_version=1,
            )
        )


def test_update_role_permissions_unknown_role_raises_not_found() -> None:
    roles, permissions, users, _role = _setup()
    use_case = UpdateRolePermissionsUseCase(
        roles=roles, permissions=permissions, users=users, audit=FakeAuditLogWriter()
    )
    actor = _actor(frozenset({"roles.manage"}))

    with pytest.raises(NotFoundError):
        use_case.execute(
            UpdateRolePermissionsCommand(
                actor=actor,
                role_id=uuid4(),
                permission_codes=frozenset({"clinics.read"}),
                expected_row_version=1,
            )
        )


def test_update_role_permissions_unknown_code_is_validation_error() -> None:
    roles, permissions, users, role = _setup()
    use_case = UpdateRolePermissionsUseCase(
        roles=roles, permissions=permissions, users=users, audit=FakeAuditLogWriter()
    )
    actor = _actor(frozenset({"roles.manage"}))

    with pytest.raises(ValidationError):
        use_case.execute(
            UpdateRolePermissionsCommand(
                actor=actor,
                role_id=role.id,
                permission_codes=frozenset({"does.not_exist"}),
                expected_row_version=1,
            )
        )


def test_update_role_permissions_stale_row_version_is_conflict() -> None:
    roles, permissions, users, role = _setup()
    use_case = UpdateRolePermissionsUseCase(
        roles=roles, permissions=permissions, users=users, audit=FakeAuditLogWriter()
    )
    actor = _actor(frozenset({"roles.manage"}))

    with pytest.raises(ConflictError):
        use_case.execute(
            UpdateRolePermissionsCommand(
                actor=actor,
                role_id=role.id,
                permission_codes=frozenset({"clinics.read"}),
                expected_row_version=99,
            )
        )


def test_update_role_permissions_rejects_master_only_permission_for_a_lab_scope_role() -> None:
    roles, permissions, users, role = _setup()
    use_case = UpdateRolePermissionsUseCase(
        roles=roles, permissions=permissions, users=users, audit=FakeAuditLogWriter()
    )
    actor = _actor(frozenset({"roles.manage"}))

    with pytest.raises(ValidationError):
        use_case.execute(
            UpdateRolePermissionsCommand(
                actor=actor,
                role_id=role.id,
                permission_codes=frozenset({"clinics.read", "attendances.view_prices"}),
                expected_row_version=1,
            )
        )

    # Não é meio-caminho: o papel continua exatamente como estava.
    assert roles.get_by_id(role.id).permission_codes == frozenset({"clinics.read"})  # type: ignore[union-attr]


def test_update_role_permissions_allows_master_only_permission_for_a_global_scope_role() -> None:
    roles = FakeRoleRepository()
    users = FakeUserRepository(roles=roles)
    permissions = FakePermissionRepository(
        codes=frozenset({"clinics.read", "roles.manage", "attendances.view_prices"})
    )
    role = Role(
        id=uuid4(),
        name="SUPER_ADMIN",
        scope=RoleScope.GLOBAL,
        permission_codes=frozenset({"clinics.read"}),
        row_version=1,
    )
    roles.add(role)
    use_case = UpdateRolePermissionsUseCase(
        roles=roles, permissions=permissions, users=users, audit=FakeAuditLogWriter()
    )
    actor = _actor(frozenset({"roles.manage"}))

    result = use_case.execute(
        UpdateRolePermissionsCommand(
            actor=actor,
            role_id=role.id,
            permission_codes=frozenset({"clinics.read", "attendances.view_prices"}),
            expected_row_version=1,
        )
    )

    assert result.permissions == frozenset({"clinics.read", "attendances.view_prices"})


def _setup_sole_admin() -> tuple[
    FakeRoleRepository, FakePermissionRepository, FakeUserRepository, Role, User
]:
    """One role holding `roles.manage`, with exactly one active user in it —
    the exact scenario proven live in manual testing (ADR-007): editing this
    role's own permissions to drop `roles.manage` used to succeed silently
    and lock the whole system out of ever managing permissions again."""
    roles = FakeRoleRepository()
    users = FakeUserRepository(roles=roles)
    permissions = FakePermissionRepository(codes=frozenset({"clinics.read", "roles.manage"}))
    admin_role = Role(
        id=uuid4(),
        name="SUPER_ADMIN",
        scope=RoleScope.GLOBAL,
        permission_codes=frozenset({"roles.manage", "clinics.read"}),
        row_version=1,
    )
    roles.add(admin_role)
    admin_user = User(
        id=uuid4(),
        email=Email("admin@vertere.local"),
        full_name="Admin",
        password_hash="hash",
        role_id=admin_role.id,
        created_at=_NOW,
        updated_at=_NOW,
    )
    users.add(admin_user)
    return roles, permissions, users, admin_role, admin_user


def test_update_role_permissions_blocks_removing_the_last_roles_manage() -> None:
    roles, permissions, users, admin_role, admin_user = _setup_sole_admin()
    use_case = UpdateRolePermissionsUseCase(
        roles=roles, permissions=permissions, users=users, audit=FakeAuditLogWriter()
    )
    actor = AuthenticatedUserDTO(
        user_id=admin_user.id,
        email=str(admin_user.email),
        full_name=admin_user.full_name,
        role_id=admin_role.id,
        role_name=admin_role.name,
        permissions=admin_role.permission_codes,
    )

    with pytest.raises(SelfLockoutError):
        use_case.execute(
            UpdateRolePermissionsCommand(
                actor=actor,
                role_id=admin_role.id,
                permission_codes=frozenset({"clinics.read"}),
                expected_row_version=1,
            )
        )

    # Não é meio-caminho: o papel continua exatamente como estava.
    assert roles.get_by_id(admin_role.id).permission_codes == frozenset(  # type: ignore[union-attr]
        {"roles.manage", "clinics.read"}
    )


def test_update_role_permissions_allows_removal_when_another_role_still_covers_it() -> None:
    roles, permissions, users, admin_role, admin_user = _setup_sole_admin()
    second_admin_role = Role(
        id=uuid4(),
        name="SECOND_ADMIN",
        scope=RoleScope.GLOBAL,
        permission_codes=frozenset({"roles.manage"}),
        row_version=1,
    )
    roles.add(second_admin_role)
    second_admin_user = User(
        id=uuid4(),
        email=Email("second-admin@vertere.local"),
        full_name="Second Admin",
        password_hash="hash",
        role_id=second_admin_role.id,
        created_at=_NOW,
        updated_at=_NOW,
    )
    users.add(second_admin_user)

    use_case = UpdateRolePermissionsUseCase(
        roles=roles, permissions=permissions, users=users, audit=FakeAuditLogWriter()
    )
    actor = AuthenticatedUserDTO(
        user_id=admin_user.id,
        email=str(admin_user.email),
        full_name=admin_user.full_name,
        role_id=admin_role.id,
        role_name=admin_role.name,
        permissions=admin_role.permission_codes,
    )

    result = use_case.execute(
        UpdateRolePermissionsCommand(
            actor=actor,
            role_id=admin_role.id,
            permission_codes=frozenset({"clinics.read"}),
            expected_row_version=1,
        )
    )

    assert result.permissions == frozenset({"clinics.read"})
