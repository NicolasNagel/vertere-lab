"""Transactional boundaries used by import application handlers."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.modules.attendances.domain.repositories import (
    AttendanceRepository,
    AttendanceSequenceRepository,
)
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.domain.repositories import ExamCategoryRepository, ExamRepository
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.imports.domain.repositories import (
    ImportBatchRepository,
    ImportExceptionRepository,
    ImportStagingRowRepository,
)
from app.modules.patients.domain.repositories import PatientRepository, SpeciesRepository
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.repositories import VeterinarianRepository


class ImportUnitOfWork(Protocol):
    @property
    def batches(self) -> ImportBatchRepository: ...

    @property
    def staging_rows(self) -> ImportStagingRowRepository: ...

    @property
    def exceptions(self) -> ImportExceptionRepository: ...

    @property
    def exams(self) -> ExamRepository: ...

    @property
    def exam_categories(self) -> ExamCategoryRepository: ...

    @property
    def attendances(self) -> AttendanceRepository: ...

    @property
    def attendance_sequences(self) -> AttendanceSequenceRepository: ...

    @property
    def clinics(self) -> ClinicRepository: ...

    @property
    def veterinarians(self) -> VeterinarianRepository: ...

    @property
    def patients(self) -> PatientRepository: ...

    @property
    def species(self) -> SpeciesRepository: ...

    @property
    def veterinarian_clinic_links(self) -> VeterinarianClinicLinkRepository: ...

    @property
    def audit(self) -> AuditLogWriter: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def lock_batch(self, batch_id: UUID) -> None: ...

    def commit(self) -> None: ...
