from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.patients.domain.repositories import PatientRepository, SpeciesRepository


class PatientUnitOfWork(Protocol):
    @property
    def patients(self) -> PatientRepository: ...
    @property
    def species(self) -> SpeciesRepository: ...
    @property
    def clinics(self) -> ClinicRepository: ...
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
