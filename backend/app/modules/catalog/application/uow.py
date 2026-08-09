from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.domain.repositories import ExamCategoryRepository, ExamRepository
from app.modules.patients.domain.repositories import SpeciesRepository


class CatalogUnitOfWork(Protocol):
    @property
    def exams(self) -> ExamRepository: ...
    @property
    def categories(self) -> ExamCategoryRepository: ...
    @property
    def species(self) -> SpeciesRepository: ...
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
