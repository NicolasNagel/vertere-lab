"""Imports API — thin router, no business rule (rule:
.claude/rules/02-backend.md). Staging, Fase 1 (clinics/veterinarians/link
backfill), Fase 2/3 (exam catalog/patients), and dry-run/commit pipeline
orchestration all live here."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session as SqlAlchemySession

from app.api.dependencies import get_session, get_unit_of_work
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
from app.modules.identity.api.dependencies import require_permission
from app.modules.imports.api.schemas import (
    AttendanceHistoryImportResponse,
    ImportBatchRead,
    ImportBatchStatusLiteral,
    ImportClinicsResponse,
    ImportExamCategoriesResponse,
    ImportExamsFromHistoryResponse,
    ImportExceptionRead,
    ImportExceptionsListResponse,
    ImportPatientsResponse,
    ImportPipelineResponse,
    ImportRowExceptionRead,
    ImportVeterinariansResponse,
    LinkVeterinarianClinicsResponse,
    PipelinePhaseRead,
    PriceTableImportResponse,
    PriceTablePdfStageResponse,
    SpreadsheetStageResponse,
)
from app.modules.imports.application.import_clinics import (
    ImportClinicsCommand,
    ImportClinicsUseCase,
)
from app.modules.imports.application.import_exam_categories import (
    ImportExamCategoriesCommand,
    ImportExamCategoriesUseCase,
)
from app.modules.imports.application.import_exams_from_history import (
    ImportExamsFromHistoryCommand,
    ImportExamsFromHistoryUseCase,
)
from app.modules.imports.application.import_patients import (
    ImportPatientsCommand,
    ImportPatientsUseCase,
)
from app.modules.imports.application.import_veterinarians import (
    ImportVeterinariansCommand,
    ImportVeterinariansUseCase,
)
from app.modules.imports.application.link_veterinarian_clinics_from_history import (
    LinkVeterinarianClinicsFromHistoryCommand,
    LinkVeterinarianClinicsFromHistoryUseCase,
)
from app.modules.imports.application.list_import_exceptions import (
    ListImportExceptionsQuery,
    ListImportExceptionsUseCase,
)
from app.modules.imports.application.run_attendance_history_import import (
    AttendanceHistoryImportResult,
    CommitAttendanceHistoryImportUseCase,
    DryRunAttendanceHistoryImportUseCase,
    RunAttendanceHistoryImportCommand,
)
from app.modules.imports.application.run_import_pipeline import (
    CommitImportUseCase,
    DryRunImportUseCase,
    ImportPipelineResult,
    RunImportPipelineCommand,
)
from app.modules.imports.application.run_price_table_import import (
    CommitPriceTableImportUseCase,
    DryRunPriceTableImportUseCase,
    PriceTableImportResult,
    RunPriceTableImportCommand,
)
from app.modules.imports.application.stage_price_table_pdf import (
    StagePriceTablePdfCommand,
    StagePriceTablePdfUseCase,
)
from app.modules.imports.application.stage_spreadsheet import (
    StageSpreadsheetCommand,
    StageSpreadsheetUseCase,
)
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
from app.shared.application.authorization import ActorContext
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/imports", tags=["imports"])

_MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB — planilha de origem tem ~1 MB


@router.post("/spreadsheet/stage", response_model=SpreadsheetStageResponse)
async def stage_spreadsheet(
    file: UploadFile = File(...),
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("imports.execute")),
) -> SpreadsheetStageResponse:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="Envie um arquivo .xlsx.")

    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413, detail="Arquivo excede o tamanho máximo permitido (20 MB)."
        )

    with uow:
        use_case = StageSpreadsheetUseCase(
            batches=SqlAlchemyImportBatchRepository(uow.session),
            staging_rows=SqlAlchemyImportStagingRowRepository(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            StageSpreadsheetCommand(
                actor_id=current_user.id,
                actor_permissions=current_user.permissions,
                source_filename=file.filename,
                content=content,
            )
        )
        uow.commit()

    return SpreadsheetStageResponse(
        batch=ImportBatchRead(
            id=result.batch.id,
            source_filename=result.batch.source_filename,
            checksum_sha256=result.batch.checksum_sha256,
            status=result.batch.status.value,
            created_at=result.batch.created_at,
        ),
        already_staged=result.already_staged,
        sheet_row_counts=result.sheet_row_counts,
    )


@router.post("/price-table/stage", response_model=PriceTablePdfStageResponse)
async def stage_price_table_pdf(
    file: UploadFile = File(...),
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("imports.execute")),
) -> PriceTablePdfStageResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Envie um arquivo .pdf.")

    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413, detail="Arquivo excede o tamanho máximo permitido (20 MB)."
        )

    with uow:
        use_case = StagePriceTablePdfUseCase(
            batches=SqlAlchemyImportBatchRepository(uow.session),
            staging_rows=SqlAlchemyImportStagingRowRepository(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            StagePriceTablePdfCommand(
                actor_id=current_user.id,
                actor_permissions=current_user.permissions,
                source_filename=file.filename,
                content=content,
            )
        )
        uow.commit()

    return PriceTablePdfStageResponse(
        batch=ImportBatchRead(
            id=result.batch.id,
            source_filename=result.batch.source_filename,
            checksum_sha256=result.batch.checksum_sha256,
            status=result.batch.status.value,
            created_at=result.batch.created_at,
        ),
        already_staged=result.already_staged,
        item_count=result.item_count,
        ignored_surcharge_line_count=result.ignored_surcharge_line_count,
        unpaired_line_count=result.unpaired_line_count,
    )


def _price_table_response(
    result: PriceTableImportResult, *, status: ImportBatchStatusLiteral
) -> PriceTableImportResponse:
    return PriceTableImportResponse(
        batch_id=result.batch_id,
        status=status,
        imported_count=result.imported_count,
        skipped_existing_count=result.skipped_existing_count,
        exceptions=[
            ImportRowExceptionRead(source_row_number=e.source_row_number, message=e.message)
            for e in result.exceptions
        ],
    )


@router.post("/{batch_id}/price-table/dry-run", response_model=PriceTableImportResponse)
def dry_run_price_table_import(
    batch_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("imports.execute")),
) -> PriceTableImportResponse:
    with uow:
        acquire_batch_lock(uow.session, batch_id)
        use_case = DryRunPriceTableImportUseCase(
            staging_rows=SqlAlchemyImportStagingRowRepository(uow.session),
            batches=SqlAlchemyImportBatchRepository(uow.session),
            exams=SqlAlchemyExamRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            RunPriceTableImportCommand(
                actor_id=current_user.id,
                actor_permissions=current_user.permissions,
                batch_id=batch_id,
            )
        )
        # Deliberately no uow.commit() — same rollback-based dry-run as /dry-run above.

    return _price_table_response(result, status="DRY_RUN_DONE")


@router.post("/{batch_id}/price-table/commit", response_model=PriceTableImportResponse)
def commit_price_table_import(
    batch_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("imports.execute")),
) -> PriceTableImportResponse:
    with uow:
        acquire_batch_lock(uow.session, batch_id)
        use_case = CommitPriceTableImportUseCase(
            staging_rows=SqlAlchemyImportStagingRowRepository(uow.session),
            batches=SqlAlchemyImportBatchRepository(uow.session),
            exceptions=SqlAlchemyImportExceptionRepository(uow.session),
            exams=SqlAlchemyExamRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            RunPriceTableImportCommand(
                actor_id=current_user.id,
                actor_permissions=current_user.permissions,
                batch_id=batch_id,
            )
        )
        uow.commit()

    return _price_table_response(result, status="COMMITTED")


def _attendance_history_response(
    result: AttendanceHistoryImportResult, *, status: ImportBatchStatusLiteral
) -> AttendanceHistoryImportResponse:
    return AttendanceHistoryImportResponse(
        batch_id=result.batch_id,
        status=status,
        imported_count=result.imported_count,
        skipped_existing_count=result.skipped_existing_count,
        rejected_count=result.rejected_count,
        imported_grand_total=result.imported_grand_total,
        exceptions=[
            ImportRowExceptionRead(source_row_number=e.source_row_number, message=e.message)
            for e in result.exceptions
        ],
    )


@router.post("/{batch_id}/attendances/dry-run", response_model=AttendanceHistoryImportResponse)
def dry_run_attendance_history_import(
    batch_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("imports.execute")),
) -> AttendanceHistoryImportResponse:
    with uow:
        acquire_batch_lock(uow.session, batch_id)
        use_case = DryRunAttendanceHistoryImportUseCase(
            staging_rows=SqlAlchemyImportStagingRowRepository(uow.session),
            batches=SqlAlchemyImportBatchRepository(uow.session),
            attendances=SqlAlchemyAttendanceRepository(uow.session),
            attendance_sequences=SqlAlchemyAttendanceSequenceRepository(uow.session),
            clinics=SqlAlchemyClinicRepository(uow.session),
            veterinarians=SqlAlchemyVeterinarianRepository(uow.session),
            patients=SqlAlchemyPatientRepository(uow.session),
            exams=SqlAlchemyExamRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            RunAttendanceHistoryImportCommand(
                actor_id=current_user.id,
                actor_permissions=current_user.permissions,
                batch_id=batch_id,
            )
        )
        # Deliberately no uow.commit() — same rollback-based dry-run as every
        # other phase's /dry-run, including protocol sequence allocation:
        # a dry-run must never actually consume real protocol numbers.

    return _attendance_history_response(result, status="DRY_RUN_DONE")


@router.post("/{batch_id}/attendances/commit", response_model=AttendanceHistoryImportResponse)
def commit_attendance_history_import(
    batch_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("imports.execute")),
) -> AttendanceHistoryImportResponse:
    with uow:
        acquire_batch_lock(uow.session, batch_id)
        use_case = CommitAttendanceHistoryImportUseCase(
            staging_rows=SqlAlchemyImportStagingRowRepository(uow.session),
            batches=SqlAlchemyImportBatchRepository(uow.session),
            exceptions=SqlAlchemyImportExceptionRepository(uow.session),
            attendances=SqlAlchemyAttendanceRepository(uow.session),
            attendance_sequences=SqlAlchemyAttendanceSequenceRepository(uow.session),
            clinics=SqlAlchemyClinicRepository(uow.session),
            veterinarians=SqlAlchemyVeterinarianRepository(uow.session),
            patients=SqlAlchemyPatientRepository(uow.session),
            exams=SqlAlchemyExamRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            RunAttendanceHistoryImportCommand(
                actor_id=current_user.id,
                actor_permissions=current_user.permissions,
                batch_id=batch_id,
            )
        )
        uow.commit()

    return _attendance_history_response(result, status="COMMITTED")


@router.post("/{batch_id}/clinics", response_model=ImportClinicsResponse)
def import_clinics(
    batch_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("imports.execute")),
) -> ImportClinicsResponse:
    with uow:
        acquire_batch_lock(uow.session, batch_id)
        use_case = ImportClinicsUseCase(
            staging_rows=SqlAlchemyImportStagingRowRepository(uow.session),
            clinics=SqlAlchemyClinicRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            ImportClinicsCommand(
                actor_id=current_user.id,
                actor_permissions=current_user.permissions,
                batch_id=batch_id,
            )
        )
        uow.commit()

    return ImportClinicsResponse(
        imported_count=result.imported_count,
        skipped_existing_count=result.skipped_existing_count,
        exceptions=[
            ImportRowExceptionRead(source_row_number=e.source_row_number, message=e.message)
            for e in result.exceptions
        ],
    )


@router.post("/{batch_id}/veterinarians", response_model=ImportVeterinariansResponse)
def import_veterinarians(
    batch_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("imports.execute")),
) -> ImportVeterinariansResponse:
    with uow:
        acquire_batch_lock(uow.session, batch_id)
        use_case = ImportVeterinariansUseCase(
            staging_rows=SqlAlchemyImportStagingRowRepository(uow.session),
            veterinarians=SqlAlchemyVeterinarianRepository(uow.session),
            clinics=SqlAlchemyClinicRepository(uow.session),
            links=SqlAlchemyVeterinarianClinicLinkRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            ImportVeterinariansCommand(
                actor_id=current_user.id,
                actor_permissions=current_user.permissions,
                batch_id=batch_id,
            )
        )
        uow.commit()

    return ImportVeterinariansResponse(
        imported_count=result.imported_count,
        skipped_existing_count=result.skipped_existing_count,
        exceptions=[
            ImportRowExceptionRead(source_row_number=e.source_row_number, message=e.message)
            for e in result.exceptions
        ],
    )


@router.post(
    "/{batch_id}/veterinarian-clinics/backfill", response_model=LinkVeterinarianClinicsResponse
)
def link_veterinarian_clinics_from_history(
    batch_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("imports.execute")),
) -> LinkVeterinarianClinicsResponse:
    with uow:
        acquire_batch_lock(uow.session, batch_id)
        use_case = LinkVeterinarianClinicsFromHistoryUseCase(
            staging_rows=SqlAlchemyImportStagingRowRepository(uow.session),
            clinics=SqlAlchemyClinicRepository(uow.session),
            veterinarians=SqlAlchemyVeterinarianRepository(uow.session),
            links=SqlAlchemyVeterinarianClinicLinkRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            LinkVeterinarianClinicsFromHistoryCommand(
                actor_id=current_user.id,
                actor_permissions=current_user.permissions,
                batch_id=batch_id,
            )
        )
        uow.commit()

    return LinkVeterinarianClinicsResponse(
        links_created_count=result.links_created_count,
        exceptions=[
            ImportRowExceptionRead(source_row_number=e.source_row_number, message=e.message)
            for e in result.exceptions
        ],
    )


@router.post("/{batch_id}/exam-categories", response_model=ImportExamCategoriesResponse)
def import_exam_categories(
    batch_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("imports.execute")),
) -> ImportExamCategoriesResponse:
    with uow:
        acquire_batch_lock(uow.session, batch_id)
        use_case = ImportExamCategoriesUseCase(
            staging_rows=SqlAlchemyImportStagingRowRepository(uow.session),
            categories=SqlAlchemyExamCategoryRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            ImportExamCategoriesCommand(
                actor_id=current_user.id,
                actor_permissions=current_user.permissions,
                batch_id=batch_id,
            )
        )
        uow.commit()

    return ImportExamCategoriesResponse(
        imported_count=result.imported_count,
        skipped_existing_count=result.skipped_existing_count,
    )


@router.post("/{batch_id}/exams", response_model=ImportExamsFromHistoryResponse)
def import_exams_from_history(
    batch_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("imports.execute")),
) -> ImportExamsFromHistoryResponse:
    with uow:
        acquire_batch_lock(uow.session, batch_id)
        use_case = ImportExamsFromHistoryUseCase(
            staging_rows=SqlAlchemyImportStagingRowRepository(uow.session),
            exams=SqlAlchemyExamRepository(uow.session),
            categories=SqlAlchemyExamCategoryRepository(uow.session),
            species=SqlAlchemySpeciesRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            ImportExamsFromHistoryCommand(
                actor_id=current_user.id,
                actor_permissions=current_user.permissions,
                batch_id=batch_id,
            )
        )
        uow.commit()

    return ImportExamsFromHistoryResponse(
        imported_count=result.imported_count,
        skipped_existing_count=result.skipped_existing_count,
        exceptions=[
            ImportRowExceptionRead(source_row_number=e.source_row_number, message=e.message)
            for e in result.exceptions
        ],
    )


@router.post("/{batch_id}/patients", response_model=ImportPatientsResponse)
def import_patients(
    batch_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("imports.execute")),
) -> ImportPatientsResponse:
    with uow:
        acquire_batch_lock(uow.session, batch_id)
        use_case = ImportPatientsUseCase(
            staging_rows=SqlAlchemyImportStagingRowRepository(uow.session),
            patients=SqlAlchemyPatientRepository(uow.session),
            species=SqlAlchemySpeciesRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            ImportPatientsCommand(
                actor_id=current_user.id,
                actor_permissions=current_user.permissions,
                batch_id=batch_id,
            )
        )
        uow.commit()

    return ImportPatientsResponse(
        imported_count=result.imported_count,
        skipped_existing_count=result.skipped_existing_count,
        exceptions=[
            ImportRowExceptionRead(source_row_number=e.source_row_number, message=e.message)
            for e in result.exceptions
        ],
    )


def _pipeline_response(
    result: ImportPipelineResult, *, status: ImportBatchStatusLiteral
) -> ImportPipelineResponse:
    return ImportPipelineResponse(
        batch_id=result.batch_id,
        status=status,
        phases=[
            PipelinePhaseRead(
                phase=phase.phase,
                imported_count=phase.imported_count,
                skipped_existing_count=phase.skipped_existing_count,
                exceptions=[
                    ImportRowExceptionRead(source_row_number=e.source_row_number, message=e.message)
                    for e in phase.exceptions
                ],
            )
            for phase in result.phases
        ],
        total_imported_count=result.total_imported_count,
        total_exceptions_count=len(result.total_exceptions),
    )


@router.post("/{batch_id}/dry-run", response_model=ImportPipelineResponse)
def dry_run_import(
    batch_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("imports.execute")),
) -> ImportPipelineResponse:
    """Runs every phase for real against the current data, but never commits — the transaction
    is simply never committed, so closing the session at the end of `with uow:` rolls it back.
    Nothing from this call persists; the result only exists in this response."""
    with uow:
        acquire_batch_lock(uow.session, batch_id)
        use_case = DryRunImportUseCase(
            staging_rows=SqlAlchemyImportStagingRowRepository(uow.session),
            batches=SqlAlchemyImportBatchRepository(uow.session),
            clinics=SqlAlchemyClinicRepository(uow.session),
            veterinarians=SqlAlchemyVeterinarianRepository(uow.session),
            veterinarian_clinic_links=SqlAlchemyVeterinarianClinicLinkRepository(uow.session),
            exam_categories=SqlAlchemyExamCategoryRepository(uow.session),
            exams=SqlAlchemyExamRepository(uow.session),
            species=SqlAlchemySpeciesRepository(uow.session),
            patients=SqlAlchemyPatientRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            RunImportPipelineCommand(
                actor_id=current_user.id,
                actor_permissions=current_user.permissions,
                batch_id=batch_id,
            )
        )
        # Deliberately no uow.commit() — this is the whole mechanism that makes it a dry run.

    return _pipeline_response(result, status="DRY_RUN_DONE")


@router.post("/{batch_id}/commit", response_model=ImportPipelineResponse)
def commit_import(
    batch_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("imports.execute")),
) -> ImportPipelineResponse:
    with uow:
        acquire_batch_lock(uow.session, batch_id)
        use_case = CommitImportUseCase(
            staging_rows=SqlAlchemyImportStagingRowRepository(uow.session),
            batches=SqlAlchemyImportBatchRepository(uow.session),
            exceptions=SqlAlchemyImportExceptionRepository(uow.session),
            clinics=SqlAlchemyClinicRepository(uow.session),
            veterinarians=SqlAlchemyVeterinarianRepository(uow.session),
            veterinarian_clinic_links=SqlAlchemyVeterinarianClinicLinkRepository(uow.session),
            exam_categories=SqlAlchemyExamCategoryRepository(uow.session),
            exams=SqlAlchemyExamRepository(uow.session),
            species=SqlAlchemySpeciesRepository(uow.session),
            patients=SqlAlchemyPatientRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            RunImportPipelineCommand(
                actor_id=current_user.id,
                actor_permissions=current_user.permissions,
                batch_id=batch_id,
            )
        )
        uow.commit()

    return _pipeline_response(result, status="COMMITTED")


@router.get("/{batch_id}/exceptions", response_model=ImportExceptionsListResponse)
def list_import_exceptions(
    batch_id: UUID,
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("imports.execute")),
) -> ImportExceptionsListResponse:
    use_case = ListImportExceptionsUseCase(exceptions=SqlAlchemyImportExceptionRepository(session))
    exceptions = use_case.execute(
        ListImportExceptionsQuery(actor_permissions=current_user.permissions, batch_id=batch_id)
    )
    return ImportExceptionsListResponse(
        batch_id=batch_id,
        exceptions=[
            ImportExceptionRead(
                phase=exc.phase,
                source_row_number=exc.source_row_number,
                message=exc.message,
                created_at=exc.created_at,
            )
            for exc in exceptions
        ],
    )
