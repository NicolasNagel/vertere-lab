"""Identity API — thin routers, no business rule (rule: .claude/rules/02-backend.md).

Every mutating endpoint owns its transaction via the shared unit of work;
read-only endpoints reuse the request-scoped session from
`app.api.dependencies.get_session`.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session as SqlAlchemySession

from app.api.dependencies import get_session, get_unit_of_work
from app.core.config import Settings
from app.core.logging import request_id_var
from app.modules.audit.infrastructure.repositories import SqlAlchemyAuditLogWriter
from app.modules.identity.api.dependencies import (
    get_current_user,
    get_session_token,
    require_permission,
)
from app.modules.identity.api.schemas import (
    AssignRoleRequest,
    AuthResponse,
    LoginRequest,
    PermissionRead,
    RoleCreateRequest,
    RoleListResponse,
    RoleRead,
    RoleUpdateRequest,
    UserCreateRequest,
    UserCreateResponse,
    UserListItemRead,
    UserListResponse,
    UserPublicRead,
)
from app.modules.identity.application.activate_user import (
    ActivateUserCommand,
    ActivateUserUseCase,
)
from app.modules.identity.application.assign_role import AssignRoleCommand, AssignRoleUseCase
from app.modules.identity.application.create_role import CreateRoleCommand, CreateRoleUseCase
from app.modules.identity.application.create_user import CreateUserCommand, CreateUserUseCase
from app.modules.identity.application.deactivate_user import (
    DeactivateUserCommand,
    DeactivateUserUseCase,
)
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.identity.application.list_permissions import (
    ListPermissionsQuery,
    ListPermissionsUseCase,
)
from app.modules.identity.application.list_roles import (
    GetRoleQuery,
    GetRoleUseCase,
    ListRolesQuery,
    ListRolesUseCase,
)
from app.modules.identity.application.list_users import ListUsersQuery, ListUsersUseCase
from app.modules.identity.application.login import LoginCommand, LoginUseCase
from app.modules.identity.application.logout import LogoutCommand, LogoutUseCase
from app.modules.identity.application.update_role_permissions import (
    UpdateRolePermissionsCommand,
    UpdateRolePermissionsUseCase,
)
from app.modules.identity.domain.entities import RoleScope
from app.modules.identity.domain.errors import AccountInactiveError, InvalidCredentialsError
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.repositories import (
    SqlAlchemyLabMembershipRepository,
    SqlAlchemyLoginFailureRepository,
    SqlAlchemyPermissionRepository,
    SqlAlchemyRoleRepository,
    SqlAlchemySessionRepository,
    SqlAlchemyUserRepository,
)
from app.modules.identity.infrastructure.session_tokens import OpaqueSessionTokens
from app.shared.domain.errors import RateLimitedError
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork

router = APIRouter(tags=["identity"])


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _user_public_read(user: AuthenticatedUserDTO) -> UserPublicRead:
    return UserPublicRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role_id=user.role_id,
        role_name=user.role_name,
    )


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------


@router.post("/auth/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
) -> AuthResponse:
    settings = _settings(request)
    with uow:
        use_case = LoginUseCase(
            users=SqlAlchemyUserRepository(uow.session),
            roles=SqlAlchemyRoleRepository(uow.session),
            sessions=SqlAlchemySessionRepository(uow.session),
            memberships=SqlAlchemyLabMembershipRepository(uow.session),
            login_failures=SqlAlchemyLoginFailureRepository(uow.session),
            password_hasher=Argon2PasswordHasher(),
            token_generator=OpaqueSessionTokens(),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
            session_ttl=timedelta(minutes=settings.session_ttl_minutes),
            session_ttl_remember_me=timedelta(days=settings.session_ttl_remember_me_days),
            rate_limit_max_attempts=settings.login_rate_limit_max_attempts,
            rate_limit_window=timedelta(minutes=settings.login_rate_limit_window_minutes),
        )
        command = LoginCommand(
            login=payload.login,
            password=payload.password,
            remember_me=payload.remember_me,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            request_id=request_id_var.get(),
        )
        try:
            result = use_case.execute(command)
        except (InvalidCredentialsError, AccountInactiveError, RateLimitedError):
            # Rejeição esperada (senha errada, conta inativa, rate limit) não
            # é motivo para descartar o que o caso de uso já gravou nesta
            # mesma transação — o registro de falha (para o rate limit) e o
            # audit_log da tentativa precisam sobreviver, senão o rollback
            # padrão do unit of work em qualquer exceção apaga os dois e o
            # limite nunca é alcançado (achado ao testar o rate limit de
            # verdade: a 6ª tentativa passava porque nenhuma falha anterior
            # tinha sido persistida).
            uow.commit()
            raise
        uow.commit()

    ttl = (
        timedelta(days=settings.session_ttl_remember_me_days)
        if payload.remember_me
        else timedelta(minutes=settings.session_ttl_minutes)
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=result.token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=int(ttl.total_seconds()),
    )
    return AuthResponse(
        user=_user_public_read(result.user),
        permissions=sorted(result.user.permissions),
    )


@router.post("/auth/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    token: str | None = Depends(get_session_token),
) -> Response:
    if token is not None:
        with uow:
            use_case = LogoutUseCase(
                sessions=SqlAlchemySessionRepository(uow.session),
                token_generator=OpaqueSessionTokens(),
                clock=SystemClock(),
            )
            use_case.execute(LogoutCommand(token=token))
            uow.commit()

    settings = _settings(request)
    response.delete_cookie(settings.session_cookie_name)
    return Response(status_code=204)


@router.get("/auth/me", response_model=AuthResponse)
def get_me(current_user: AuthenticatedUserDTO = Depends(get_current_user)) -> AuthResponse:
    return AuthResponse(
        user=_user_public_read(current_user), permissions=sorted(current_user.permissions)
    )


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------


@router.get("/users", response_model=UserListResponse)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: bool | None = Query(None),
    search: str | None = Query(None),
    session: SqlAlchemySession = Depends(get_session),
    current_user: AuthenticatedUserDTO = Depends(require_permission("users.read")),
) -> UserListResponse:
    use_case = ListUsersUseCase(
        users=SqlAlchemyUserRepository(session), roles=SqlAlchemyRoleRepository(session)
    )
    result = use_case.execute(
        ListUsersQuery(
            actor=current_user,
            page=page,
            page_size=page_size,
            is_active=is_active,
            search=search,
        )
    )
    return UserListResponse(
        items=[
            UserListItemRead(
                id=item.id,
                email=item.email,
                full_name=item.full_name,
                is_active=item.is_active,
                role_id=item.role_id,
                role_name=item.role_name,
                created_at=item.created_at,
            )
            for item in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.post("/users", response_model=UserCreateResponse, status_code=201)
def create_user(
    payload: UserCreateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("users.create")),
) -> UserCreateResponse:
    with uow:
        use_case = CreateUserUseCase(
            users=SqlAlchemyUserRepository(uow.session),
            roles=SqlAlchemyRoleRepository(uow.session),
            memberships=SqlAlchemyLabMembershipRepository(uow.session),
            password_hasher=Argon2PasswordHasher(),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            CreateUserCommand(
                actor=current_user,
                email=payload.email,
                full_name=payload.full_name,
                role_id=payload.role_id,
            )
        )
        uow.commit()

    return UserCreateResponse(
        user=UserListItemRead(
            id=result.user.id,
            email=result.user.email,
            full_name=result.user.full_name,
            is_active=result.user.is_active,
            role_id=result.user.role_id,
            role_name=result.user.role_name,
            created_at=result.user.created_at,
        ),
        temporary_password=result.temporary_password,
    )


@router.patch("/users/{user_id}/role", response_model=UserListItemRead)
def assign_role(
    user_id: UUID,
    payload: AssignRoleRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("roles.assign")),
) -> UserListItemRead:
    with uow:
        use_case = AssignRoleUseCase(
            users=SqlAlchemyUserRepository(uow.session),
            roles=SqlAlchemyRoleRepository(uow.session),
            sessions=SqlAlchemySessionRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            AssignRoleCommand(actor=current_user, user_id=user_id, new_role_id=payload.role_id)
        )
        uow.commit()

    return UserListItemRead(
        id=result.id,
        email=result.email,
        full_name=result.full_name,
        is_active=result.is_active,
        role_id=result.role_id,
        role_name=result.role_name,
        created_at=result.created_at,
    )


@router.patch("/users/{user_id}/deactivate", response_model=UserListItemRead)
def deactivate_user(
    user_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("users.deactivate")),
) -> UserListItemRead:
    with uow:
        use_case = DeactivateUserUseCase(
            users=SqlAlchemyUserRepository(uow.session),
            roles=SqlAlchemyRoleRepository(uow.session),
            sessions=SqlAlchemySessionRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(DeactivateUserCommand(actor=current_user, user_id=user_id))
        uow.commit()

    return UserListItemRead(
        id=result.id,
        email=result.email,
        full_name=result.full_name,
        is_active=result.is_active,
        role_id=result.role_id,
        role_name=result.role_name,
        created_at=result.created_at,
    )


@router.patch("/users/{user_id}/activate", response_model=UserListItemRead)
def activate_user(
    user_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("users.activate")),
) -> UserListItemRead:
    with uow:
        use_case = ActivateUserUseCase(
            users=SqlAlchemyUserRepository(uow.session),
            roles=SqlAlchemyRoleRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(ActivateUserCommand(actor=current_user, user_id=user_id))
        uow.commit()

    return UserListItemRead(
        id=result.id,
        email=result.email,
        full_name=result.full_name,
        is_active=result.is_active,
        role_id=result.role_id,
        role_name=result.role_name,
        created_at=result.created_at,
    )


# --------------------------------------------------------------------------
# Permission profiles (roles)
# --------------------------------------------------------------------------


@router.get("/permission-profiles", response_model=RoleListResponse)
def list_permission_profiles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: SqlAlchemySession = Depends(get_session),
    current_user: AuthenticatedUserDTO = Depends(require_permission("roles.read")),
) -> RoleListResponse:
    use_case = ListRolesUseCase(roles=SqlAlchemyRoleRepository(session))
    result = use_case.execute(ListRolesQuery(actor=current_user, page=page, page_size=page_size))
    return RoleListResponse(
        items=[
            RoleRead(
                id=role.id,
                name=role.name,
                scope=role.scope,
                description=role.description,
                is_system=role.is_system,
                permissions=sorted(role.permissions),
                row_version=role.row_version,
            )
            for role in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/permission-profiles/{role_id}", response_model=RoleRead)
def get_permission_profile(
    role_id: UUID,
    session: SqlAlchemySession = Depends(get_session),
    current_user: AuthenticatedUserDTO = Depends(require_permission("roles.read")),
) -> RoleRead:
    use_case = GetRoleUseCase(roles=SqlAlchemyRoleRepository(session))
    role = use_case.execute(GetRoleQuery(actor=current_user, role_id=role_id))
    return RoleRead(
        id=role.id,
        name=role.name,
        scope=role.scope,
        description=role.description,
        is_system=role.is_system,
        permissions=sorted(role.permissions),
        row_version=role.row_version,
    )


@router.post("/permission-profiles", response_model=RoleRead, status_code=201)
def create_permission_profile(
    payload: RoleCreateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("roles.manage")),
) -> RoleRead:
    with uow:
        use_case = CreateRoleUseCase(
            roles=SqlAlchemyRoleRepository(uow.session),
            permissions=SqlAlchemyPermissionRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
        )
        role = use_case.execute(
            CreateRoleCommand(
                actor=current_user,
                name=payload.name,
                scope=RoleScope(payload.scope),
                description=payload.description,
                permission_codes=frozenset(payload.permissions),
            )
        )
        uow.commit()

    return RoleRead(
        id=role.id,
        name=role.name,
        scope=role.scope,
        description=role.description,
        is_system=role.is_system,
        permissions=sorted(role.permissions),
        row_version=role.row_version,
    )


@router.patch("/permission-profiles/{role_id}", response_model=RoleRead)
def update_permission_profile(
    role_id: UUID,
    payload: RoleUpdateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("roles.manage")),
) -> RoleRead:
    with uow:
        use_case = UpdateRolePermissionsUseCase(
            roles=SqlAlchemyRoleRepository(uow.session),
            permissions=SqlAlchemyPermissionRepository(uow.session),
            users=SqlAlchemyUserRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
        )
        role = use_case.execute(
            UpdateRolePermissionsCommand(
                actor=current_user,
                role_id=role_id,
                permission_codes=frozenset(payload.permissions),
                expected_row_version=payload.expected_row_version,
            )
        )
        uow.commit()

    return RoleRead(
        id=role.id,
        name=role.name,
        scope=role.scope,
        description=role.description,
        is_system=role.is_system,
        permissions=sorted(role.permissions),
        row_version=role.row_version,
    )


# --------------------------------------------------------------------------
# Permissions catalog
# --------------------------------------------------------------------------


@router.get("/permissions", response_model=list[PermissionRead])
def list_permissions(
    session: SqlAlchemySession = Depends(get_session),
    current_user: AuthenticatedUserDTO = Depends(require_permission("permissions.read")),
) -> list[PermissionRead]:
    use_case = ListPermissionsUseCase(permissions=SqlAlchemyPermissionRepository(session))
    result = use_case.execute(ListPermissionsQuery(actor=current_user))
    return [
        PermissionRead(id=p.id, code=p.code, description=p.description, master_only=p.master_only)
        for p in result
    ]
