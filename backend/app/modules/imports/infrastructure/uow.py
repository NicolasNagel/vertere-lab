"""SQLAlchemy adapter for the import unit of work."""

from __future__ import annotations

from types import TracebackType
from typing import Self
from uuid import UUID

from app.modules.attendances.infrastructure.repositories import (
    SqlAlchemyAttendanceRepository,
    SqlAlchemyAttendanceSequenceRepository,
)
from app.modules.audit.infrastructure.repositories import SqlAlchemyAuditLogWriter
from app.modules.catalog.infrastructure.repositories import (
    SqlAlchemyExamCategoryRepository,
    SqlAlchemyExamRepository,
)
from app.modules.clinics.infrastructure.repositories import SqlAlchemyClinicRepository
from app.modules.imports.infrastructure.locking import acquire_batch_lock
from app.modules.imports.infrastructure.repositories import (
    SqlAlchemyImportBatchRepository,
    SqlAlchemyImportExceptionRepository,
    SqlAlchemyImportStagingRowRepository,
)
from app.modules.patients.infrastructure.repositories import (
    SqlAlchemyPatientRepository,
    SqlAlchemySpeciesRepository,
)
from app.modules.veterinarian_clinics.infrastructure.repositories import (
    SqlAlchemyVeterinarianClinicLinkRepository,
)
from app.modules.veterinarians.infrastructure.repositories import SqlAlchemyVeterinarianRepository
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork


class SqlAlchemyImportUnitOfWork:
    def __init__(self, base: SqlAlchemyUnitOfWork) -> None:
        self._base = base

    def __enter__(self) -> Self:
        self._base.__enter__()
        session = self._base.session
        self.batches = SqlAlchemyImportBatchRepository(session)
        self.staging_rows = SqlAlchemyImportStagingRowRepository(session)
        self.exceptions = SqlAlchemyImportExceptionRepository(session)
        self.exams = SqlAlchemyExamRepository(session)
        self.exam_categories = SqlAlchemyExamCategoryRepository(session)
        self.attendances = SqlAlchemyAttendanceRepository(session)
        self.attendance_sequences = SqlAlchemyAttendanceSequenceRepository(session)
        self.clinics = SqlAlchemyClinicRepository(session)
        self.veterinarians = SqlAlchemyVeterinarianRepository(session)
        self.patients = SqlAlchemyPatientRepository(session)
        self.species = SqlAlchemySpeciesRepository(session)
        self.veterinarian_clinic_links = SqlAlchemyVeterinarianClinicLinkRepository(session)
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

    def lock_batch(self, batch_id: UUID) -> None:
        acquire_batch_lock(self._base.session, batch_id)
