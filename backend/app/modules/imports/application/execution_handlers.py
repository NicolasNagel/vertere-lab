"""Atomic handlers for import dry-runs and commits."""

from __future__ import annotations

from app.modules.imports.application.run_attendance_history_import import (
    AttendanceHistoryImportResult,
    CommitAttendanceHistoryImportUseCase,
    DryRunAttendanceHistoryImportUseCase,
    RunAttendanceHistoryImportCommand,
)
from app.modules.imports.application.run_price_table_import import (
    CommitPriceTableImportUseCase,
    DryRunPriceTableImportUseCase,
    PriceTableImportResult,
    RunPriceTableImportCommand,
)
from app.modules.imports.application.uow import ImportUnitOfWork
from app.shared.application.clock import Clock


def handle_dry_run_price_table_import(
    *, uow: ImportUnitOfWork, command: RunPriceTableImportCommand, clock: Clock
) -> PriceTableImportResult:
    with uow:
        uow.lock_batch(command.batch_id)
        return DryRunPriceTableImportUseCase(
            staging_rows=uow.staging_rows,
            batches=uow.batches,
            exams=uow.exams,
            audit=uow.audit,
            clock=clock,
        ).execute(command)


def handle_commit_price_table_import(
    *, uow: ImportUnitOfWork, command: RunPriceTableImportCommand, clock: Clock
) -> PriceTableImportResult:
    with uow:
        uow.lock_batch(command.batch_id)
        result = CommitPriceTableImportUseCase(
            staging_rows=uow.staging_rows,
            batches=uow.batches,
            exceptions=uow.exceptions,
            exams=uow.exams,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result


def handle_dry_run_attendance_history_import(
    *, uow: ImportUnitOfWork, command: RunAttendanceHistoryImportCommand, clock: Clock
) -> AttendanceHistoryImportResult:
    with uow:
        uow.lock_batch(command.batch_id)
        return DryRunAttendanceHistoryImportUseCase(
            staging_rows=uow.staging_rows,
            batches=uow.batches,
            attendances=uow.attendances,
            attendance_sequences=uow.attendance_sequences,
            clinics=uow.clinics,
            veterinarians=uow.veterinarians,
            patients=uow.patients,
            exams=uow.exams,
            audit=uow.audit,
            clock=clock,
        ).execute(command)


def handle_commit_attendance_history_import(
    *, uow: ImportUnitOfWork, command: RunAttendanceHistoryImportCommand, clock: Clock
) -> AttendanceHistoryImportResult:
    with uow:
        uow.lock_batch(command.batch_id)
        result = CommitAttendanceHistoryImportUseCase(
            staging_rows=uow.staging_rows,
            batches=uow.batches,
            exceptions=uow.exceptions,
            attendances=uow.attendances,
            attendance_sequences=uow.attendance_sequences,
            clinics=uow.clinics,
            veterinarians=uow.veterinarians,
            patients=uow.patients,
            exams=uow.exams,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result
