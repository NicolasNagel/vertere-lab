from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.identity.application.update_role_permissions import (
    UpdateRolePermissionsCommand,
    UpdateRolePermissionsUseCase,
)
from app.modules.identity.domain.entities import Role, RoleScope
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from tests.identity.fakes import FakeAuditLogWriter, FakePermissionRepository, FakeRoleRepository


def _setup() -> tuple[FakeRoleRepository, FakePermissionRepository, Role]:
    roles = FakeRoleRepository()
    permissions = FakePermissionRepository(codes=frozenset({"clinics.read", "clinics.manage"}))
    role = Role(
        id=uuid4(),
        name="RECEPTION",
        scope=RoleScope.LAB,
        permission_codes=frozenset({"clinics.read"}),
        row_version=1,
    )
    roles.add(role)
    return roles, permissions, role


def _actor(permission_codes: frozenset[str]) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        id=uuid4(),
        email="actor@vertere.local",
        full_name="Actor",
        role_id=uuid4(),
        role_name="LAB_ADMIN",
        permissions=permission_codes,
    )


def test_update_role_permissions_succeeds_and_bumps_row_version() -> None:
    roles, permissions, role = _setup()
    audit = FakeAuditLogWriter()
    use_case = UpdateRolePermissionsUseCase(roles=roles, permissions=permissions, audit=audit)
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
    roles, permissions, role = _setup()
    use_case = UpdateRolePermissionsUseCase(
        roles=roles, permissions=permissions, audit=FakeAuditLogWriter()
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
    roles, permissions, _role = _setup()
    use_case = UpdateRolePermissionsUseCase(
        roles=roles, permissions=permissions, audit=FakeAuditLogWriter()
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
    roles, permissions, role = _setup()
    use_case = UpdateRolePermissionsUseCase(
        roles=roles, permissions=permissions, audit=FakeAuditLogWriter()
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
    roles, permissions, role = _setup()
    use_case = UpdateRolePermissionsUseCase(
        roles=roles, permissions=permissions, audit=FakeAuditLogWriter()
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
