from __future__ import annotations

from app.modules.catalog.application.create_exam import CreateExamCommand, CreateExamUseCase
from app.modules.catalog.application.create_exam_category import (
    CreateExamCategoryCommand,
    CreateExamCategoryUseCase,
)
from app.modules.catalog.application.deactivate_exam import (
    DeactivateExamCommand,
    DeactivateExamUseCase,
)
from app.modules.catalog.application.deactivate_exam_category import (
    DeactivateExamCategoryCommand,
    DeactivateExamCategoryUseCase,
)
from app.modules.catalog.application.dtos import ExamCategoryDTO, ExamDTO
from app.modules.catalog.application.exam_code_generator import generate_exam_code
from app.modules.catalog.application.import_exams import (
    ImportExamsCommand,
    ImportExamsResult,
    ImportExamsUseCase,
)
from app.modules.catalog.application.uow import CatalogUnitOfWork
from app.modules.catalog.application.update_exam import UpdateExamCommand, UpdateExamUseCase
from app.modules.catalog.application.update_exam_category import (
    UpdateExamCategoryCommand,
    UpdateExamCategoryUseCase,
)
from app.shared.application.clock import Clock


def handle_create_category(
    *, uow: CatalogUnitOfWork, command: CreateExamCategoryCommand, clock: Clock
) -> ExamCategoryDTO:
    with uow:
        r = CreateExamCategoryUseCase(
            categories=uow.categories, audit=uow.audit, clock=clock
        ).execute(command)
        uow.commit()
        return r


def handle_update_category(
    *, uow: CatalogUnitOfWork, command: UpdateExamCategoryCommand, clock: Clock
) -> ExamCategoryDTO:
    with uow:
        r = UpdateExamCategoryUseCase(
            categories=uow.categories, audit=uow.audit, clock=clock
        ).execute(command)
        uow.commit()
        return r


def handle_deactivate_category(
    *, uow: CatalogUnitOfWork, command: DeactivateExamCategoryCommand, clock: Clock
) -> ExamCategoryDTO:
    with uow:
        r = DeactivateExamCategoryUseCase(
            categories=uow.categories, audit=uow.audit, clock=clock
        ).execute(command)
        uow.commit()
        return r


def handle_create_exam(
    *, uow: CatalogUnitOfWork, command: CreateExamCommand, clock: Clock
) -> ExamDTO:
    with uow:
        r = CreateExamUseCase(
            exams=uow.exams,
            categories=uow.categories,
            species=uow.species,
            audit=uow.audit,
            clock=clock,
            code_generator=generate_exam_code,
        ).execute(command)
        uow.commit()
        return r


def handle_update_exam(
    *, uow: CatalogUnitOfWork, command: UpdateExamCommand, clock: Clock
) -> ExamDTO:
    with uow:
        r = UpdateExamUseCase(
            exams=uow.exams,
            categories=uow.categories,
            species=uow.species,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return r


def handle_deactivate_exam(
    *, uow: CatalogUnitOfWork, command: DeactivateExamCommand, clock: Clock
) -> ExamDTO:
    with uow:
        r = DeactivateExamUseCase(exams=uow.exams, audit=uow.audit, clock=clock).execute(command)
        uow.commit()
        return r


def handle_import_exams(
    *, uow: CatalogUnitOfWork, command: ImportExamsCommand, clock: Clock
) -> ImportExamsResult:
    with uow:
        r = ImportExamsUseCase(
            exams=uow.exams,
            categories=uow.categories,
            species=uow.species,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return r
