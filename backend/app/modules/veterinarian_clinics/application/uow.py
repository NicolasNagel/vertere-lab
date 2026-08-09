"""Transactional boundary for the clinic and veterinarian directory."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.repositories import VeterinarianRepository


class ClinicDirectoryUnitOfWork(Protocol):
    @property
    def clinics(self) -> ClinicRepository: ...
    @property
    def veterinarians(self) -> VeterinarianRepository: ...
    @property
    def links(self) -> VeterinarianClinicLinkRepository: ...
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
