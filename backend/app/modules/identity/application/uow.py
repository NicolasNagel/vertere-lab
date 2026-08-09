"""Transactional boundary for identity application handlers."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.identity.domain.repositories import (
    ClinicMembershipRepository,
    LabMembershipRepository,
    LoginFailureRepository,
    PermissionRepository,
    RoleRepository,
    SessionRepository,
    UserRepository,
)


class IdentityUnitOfWork(Protocol):
    @property
    def users(self) -> UserRepository: ...
    @property
    def roles(self) -> RoleRepository: ...
    @property
    def sessions(self) -> SessionRepository: ...
    @property
    def lab_memberships(self) -> LabMembershipRepository: ...
    @property
    def clinic_memberships(self) -> ClinicMembershipRepository: ...
    @property
    def login_failures(self) -> LoginFailureRepository: ...
    @property
    def permissions(self) -> PermissionRepository: ...
    @property
    def audit(self) -> AuditLogWriter: ...

    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    def commit(self) -> None: ...
