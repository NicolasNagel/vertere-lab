"""Atomic handlers for the import phases and aggregate pipeline."""

from __future__ import annotations

from app.modules.imports.application.import_clinics import (
    ImportClinicsCommand,
    ImportClinicsResult,
    ImportClinicsUseCase,
)
from app.modules.imports.application.import_exam_categories import (
    ImportExamCategoriesCommand,
    ImportExamCategoriesResult,
    ImportExamCategoriesUseCase,
)
from app.modules.imports.application.import_exams_from_history import (
    ImportExamsFromHistoryCommand,
    ImportExamsFromHistoryResult,
    ImportExamsFromHistoryUseCase,
)
from app.modules.imports.application.import_patients import (
    ImportPatientsCommand,
    ImportPatientsResult,
    ImportPatientsUseCase,
)
from app.modules.imports.application.import_veterinarians import (
    ImportVeterinariansCommand,
    ImportVeterinariansResult,
    ImportVeterinariansUseCase,
)
from app.modules.imports.application.link_veterinarian_clinics_from_history import (
    LinkVeterinarianClinicsFromHistoryCommand,
    LinkVeterinarianClinicsFromHistoryResult,
    LinkVeterinarianClinicsFromHistoryUseCase,
)
from app.modules.imports.application.run_import_pipeline import (
    CommitImportUseCase,
    DryRunImportUseCase,
    ImportPipelineResult,
    RunImportPipelineCommand,
)
from app.modules.imports.application.uow import ImportUnitOfWork
from app.shared.application.clock import Clock


def handle_import_clinics(
    *, uow: ImportUnitOfWork, command: ImportClinicsCommand, clock: Clock
) -> ImportClinicsResult:
    with uow:
        uow.lock_batch(command.batch_id)
        result = ImportClinicsUseCase(
            staging_rows=uow.staging_rows,
            clinics=uow.clinics,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result


def handle_import_veterinarians(
    *, uow: ImportUnitOfWork, command: ImportVeterinariansCommand, clock: Clock
) -> ImportVeterinariansResult:
    with uow:
        uow.lock_batch(command.batch_id)
        result = ImportVeterinariansUseCase(
            staging_rows=uow.staging_rows,
            veterinarians=uow.veterinarians,
            clinics=uow.clinics,
            links=uow.veterinarian_clinic_links,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result


def handle_link_veterinarian_clinics(
    *,
    uow: ImportUnitOfWork,
    command: LinkVeterinarianClinicsFromHistoryCommand,
    clock: Clock,
) -> LinkVeterinarianClinicsFromHistoryResult:
    with uow:
        uow.lock_batch(command.batch_id)
        result = LinkVeterinarianClinicsFromHistoryUseCase(
            staging_rows=uow.staging_rows,
            clinics=uow.clinics,
            veterinarians=uow.veterinarians,
            links=uow.veterinarian_clinic_links,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result


def handle_import_exam_categories(
    *, uow: ImportUnitOfWork, command: ImportExamCategoriesCommand, clock: Clock
) -> ImportExamCategoriesResult:
    with uow:
        uow.lock_batch(command.batch_id)
        result = ImportExamCategoriesUseCase(
            staging_rows=uow.staging_rows,
            categories=uow.exam_categories,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result


def handle_import_exams(
    *, uow: ImportUnitOfWork, command: ImportExamsFromHistoryCommand, clock: Clock
) -> ImportExamsFromHistoryResult:
    with uow:
        uow.lock_batch(command.batch_id)
        result = ImportExamsFromHistoryUseCase(
            staging_rows=uow.staging_rows,
            exams=uow.exams,
            categories=uow.exam_categories,
            species=uow.species,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result


def handle_import_patients(
    *, uow: ImportUnitOfWork, command: ImportPatientsCommand, clock: Clock
) -> ImportPatientsResult:
    with uow:
        uow.lock_batch(command.batch_id)
        result = ImportPatientsUseCase(
            staging_rows=uow.staging_rows,
            patients=uow.patients,
            species=uow.species,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result


def handle_dry_run_import_pipeline(
    *, uow: ImportUnitOfWork, command: RunImportPipelineCommand, clock: Clock
) -> ImportPipelineResult:
    with uow:
        uow.lock_batch(command.batch_id)
        return DryRunImportUseCase(
            staging_rows=uow.staging_rows,
            batches=uow.batches,
            clinics=uow.clinics,
            veterinarians=uow.veterinarians,
            veterinarian_clinic_links=uow.veterinarian_clinic_links,
            exam_categories=uow.exam_categories,
            exams=uow.exams,
            species=uow.species,
            patients=uow.patients,
            audit=uow.audit,
            clock=clock,
        ).execute(command)


def handle_commit_import_pipeline(
    *, uow: ImportUnitOfWork, command: RunImportPipelineCommand, clock: Clock
) -> ImportPipelineResult:
    with uow:
        uow.lock_batch(command.batch_id)
        result = CommitImportUseCase(
            staging_rows=uow.staging_rows,
            batches=uow.batches,
            exceptions=uow.exceptions,
            clinics=uow.clinics,
            veterinarians=uow.veterinarians,
            veterinarian_clinic_links=uow.veterinarian_clinic_links,
            exam_categories=uow.exam_categories,
            exams=uow.exams,
            species=uow.species,
            patients=uow.patients,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result
