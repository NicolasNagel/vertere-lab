from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.identity.application.create_role import CreateRoleCommand, CreateRoleUseCase
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.identity.domain.entities import RoleScope
from app.shared.domain.errors import ForbiddenError, ValidationError
from tests.identity.fakes import FakeAuditLogWriter, FakePermissionRepository, FakeRoleRepository

_PERMISSION_CODES = frozenset({"clinics.read", "roles.manage", "attendances.view_prices"})


def _actor(permission_codes: frozenset[str]) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        user_id=uuid4(),
        email="actor@vertere.local",
        full_name="Actor",
        role_id=uuid4(),
        role_name="LAB_ADMIN",
        permissions=permission_codes,
    )


def test_create_role_succeeds_for_a_lab_scope_role() -> None:
    roles = FakeRoleRepository()
    use_case = CreateRoleUseCase(
        roles=roles,
        permissions=FakePermissionRepository(codes=_PERMISSION_CODES),
        audit=FakeAuditLogWriter(),
    )

    result = use_case.execute(
        CreateRoleCommand(
            actor=_actor(frozenset({"roles.manage"})),
            name="AUDITOR",
            scope=RoleScope.LAB,
            description="",
            permission_codes=frozenset({"clinics.read"}),
        )
    )

    assert result.permissions == frozenset({"clinics.read"})


def test_create_role_without_permission_is_forbidden() -> None:
    use_case = CreateRoleUseCase(
        roles=FakeRoleRepository(),
        permissions=FakePermissionRepository(codes=_PERMISSION_CODES),
        audit=FakeAuditLogWriter(),
    )

    with pytest.raises(ForbiddenError):
        use_case.execute(
            CreateRoleCommand(
                actor=_actor(frozenset()),
                name="AUDITOR",
                scope=RoleScope.LAB,
                description="",
                permission_codes=frozenset(),
            )
        )


def test_create_role_rejects_master_only_permission_for_a_lab_scope_role() -> None:
    use_case = CreateRoleUseCase(
        roles=FakeRoleRepository(),
        permissions=FakePermissionRepository(codes=_PERMISSION_CODES),
        audit=FakeAuditLogWriter(),
    )

    with pytest.raises(ValidationError):
        use_case.execute(
            CreateRoleCommand(
                actor=_actor(frozenset({"roles.manage"})),
                name="AUDITOR",
                scope=RoleScope.LAB,
                description="",
                permission_codes=frozenset({"clinics.read", "attendances.view_prices"}),
            )
        )


def test_create_role_allows_master_only_permission_for_a_global_scope_role() -> None:
    use_case = CreateRoleUseCase(
        roles=FakeRoleRepository(),
        permissions=FakePermissionRepository(codes=_PERMISSION_CODES),
        audit=FakeAuditLogWriter(),
    )

    result = use_case.execute(
        CreateRoleCommand(
            actor=_actor(frozenset({"roles.manage"})),
            name="SECOND_MASTER",
            scope=RoleScope.GLOBAL,
            description="",
            permission_codes=frozenset({"clinics.read", "attendances.view_prices"}),
        )
    )

    assert result.permissions == frozenset({"clinics.read", "attendances.view_prices"})
