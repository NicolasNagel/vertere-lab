"""Dry-run/commit entry points for Fase 4 (attendance-history migration) —
same shape as `run_price_table_import.py`, wrapping
`ImportAttendanceHistoryUseCase`. Kept as its own phase rather than folded
into `run_import_pipeline.py`: it depends on clinics/veterinarians/patients/
exams already being committed by that pipeline (and, for the money split
on combined lines, on the exam catalog already carrying real prices) — it
is meant to run *after* the pipeline and price-table phases, not alongside
them.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.attendances.domain.repositories import (
    AttendanceRepository,
    AttendanceSequenceRepository,
)
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.domain.repositories import ExamRepository
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.imports.application.import_attendance_history import (
    ImportAttendanceHistoryCommand,
    ImportAttendanceHistoryUseCase,
    ImportRowException,
)
from app.modules.imports.domain.entities import ImportException
from app.modules.imports.domain.repositories import (
    ImportBatchRepository,
    ImportExceptionRepository,
    ImportStagingRowRepository,
)
from app.modules.patients.domain.repositories import PatientRepository
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.application.clock import Clock
from app.shared.domain.errors import NotFoundError

_PHASE_ATTENDANCES = "attendances"


@dataclass(frozen=True, kw_only=True)
class RunAttendanceHistoryImportCommand:
    actor_id: UUID | None
    actor_permissions: frozenset[str]
    batch_id: UUID


@dataclass(frozen=True, kw_only=True)
class AttendanceHistoryImportResult:
    batch_id: UUID
    imported_count: int
    skipped_existing_count: int
    rejected_count: int
    imported_grand_total: Decimal
    exceptions: tuple[ImportRowException, ...]


class _Runner:
    def __init__(
        self,
        *,
        staging_rows: ImportStagingRowRepository,
        batches: ImportBatchRepository,
        attendances: AttendanceRepository,
        attendance_sequences: AttendanceSequenceRepository,
        clinics: ClinicRepository,
        veterinarians: VeterinarianRepository,
        patients: PatientRepository,
        exams: ExamRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._batches = batches
        self._phase = ImportAttendanceHistoryUseCase(
            staging_rows=staging_rows,
            attendances=attendances,
            attendance_sequences=attendance_sequences,
            clinics=clinics,
            veterinarians=veterinarians,
            patients=patients,
            exams=exams,
            audit=audit,
            clock=clock,
        )

    def run(self, command: RunAttendanceHistoryImportCommand) -> AttendanceHistoryImportResult:
        if self._batches.get_by_id(command.batch_id) is None:
            raise NotFoundError("Lote de importação não encontrado.")
        result = self._phase.execute(
            ImportAttendanceHistoryCommand(
                actor_id=command.actor_id,
                actor_permissions=command.actor_permissions,
                batch_id=command.batch_id,
            )
        )
        return AttendanceHistoryImportResult(
            batch_id=command.batch_id,
            imported_count=result.imported_count,
            skipped_existing_count=result.skipped_existing_count,
            rejected_count=result.rejected_count,
            imported_grand_total=result.imported_grand_total,
            exceptions=result.exceptions,
        )


class DryRunAttendanceHistoryImportUseCase:
    """Runs the phase for real against the caller's session, but the caller
    (the router) must never commit that transaction — same rollback-based
    dry-run as every other phase's dry-run entry point."""

    def __init__(
        self,
        *,
        staging_rows: ImportStagingRowRepository,
        batches: ImportBatchRepository,
        attendances: AttendanceRepository,
        attendance_sequences: AttendanceSequenceRepository,
        clinics: ClinicRepository,
        veterinarians: VeterinarianRepository,
        patients: PatientRepository,
        exams: ExamRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._runner = _Runner(
            staging_rows=staging_rows,
            batches=batches,
            attendances=attendances,
            attendance_sequences=attendance_sequences,
            clinics=clinics,
            veterinarians=veterinarians,
            patients=patients,
            exams=exams,
            audit=audit,
            clock=clock,
        )

    def execute(self, command: RunAttendanceHistoryImportCommand) -> AttendanceHistoryImportResult:
        return self._runner.run(command)


class CommitAttendanceHistoryImportUseCase:
    """Same phase run as the dry-run, plus persisting every collected
    exception (deduplicated against what's already there) — never marks the
    batch `COMMITTED` on its own: the xlsx pipeline (`run_import_pipeline.py`)
    already owns that transition for this batch, and this phase always runs
    after it. No `MonthlyClosure` is created here either — that stays a
    separate, explicitly human-approved step
    (`.claude/rules/10-data-migration.md`: "importação nunca marca um
    período como fechado sem aprovação humana explícita")."""

    def __init__(
        self,
        *,
        staging_rows: ImportStagingRowRepository,
        batches: ImportBatchRepository,
        exceptions: ImportExceptionRepository,
        attendances: AttendanceRepository,
        attendance_sequences: AttendanceSequenceRepository,
        clinics: ClinicRepository,
        veterinarians: VeterinarianRepository,
        patients: PatientRepository,
        exams: ExamRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._runner = _Runner(
            staging_rows=staging_rows,
            batches=batches,
            attendances=attendances,
            attendance_sequences=attendance_sequences,
            clinics=clinics,
            veterinarians=veterinarians,
            patients=patients,
            exams=exams,
            audit=audit,
            clock=clock,
        )
        self._exceptions = exceptions
        self._clock = clock

    def execute(self, command: RunAttendanceHistoryImportCommand) -> AttendanceHistoryImportResult:
        result = self._runner.run(command)

        already_persisted = {
            (exc.phase, exc.source_row_number, exc.message)
            for exc in self._exceptions.list_by_batch(command.batch_id)
        }
        now = self._clock.now()
        exception_rows = [
            ImportException(
                id=uuid4(),
                batch_id=command.batch_id,
                phase=_PHASE_ATTENDANCES,
                source_row_number=exc.source_row_number,
                message=exc.message,
                created_at=now,
            )
            for exc in result.exceptions
            if (_PHASE_ATTENDANCES, exc.source_row_number, exc.message) not in already_persisted
        ]
        if exception_rows:
            self._exceptions.add_many(exception_rows)

        return result
