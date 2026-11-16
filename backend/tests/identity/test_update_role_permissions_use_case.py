from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

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


def _command(
    role_id: UUID, actor: AuthenticatedUserDTO, **overrides: object
) -> UpdateRolePermissionsCommand:
    fields: dict[str, object] = {
        "actor": actor,
        "role_id": role_id,
        "permission_codes": frozenset({"clinics.read"}),
        "expected_row_version": 1,
    }
    fields.update(overrides)
    return UpdateRolePermissionsCommand(**fields)  # type: ignore[arg-type]


def test_update_role_permissions_validates_input_then_applies_versioned_and_audited_change() -> (
    None
):
    roles, permissions, users, role = _setup()
    global_role = Role(
        id=uuid4(),
        name="SUPER_ADMIN",
        scope=RoleScope.GLOBAL,
        permission_codes=frozenset({"clinics.read"}),
        row_version=1,
    )
    roles.add(global_role)
    audit = FakeAuditLogWriter()
    use_case = UpdateRolePermissionsUseCase(
        roles=roles, permissions=permissions, users=users, audit=audit
    )
    manager = _actor(frozenset({"roles.manage"}))
    master_only = frozenset({"clinics.read", "attendances.view_prices"})

    with pytest.raises(ForbiddenError):
        use_case.execute(_command(role.id, _actor(frozenset())))
    with pytest.raises(NotFoundError):
        use_case.execute(_command(uuid4(), manager))
    with pytest.raises(ValidationError):  # permissão que não existe
        use_case.execute(_command(role.id, manager, permission_codes=frozenset({"does.not_exist"})))
    with pytest.raises(ConflictError):  # versão velha
        use_case.execute(_command(role.id, manager, expected_row_version=99))
    with pytest.raises(ValidationError):  # permissão exclusiva do Master num papel LAB
        use_case.execute(_command(role.id, manager, permission_codes=master_only))
    # Nenhuma tentativa inválida altera o papel nem gera auditoria.
    assert roles.get_by_id(role.id).permission_codes == frozenset({"clinics.read"})  # type: ignore[union-attr]
    assert not audit.entries

    result = use_case.execute(
        _command(role.id, manager, permission_codes=frozenset({"clinics.read", "clinics.manage"}))
    )
    assert result.permissions == frozenset({"clinics.read", "clinics.manage"})
    assert result.row_version == 2
    assert audit.entries[0].action == "roles.permissions_updated"

    # A mesma permissão exclusiva do Master é aceita num papel de escopo GLOBAL.
    assert (
        use_case.execute(
            _command(global_role.id, manager, permission_codes=master_only)
        ).permissions
        == master_only
    )


def test_update_role_permissions_never_removes_the_last_roles_manage() -> None:
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

    # Único admin: tirar `roles.manage` do próprio papel travaria o sistema (ADR-007).
    with pytest.raises(SelfLockoutError):
        use_case.execute(_command(admin_role.id, actor))
    assert roles.get_by_id(admin_role.id).permission_codes == frozenset(  # type: ignore[union-attr]
        {"roles.manage", "clinics.read"}
    )

    # Com outro papel ativo que ainda cobre `roles.manage`, a remoção é permitida.
    second_admin_role = Role(
        id=uuid4(),
        name="SECOND_ADMIN",
        scope=RoleScope.GLOBAL,
        permission_codes=frozenset({"roles.manage"}),
        row_version=1,
    )
    roles.add(second_admin_role)
    users.add(
        User(
            id=uuid4(),
            email=Email("second-admin@vertere.local"),
            full_name="Second Admin",
            password_hash="hash",
            role_id=second_admin_role.id,
            created_at=_NOW,
            updated_at=_NOW,
        )
    )
    assert use_case.execute(_command(admin_role.id, actor)).permissions == frozenset(
        {"clinics.read"}
    )
