"""SQLAlchemy implementations of the identity repository protocols.

Domain entities are the only thing that crosses back out of this module;
ORM models never leak past this file (rule: .claude/rules/database.md).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session as SqlAlchemySession

from app.modules.identity.domain.entities import (
    LabMembership,
    Permission,
    Role,
    RoleScope,
    Session,
    User,
)
from app.modules.identity.domain.value_objects import Email
from app.modules.identity.infrastructure.models import (
    LabMembershipModel,
    PermissionModel,
    RoleModel,
    RolePermissionModel,
    SessionModel,
    UserModel,
)


def _user_to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        email=Email(model.email),
        full_name=model.full_name,
        password_hash=model.password_hash,
        is_active=model.is_active,
        role_id=model.role_id,
        created_by=model.created_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
        row_version=model.row_version,
    )


def _session_to_domain(model: SessionModel) -> Session:
    return Session(
        id=model.id,
        user_id=model.user_id,
        token_hash=model.token_hash,
        created_at=model.created_at,
        last_seen_at=model.last_seen_at,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
        remember_me=model.remember_me,
        ip_address=model.ip_address,
        user_agent=model.user_agent,
    )


class SqlAlchemyUserRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def get_by_id(self, user_id: UUID) -> User | None:
        model = self._session.get(UserModel, user_id)
        return _user_to_domain(model) if model is not None else None

    def get_by_email(self, email: str) -> User | None:
        model = self._session.execute(
            select(UserModel).where(UserModel.email == email)
        ).scalar_one_or_none()
        return _user_to_domain(model) if model is not None else None

    def add(self, user: User) -> None:
        self._session.add(
            UserModel(
                id=user.id,
                email=str(user.email),
                full_name=user.full_name,
                password_hash=user.password_hash,
                is_active=user.is_active,
                role_id=user.role_id,
                created_by=user.created_by,
                created_at=user.created_at,
                updated_at=user.updated_at,
                row_version=user.row_version,
            )
        )
        # Flush já: sem `relationship()` entre User e LabMembership/Session, o
        # unit of work do SQLAlchemy não infere a ordem de FK entre eles — o
        # flush garante que o usuário já existe antes de quem referencia seu id
        # na mesma transação (rule: .claude/rules/database.md).
        self._session.flush()

    def save(self, user: User) -> None:
        model = self._session.get(UserModel, user.id)
        if model is None:
            raise LookupError(f"Usuário {user.id} não encontrado para atualização.")
        model.full_name = user.full_name
        model.password_hash = user.password_hash
        model.is_active = user.is_active
        model.role_id = user.role_id
        model.updated_at = user.updated_at
        model.row_version = user.row_version + 1

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        is_active: bool | None,
        search: str | None,
    ) -> tuple[list[User], int]:
        conditions: list[ColumnElement[bool]] = []
        if is_active is not None:
            conditions.append(UserModel.is_active.is_(is_active))
        if search:
            like_pattern = f"%{search.lower()}%"
            conditions.append(
                or_(
                    func.lower(UserModel.full_name).like(like_pattern),
                    func.lower(UserModel.email).like(like_pattern),
                )
            )

        count_stmt = select(func.count()).select_from(UserModel)
        list_stmt = select(UserModel).order_by(UserModel.created_at.desc())
        for condition in conditions:
            count_stmt = count_stmt.where(condition)
            list_stmt = list_stmt.where(condition)

        total = self._session.execute(count_stmt).scalar_one()
        list_stmt = list_stmt.offset((page - 1) * page_size).limit(page_size)
        models = self._session.execute(list_stmt).scalars().all()
        return [_user_to_domain(model) for model in models], total

    def count_active_users_with_permission(
        self, permission_code: str, *, exclude_user_id: UUID | None = None
    ) -> int:
        stmt = (
            select(func.count(func.distinct(UserModel.id)))
            .select_from(UserModel)
            .join(RoleModel, RoleModel.id == UserModel.role_id)
            .join(RolePermissionModel, RolePermissionModel.role_id == RoleModel.id)
            .join(PermissionModel, PermissionModel.id == RolePermissionModel.permission_id)
            .where(UserModel.is_active.is_(True))
            .where(PermissionModel.code == permission_code)
        )
        if exclude_user_id is not None:
            stmt = stmt.where(UserModel.id != exclude_user_id)
        return self._session.execute(stmt).scalar_one()


class SqlAlchemyRoleRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def _permission_codes_for(self, role_id: UUID) -> frozenset[str]:
        stmt = (
            select(PermissionModel.code)
            .join(RolePermissionModel, RolePermissionModel.permission_id == PermissionModel.id)
            .where(RolePermissionModel.role_id == role_id)
        )
        return frozenset(self._session.execute(stmt).scalars().all())

    def _to_domain(self, model: RoleModel) -> Role:
        return Role(
            id=model.id,
            name=model.name,
            scope=RoleScope(model.scope),
            description=model.description,
            is_system=model.is_system,
            permission_codes=self._permission_codes_for(model.id),
            row_version=model.row_version,
        )

    def get_by_id(self, role_id: UUID) -> Role | None:
        model = self._session.get(RoleModel, role_id)
        return self._to_domain(model) if model is not None else None

    def get_by_name(self, name: str) -> Role | None:
        model = self._session.execute(
            select(RoleModel).where(RoleModel.name == name)
        ).scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    def add(self, role: Role) -> None:
        model = RoleModel(
            id=role.id,
            name=role.name,
            scope=role.scope.value,
            description=role.description,
            is_system=role.is_system,
            row_version=role.row_version,
        )
        self._session.add(model)
        self._session.flush()
        self._link_permissions(role.id, role.permission_codes)

    def _link_permissions(self, role_id: UUID, permission_codes: frozenset[str]) -> None:
        if not permission_codes:
            return
        permission_ids = (
            self._session.execute(
                select(PermissionModel.id).where(PermissionModel.code.in_(permission_codes))
            )
            .scalars()
            .all()
        )
        now = func.now()
        for permission_id in permission_ids:
            self._session.add(
                RolePermissionModel(role_id=role_id, permission_id=permission_id, granted_at=now)
            )

    def replace_permissions(self, role_id: UUID, permission_codes: frozenset[str]) -> None:
        existing = (
            self._session.execute(
                select(RolePermissionModel).where(RolePermissionModel.role_id == role_id)
            )
            .scalars()
            .all()
        )
        for link in existing:
            self._session.delete(link)
        self._session.flush()
        self._link_permissions(role_id, permission_codes)

        model = self._session.get(RoleModel, role_id)
        if model is not None:
            model.row_version += 1

    def list_page(self, *, page: int, page_size: int) -> tuple[list[Role], int]:
        total = self._session.execute(select(func.count()).select_from(RoleModel)).scalar_one()
        stmt = (
            select(RoleModel)
            .order_by(RoleModel.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        models = self._session.execute(stmt).scalars().all()
        return [self._to_domain(model) for model in models], total


class SqlAlchemyPermissionRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def list_all(self) -> list[Permission]:
        models = (
            self._session.execute(select(PermissionModel).order_by(PermissionModel.code))
            .scalars()
            .all()
        )
        return [
            Permission(id=model.id, code=model.code, description=model.description)
            for model in models
        ]

    def all_codes_exist(self, codes: frozenset[str]) -> bool:
        if not codes:
            return True
        found = self._session.execute(
            select(func.count()).select_from(PermissionModel).where(PermissionModel.code.in_(codes))
        ).scalar_one()
        return found == len(codes)


class SqlAlchemySessionRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def add(self, session_entity: Session) -> None:
        self._session.add(
            SessionModel(
                id=session_entity.id,
                user_id=session_entity.user_id,
                token_hash=session_entity.token_hash,
                created_at=session_entity.created_at,
                last_seen_at=session_entity.last_seen_at,
                expires_at=session_entity.expires_at,
                revoked_at=session_entity.revoked_at,
                remember_me=session_entity.remember_me,
                ip_address=session_entity.ip_address,
                user_agent=session_entity.user_agent,
            )
        )

    def get_by_token_hash(self, token_hash: str) -> Session | None:
        model = self._session.execute(
            select(SessionModel).where(SessionModel.token_hash == token_hash)
        ).scalar_one_or_none()
        return _session_to_domain(model) if model is not None else None

    def save(self, session_entity: Session) -> None:
        model = self._session.get(SessionModel, session_entity.id)
        if model is None:
            raise LookupError(f"Sessão {session_entity.id} não encontrada para atualização.")
        model.last_seen_at = session_entity.last_seen_at
        model.expires_at = session_entity.expires_at
        model.revoked_at = session_entity.revoked_at

    def revoke_all_for_user(self, user_id: UUID, *, now: datetime) -> None:
        models = (
            self._session.execute(
                select(SessionModel).where(
                    SessionModel.user_id == user_id, SessionModel.revoked_at.is_(None)
                )
            )
            .scalars()
            .all()
        )
        for model in models:
            model.revoked_at = now


class SqlAlchemyLabMembershipRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def add(self, membership: LabMembership) -> None:
        self._session.add(
            LabMembershipModel(
                id=membership.id,
                user_id=membership.user_id,
                is_active=membership.is_active,
                granted_at=membership.granted_at,
                granted_by=membership.granted_by,
                revoked_at=membership.revoked_at,
            )
        )
