"""SQLAlchemy implementations of the identity repository protocols.

Domain entities are the only thing that crosses back out of this module;
ORM models never leak past this file (rule: .claude/rules/03-database.md).
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, CursorResult, delete, func, or_, select, update
from sqlalchemy.orm import Session as SqlAlchemySession

from app.modules.clinics.infrastructure.models import ClinicModel
from app.modules.identity.domain.entities import (
    ClinicMembership,
    LabMembership,
    Permission,
    Role,
    RoleScope,
    Session,
    User,
)
from app.modules.identity.domain.value_objects import Email
from app.modules.identity.infrastructure.models import (
    ClinicMembershipModel,
    LabMembershipModel,
    LoginFailureModel,
    PermissionModel,
    RoleModel,
    RolePermissionModel,
    SessionModel,
    UserModel,
)
from app.shared.infrastructure.sql import LIKE_ESCAPE, folded, folded_pattern


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


class SqlAlchemyUserNameLookup:
    """Read-only `id -> full_name` lookup (timeline author names); no domain entity needed."""

    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def names_by_id(self, user_ids: Collection[UUID]) -> dict[UUID, str]:
        if not user_ids:
            return {}
        rows = self._session.execute(
            select(UserModel.id, UserModel.full_name).where(UserModel.id.in_(user_ids))
        ).all()
        return {row.id: row.full_name for row in rows}


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
        # na mesma transação (rule: .claude/rules/03-database.md).
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
        user.row_version = model.row_version

    def change_role_if_version(
        self, user_id: UUID, role_id: UUID, *, expected_row_version: int, now: datetime
    ) -> bool:
        result: CursorResult[Any] = self._session.execute(  # type: ignore[assignment]
            update(UserModel)
            .where(UserModel.id == user_id, UserModel.row_version == expected_row_version)
            .values(role_id=role_id, updated_at=now, row_version=UserModel.row_version + 1)
        )
        return result.rowcount == 1

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        is_active: bool | None,
        search: str | None,
        clinic_ids: frozenset[UUID] | None = None,
    ) -> tuple[list[User], int]:
        conditions: list[ColumnElement[bool]] = []
        if clinic_ids is not None:
            # Only users that belong to the actor's clinics and to no other clinic.
            active_membership = select(ClinicMembershipModel.id).where(
                ClinicMembershipModel.user_id == UserModel.id,
                ClinicMembershipModel.is_active.is_(True),
                ClinicMembershipModel.revoked_at.is_(None),
            )
            conditions.append(
                active_membership.where(ClinicMembershipModel.clinic_id.in_(clinic_ids)).exists()
            )
            conditions.append(
                ~active_membership.where(
                    ClinicMembershipModel.clinic_id.notin_(clinic_ids)
                ).exists()
            )
        if is_active is not None:
            conditions.append(UserModel.is_active.is_(is_active))
        if search:
            like_pattern = folded_pattern(search)
            conditions.append(
                or_(
                    folded(UserModel.full_name).like(like_pattern, escape=LIKE_ESCAPE),
                    folded(UserModel.email).like(like_pattern, escape=LIKE_ESCAPE),
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
        self,
        permission_code: str,
        *,
        exclude_user_id: UUID | None = None,
        exclude_role_id: UUID | None = None,
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
        if exclude_role_id is not None:
            stmt = stmt.where(UserModel.role_id != exclude_role_id)
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

    def replace_permissions(
        self, role_id: UUID, permission_codes: frozenset[str], *, expected_row_version: int
    ) -> bool:
        # Conditional UPDATE (CAS) instead of read-then-write: the WHERE
        # clause re-checks `row_version` at the database level, inside this
        # transaction, so two concurrent callers that both read the same
        # stale version can no longer both succeed — only the first UPDATE
        # matches the WHERE and the second sees `rowcount == 0`.
        # `Session.execute` on an `Update` construct returns a `CursorResult`
        # at runtime (`.rowcount` is valid there); the stub's generic
        # `Result[Any]` return type just doesn't say so.
        result: CursorResult[Any] = self._session.execute(  # type: ignore[assignment]
            update(RoleModel)
            .where(RoleModel.id == role_id, RoleModel.row_version == expected_row_version)
            .values(row_version=RoleModel.row_version + 1)
        )
        if result.rowcount == 0:
            return False

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
        return True

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

    def get_active_by_user_id(self, user_id: UUID) -> LabMembership | None:
        model = self._session.execute(
            select(LabMembershipModel).where(
                LabMembershipModel.user_id == user_id,
                LabMembershipModel.is_active.is_(True),
                LabMembershipModel.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        if model is None:
            return None
        return LabMembership(
            id=model.id,
            user_id=model.user_id,
            is_active=model.is_active,
            granted_at=model.granted_at,
            granted_by=model.granted_by,
            revoked_at=model.revoked_at,
        )

    def set_active(self, user_id: UUID, *, active: bool, now: datetime, granted_by: UUID) -> None:
        model = self._session.execute(
            select(LabMembershipModel).where(LabMembershipModel.user_id == user_id)
        ).scalar_one_or_none()
        if model is None:
            if active:
                self.add(
                    LabMembership(
                        id=uuid4(), user_id=user_id, granted_at=now, granted_by=granted_by
                    )
                )
            return
        model.is_active = active
        model.revoked_at = None if active else now
        if active:
            model.granted_at = now
            model.granted_by = granted_by


class SqlAlchemyClinicMembershipRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def add(self, membership: ClinicMembership) -> None:
        self._session.add(
            ClinicMembershipModel(
                id=membership.id,
                user_id=membership.user_id,
                clinic_id=membership.clinic_id,
                is_active=membership.is_active,
                granted_at=membership.granted_at,
                granted_by=membership.granted_by,
                revoked_at=membership.revoked_at,
            )
        )

    def all_clinic_ids_exist(self, clinic_ids: frozenset[UUID]) -> bool:
        if not clinic_ids:
            return True
        count = self._session.execute(
            select(func.count()).select_from(ClinicModel).where(ClinicModel.id.in_(clinic_ids))
        ).scalar_one()
        return count == len(clinic_ids)

    def list_active_clinic_ids_for_user(self, user_id: UUID) -> frozenset[UUID]:
        rows = self._session.execute(
            select(ClinicMembershipModel.clinic_id).where(
                ClinicMembershipModel.user_id == user_id,
                ClinicMembershipModel.is_active.is_(True),
                ClinicMembershipModel.revoked_at.is_(None),
            )
        ).scalars()
        return frozenset(rows)

    def get_active_by_user_and_clinic(
        self, user_id: UUID, clinic_id: UUID
    ) -> ClinicMembership | None:
        model = self._session.execute(
            select(ClinicMembershipModel).where(
                ClinicMembershipModel.user_id == user_id,
                ClinicMembershipModel.clinic_id == clinic_id,
                ClinicMembershipModel.is_active.is_(True),
                ClinicMembershipModel.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        if model is None:
            return None
        return ClinicMembership(
            id=model.id,
            user_id=model.user_id,
            clinic_id=model.clinic_id,
            is_active=model.is_active,
            granted_at=model.granted_at,
            granted_by=model.granted_by,
            revoked_at=model.revoked_at,
        )

    def replace_active_clinic_ids(
        self, user_id: UUID, clinic_ids: frozenset[UUID], *, now: datetime, granted_by: UUID
    ) -> None:
        models = (
            self._session.execute(
                select(ClinicMembershipModel).where(ClinicMembershipModel.user_id == user_id)
            )
            .scalars()
            .all()
        )
        by_clinic_id = {model.clinic_id: model for model in models}
        for clinic_id, model in by_clinic_id.items():
            active = clinic_id in clinic_ids
            model.is_active = active
            model.revoked_at = None if active else now
            if active:
                model.granted_at = now
                model.granted_by = granted_by
        for clinic_id in clinic_ids - by_clinic_id.keys():
            self.add(
                ClinicMembership(
                    id=uuid4(),
                    user_id=user_id,
                    clinic_id=clinic_id,
                    granted_at=now,
                    granted_by=granted_by,
                )
            )


class SqlAlchemyLoginFailureRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def record_failure(self, login: str, *, occurred_at: datetime) -> None:
        self._session.add(LoginFailureModel(login=login, occurred_at=occurred_at))

    def count_recent_failures(self, login: str, *, since: datetime) -> int:
        stmt = (
            select(func.count())
            .select_from(LoginFailureModel)
            .where(LoginFailureModel.login == login, LoginFailureModel.occurred_at >= since)
        )
        return self._session.execute(stmt).scalar_one()

    def clear(self, login: str) -> None:
        self._session.execute(delete(LoginFailureModel).where(LoginFailureModel.login == login))
