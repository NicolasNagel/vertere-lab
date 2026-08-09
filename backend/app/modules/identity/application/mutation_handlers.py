"""Atomic handlers for identity mutations."""

from __future__ import annotations

from datetime import timedelta

from app.modules.identity.application.activate_user import ActivateUserCommand, ActivateUserUseCase
from app.modules.identity.application.assign_role import AssignRoleCommand, AssignRoleUseCase
from app.modules.identity.application.create_role import CreateRoleCommand, CreateRoleUseCase
from app.modules.identity.application.create_user import CreateUserCommand, CreateUserUseCase
from app.modules.identity.application.deactivate_user import (
    DeactivateUserCommand,
    DeactivateUserUseCase,
)
from app.modules.identity.application.dtos import (
    RoleDTO,
    SessionIssuedDTO,
    UserCreatedDTO,
    UserSummaryDTO,
)
from app.modules.identity.application.login import LoginCommand, LoginUseCase
from app.modules.identity.application.logout import LogoutCommand, LogoutUseCase
from app.modules.identity.application.password_hasher import PasswordHasher
from app.modules.identity.application.session_tokens import SessionTokenGenerator
from app.modules.identity.application.uow import IdentityUnitOfWork
from app.modules.identity.application.update_role_permissions import (
    UpdateRolePermissionsCommand,
    UpdateRolePermissionsUseCase,
)
from app.modules.identity.application.update_user_access import (
    UpdateUserAccessCommand,
    UpdateUserAccessUseCase,
)
from app.modules.identity.domain.errors import AccountInactiveError, InvalidCredentialsError
from app.shared.application.clock import Clock
from app.shared.domain.errors import RateLimitedError


def handle_login(
    *,
    uow: IdentityUnitOfWork,
    command: LoginCommand,
    password_hasher: PasswordHasher,
    token_generator: SessionTokenGenerator,
    clock: Clock,
    session_ttl: timedelta,
    session_ttl_remember_me: timedelta,
    rate_limit_max_attempts: int,
    rate_limit_window: timedelta,
) -> SessionIssuedDTO:
    with uow:
        use_case = LoginUseCase(
            users=uow.users,
            roles=uow.roles,
            sessions=uow.sessions,
            memberships=uow.lab_memberships,
            clinic_memberships=uow.clinic_memberships,
            login_failures=uow.login_failures,
            password_hasher=password_hasher,
            token_generator=token_generator,
            audit=uow.audit,
            clock=clock,
            session_ttl=session_ttl,
            session_ttl_remember_me=session_ttl_remember_me,
            rate_limit_max_attempts=rate_limit_max_attempts,
            rate_limit_window=rate_limit_window,
        )
        try:
            result = use_case.execute(command)
        except (InvalidCredentialsError, AccountInactiveError, RateLimitedError):
            uow.commit()
            raise
        uow.commit()
        return result


def handle_logout(
    *,
    uow: IdentityUnitOfWork,
    command: LogoutCommand,
    token_generator: SessionTokenGenerator,
    clock: Clock,
) -> None:
    with uow:
        LogoutUseCase(sessions=uow.sessions, token_generator=token_generator, clock=clock).execute(
            command
        )
        uow.commit()


def handle_create_user(
    *,
    uow: IdentityUnitOfWork,
    command: CreateUserCommand,
    password_hasher: PasswordHasher,
    clock: Clock,
) -> UserCreatedDTO:
    with uow:
        result = CreateUserUseCase(
            users=uow.users,
            roles=uow.roles,
            memberships=uow.lab_memberships,
            clinic_memberships=uow.clinic_memberships,
            password_hasher=password_hasher,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result


def handle_update_user_access(
    *,
    uow: IdentityUnitOfWork,
    command: UpdateUserAccessCommand,
    clock: Clock,
) -> UserSummaryDTO:
    with uow:
        result = UpdateUserAccessUseCase(
            users=uow.users,
            roles=uow.roles,
            lab_memberships=uow.lab_memberships,
            clinic_memberships=uow.clinic_memberships,
            sessions=uow.sessions,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result


def handle_assign_role(
    *,
    uow: IdentityUnitOfWork,
    command: AssignRoleCommand,
    clock: Clock,
) -> UserSummaryDTO:
    with uow:
        result = AssignRoleUseCase(
            users=uow.users, roles=uow.roles, sessions=uow.sessions, audit=uow.audit, clock=clock
        ).execute(command)
        uow.commit()
        return result


def handle_deactivate_user(
    *,
    uow: IdentityUnitOfWork,
    command: DeactivateUserCommand,
    clock: Clock,
) -> UserSummaryDTO:
    with uow:
        result = DeactivateUserUseCase(
            users=uow.users, roles=uow.roles, sessions=uow.sessions, audit=uow.audit, clock=clock
        ).execute(command)
        uow.commit()
        return result


def handle_activate_user(
    *,
    uow: IdentityUnitOfWork,
    command: ActivateUserCommand,
    clock: Clock,
) -> UserSummaryDTO:
    with uow:
        result = ActivateUserUseCase(
            users=uow.users, roles=uow.roles, audit=uow.audit, clock=clock
        ).execute(command)
        uow.commit()
        return result


def handle_create_role(*, uow: IdentityUnitOfWork, command: CreateRoleCommand) -> RoleDTO:
    with uow:
        result = CreateRoleUseCase(
            roles=uow.roles, permissions=uow.permissions, audit=uow.audit
        ).execute(command)
        uow.commit()
        return result


def handle_update_role_permissions(
    *,
    uow: IdentityUnitOfWork,
    command: UpdateRolePermissionsCommand,
) -> RoleDTO:
    with uow:
        result = UpdateRolePermissionsUseCase(
            roles=uow.roles, permissions=uow.permissions, users=uow.users, audit=uow.audit
        ).execute(command)
        uow.commit()
        return result
