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


def test_create_role_enforces_permission_and_master_only_rules_by_scope() -> None:
    use_case = CreateRoleUseCase(
        roles=FakeRoleRepository(),
        permissions=FakePermissionRepository(codes=_PERMISSION_CODES),
        audit=FakeAuditLogWriter(),
    )
    manager = _actor(frozenset({"roles.manage"}))
    master_only = frozenset({"clinics.read", "attendances.view_prices"})

    def command(**overrides: object) -> CreateRoleCommand:
        fields: dict[str, object] = {
            "actor": manager,
            "name": "AUDITOR",
            "scope": RoleScope.LAB,
            "description": "",
            "permission_codes": frozenset({"clinics.read"}),
        }
        fields.update(overrides)
        return CreateRoleCommand(**fields)  # type: ignore[arg-type]

    with pytest.raises(ForbiddenError):
        use_case.execute(command(actor=_actor(frozenset())))
    with pytest.raises(ValidationError):  # permissão exclusiva do Master num papel LAB
        use_case.execute(command(permission_codes=master_only))

    assert use_case.execute(command()).permissions == frozenset({"clinics.read"})
    assert (
        use_case.execute(
            command(name="SECOND_MASTER", scope=RoleScope.GLOBAL, permission_codes=master_only)
        ).permissions
        == master_only
    )
