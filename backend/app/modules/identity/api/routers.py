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
    UpdateUserAccessRequest,
    UserCreateRequest,
    UserCreateResponse,
    UserListItemRead,
    UserListResponse,
    UserPublicRead,
)
from app.modules.identity.application.activate_user import (
    ActivateUserCommand,
)
from app.modules.identity.application.assign_role import AssignRoleCommand
from app.modules.identity.application.create_role import CreateRoleCommand
from app.modules.identity.application.create_user import CreateUserCommand
from app.modules.identity.application.deactivate_user import (
    DeactivateUserCommand,
)
from app.modules.identity.application.dtos import UserSummaryDTO
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
from app.modules.identity.application.login import LoginCommand
from app.modules.identity.application.logout import LogoutCommand
from app.modules.identity.application.mutation_handlers import (
    handle_activate_user,
    handle_assign_role,
    handle_create_role,
    handle_create_user,
    handle_deactivate_user,
    handle_login,
    handle_logout,
    handle_update_role_permissions,
    handle_update_user_access,
)
from app.modules.identity.application.update_role_permissions import (
    UpdateRolePermissionsCommand,
)
from app.modules.identity.application.update_user_access import (
    UpdateUserAccessCommand,
)
from app.modules.identity.domain.entities import RoleScope
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.repositories import (
    SqlAlchemyClinicMembershipRepository,
    SqlAlchemyPermissionRepository,
    SqlAlchemyRoleRepository,
    SqlAlchemyUserRepository,
)
from app.modules.identity.infrastructure.session_tokens import OpaqueSessionTokens
from app.modules.identity.infrastructure.uow import SqlAlchemyIdentityUnitOfWork
from app.shared.application.authorization import ActorContext
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork

router = APIRouter(tags=["identity"])


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _user_public_read(user: ActorContext) -> UserPublicRead:
    return UserPublicRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role_id=user.role_id,
        role_name=user.role_name,
        role_scope=user.role_scope,
        clinic_ids=sorted(user.clinic_ids),
        row_version=user.row_version,
    )


def _user_list_item_read(user: UserSummaryDTO) -> UserListItemRead:
    return UserListItemRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        role_id=user.role_id,
        role_name=user.role_name,
        role_scope=user.role_scope,
        clinic_ids=sorted(user.clinic_ids),
        row_version=user.row_version,
        created_at=user.created_at,
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
    result = handle_login(
        uow=SqlAlchemyIdentityUnitOfWork(uow),
        command=LoginCommand(
            login=payload.login,
            password=payload.password,
            remember_me=payload.remember_me,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            request_id=request_id_var.get(),
        ),
        password_hasher=Argon2PasswordHasher(),
        token_generator=OpaqueSessionTokens(),
        clock=SystemClock(),
        session_ttl=timedelta(minutes=settings.session_ttl_minutes),
        session_ttl_remember_me=timedelta(days=settings.session_ttl_remember_me_days),
        rate_limit_max_attempts=settings.login_rate_limit_max_attempts,
        rate_limit_window=timedelta(minutes=settings.login_rate_limit_window_minutes),
    )
    # Rejeição esperada (senha errada, conta inativa, rate limit) não
    # é motivo para descartar o que o caso de uso já gravou nesta
    # mesma transação — o registro de falha (para o rate limit) e o
    # audit_log da tentativa precisam sobreviver, senão o rollback
    # padrão do unit of work em qualquer exceção apaga os dois e o
    # limite nunca é alcançado (achado ao testar o rate limit de
    # verdade: a 6ª tentativa passava porque nenhuma falha anterior
    # tinha sido persistida).

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
        handle_logout(
            uow=SqlAlchemyIdentityUnitOfWork(uow),
            command=LogoutCommand(token=token),
            token_generator=OpaqueSessionTokens(),
            clock=SystemClock(),
        )

    settings = _settings(request)
    response.delete_cookie(settings.session_cookie_name)
    return Response(status_code=204)


@router.get("/auth/me", response_model=AuthResponse)
def get_me(current_user: ActorContext = Depends(get_current_user)) -> AuthResponse:
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
    current_user: ActorContext = Depends(require_permission("users.read")),
) -> UserListResponse:
    use_case = ListUsersUseCase(
        users=SqlAlchemyUserRepository(session),
        roles=SqlAlchemyRoleRepository(session),
        clinic_memberships=SqlAlchemyClinicMembershipRepository(session),
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
        items=[_user_list_item_read(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.post("/users", response_model=UserCreateResponse, status_code=201)
def create_user(
    payload: UserCreateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("users.create")),
) -> UserCreateResponse:
    result = handle_create_user(
        uow=SqlAlchemyIdentityUnitOfWork(uow),
        command=CreateUserCommand(
            actor=current_user,
            email=payload.email,
            full_name=payload.full_name,
            role_id=payload.role_id,
            clinic_ids=frozenset(payload.clinic_ids),
        ),
        password_hasher=Argon2PasswordHasher(),
        clock=SystemClock(),
    )

    return UserCreateResponse(
        user=_user_list_item_read(result.user), temporary_password=result.temporary_password
    )


@router.patch("/users/{user_id}/access", response_model=UserListItemRead)
def update_user_access(
    user_id: UUID,
    payload: UpdateUserAccessRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("roles.assign")),
) -> UserListItemRead:
    result = handle_update_user_access(
        uow=SqlAlchemyIdentityUnitOfWork(uow),
        command=UpdateUserAccessCommand(
            actor=current_user,
            user_id=user_id,
            role_id=payload.role_id,
            clinic_ids=frozenset(payload.clinic_ids),
            expected_row_version=payload.expected_row_version,
        ),
        clock=SystemClock(),
    )
    return _user_list_item_read(result)


@router.patch("/users/{user_id}/role", response_model=UserListItemRead, deprecated=True)
def assign_role(
    user_id: UUID,
    payload: AssignRoleRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("roles.assign")),
) -> UserListItemRead:
    result = handle_assign_role(
        uow=SqlAlchemyIdentityUnitOfWork(uow),
        command=AssignRoleCommand(actor=current_user, user_id=user_id, new_role_id=payload.role_id),
        clock=SystemClock(),
    )

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
    current_user: ActorContext = Depends(require_permission("users.deactivate")),
) -> UserListItemRead:
    result = handle_deactivate_user(
        uow=SqlAlchemyIdentityUnitOfWork(uow),
        command=DeactivateUserCommand(actor=current_user, user_id=user_id),
        clock=SystemClock(),
    )

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
    current_user: ActorContext = Depends(require_permission("users.activate")),
) -> UserListItemRead:
    result = handle_activate_user(
        uow=SqlAlchemyIdentityUnitOfWork(uow),
        command=ActivateUserCommand(actor=current_user, user_id=user_id),
        clock=SystemClock(),
    )

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
    current_user: ActorContext = Depends(require_permission("roles.read")),
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
    current_user: ActorContext = Depends(require_permission("roles.read")),
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
    current_user: ActorContext = Depends(require_permission("roles.manage")),
) -> RoleRead:
    role = handle_create_role(
        uow=SqlAlchemyIdentityUnitOfWork(uow),
        command=CreateRoleCommand(
            actor=current_user,
            name=payload.name,
            scope=RoleScope(payload.scope),
            description=payload.description,
            permission_codes=frozenset(payload.permissions),
        ),
    )

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
    current_user: ActorContext = Depends(require_permission("roles.manage")),
) -> RoleRead:
    role = handle_update_role_permissions(
        uow=SqlAlchemyIdentityUnitOfWork(uow),
        command=UpdateRolePermissionsCommand(
            actor=current_user,
            role_id=role_id,
            permission_codes=frozenset(payload.permissions),
            expected_row_version=payload.expected_row_version,
        ),
    )

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
    current_user: ActorContext = Depends(require_permission("permissions.read")),
) -> list[PermissionRead]:
    use_case = ListPermissionsUseCase(permissions=SqlAlchemyPermissionRepository(session))
    result = use_case.execute(ListPermissionsQuery(actor=current_user))
    return [
        PermissionRead(id=p.id, code=p.code, description=p.description, master_only=p.master_only)
        for p in result
    ]
