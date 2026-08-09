"""SQLAlchemy adapter for the identity unit of work."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from app.modules.audit.infrastructure.repositories import SqlAlchemyAuditLogWriter
from app.modules.identity.infrastructure.repositories import (
    SqlAlchemyClinicMembershipRepository,
    SqlAlchemyLabMembershipRepository,
    SqlAlchemyLoginFailureRepository,
    SqlAlchemyPermissionRepository,
    SqlAlchemyRoleRepository,
    SqlAlchemySessionRepository,
    SqlAlchemyUserRepository,
)
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork


class SqlAlchemyIdentityUnitOfWork:
    def __init__(self, base: SqlAlchemyUnitOfWork) -> None:
        self._base = base

    def __enter__(self) -> Self:
        self._base.__enter__()
        session = self._base.session
        self.users = SqlAlchemyUserRepository(session)
        self.roles = SqlAlchemyRoleRepository(session)
        self.sessions = SqlAlchemySessionRepository(session)
        self.lab_memberships = SqlAlchemyLabMembershipRepository(session)
        self.clinic_memberships = SqlAlchemyClinicMembershipRepository(session)
        self.login_failures = SqlAlchemyLoginFailureRepository(session)
        self.permissions = SqlAlchemyPermissionRepository(session)
        self.audit = SqlAlchemyAuditLogWriter(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._base.__exit__(exc_type, exc, traceback)

    def commit(self) -> None:
        self._base.commit()
