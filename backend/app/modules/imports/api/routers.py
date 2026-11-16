"""Imports API — thin router, no business rule (rule:
.claude/rules/02-backend.md). Staging, Fase 1 (clinics/veterinarians/link
backfill), Fase 2/3 (exam catalog/patients), and dry-run/commit pipeline
orchestration all live here."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session as SqlAlchemySession

from app.api.dependencies import get_session, get_unit_of_work
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
from app.modules.imports.application.execution_handlers import (
    handle_commit_attendance_history_import,
    handle_commit_price_table_import,
    handle_dry_run_attendance_history_import,
    handle_dry_run_price_table_import,
)
from app.modules.imports.application.import_clinics import (
    ImportClinicsCommand,
)
from app.modules.imports.application.import_exam_categories import (
    ImportExamCategoriesCommand,
)
from app.modules.imports.application.import_exams_from_history import (
    ImportExamsFromHistoryCommand,
)
from app.modules.imports.application.import_patients import (
    ImportPatientsCommand,
)
from app.modules.imports.application.import_veterinarians import (
    ImportVeterinariansCommand,
)
from app.modules.imports.application.link_veterinarian_clinics_from_history import (
    LinkVeterinarianClinicsFromHistoryCommand,
)
from app.modules.imports.application.list_import_exceptions import (
    ListImportExceptionsQuery,
    ListImportExceptionsUseCase,
)
from app.modules.imports.application.pipeline_handlers import (
    handle_commit_import_pipeline,
    handle_dry_run_import_pipeline,
    handle_import_clinics,
    handle_import_exam_categories,
    handle_import_exams,
    handle_import_patients,
    handle_import_veterinarians,
    handle_link_veterinarian_clinics,
)
from app.modules.imports.application.run_attendance_history_import import (
    AttendanceHistoryImportResult,
    RunAttendanceHistoryImportCommand,
)
from app.modules.imports.application.run_import_pipeline import (
    ImportPipelineResult,
    RunImportPipelineCommand,
)
from app.modules.imports.application.run_price_table_import import (
    PriceTableImportResult,
    RunPriceTableImportCommand,
)
from app.modules.imports.application.stage_price_table_pdf import (
    StagePriceTablePdfCommand,
)
from app.modules.imports.application.stage_spreadsheet import (
    StageSpreadsheetCommand,
)
from app.modules.imports.application.staging_handlers import (
    handle_stage_price_table_pdf,
    handle_stage_spreadsheet,
)
from app.modules.imports.infrastructure.repositories import (
    SqlAlchemyImportExceptionRepository,
)
from app.modules.imports.infrastructure.uow import SqlAlchemyImportUnitOfWork
from app.shared.application.authorization import ActorContext
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/imports", tags=["imports"])

_IMPORT_ACCESS = require_permission("imports.execute", allowed_scopes=frozenset({"GLOBAL", "LAB"}))

_MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB — planilha de origem tem ~1 MB
_READ_CHUNK_SIZE = 1024 * 1024


async def _read_within_limit(file: UploadFile) -> bytes:
    """Lê o upload em blocos e aborta ao passar do limite, sem carregá-lo inteiro antes."""

    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_READ_CHUNK_SIZE):
        total += len(chunk)
        if total > _MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, detail="Arquivo excede o tamanho máximo permitido (20 MB)."
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/spreadsheet/stage", response_model=SpreadsheetStageResponse)
async def stage_spreadsheet(
    file: UploadFile = File(...),
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(_IMPORT_ACCESS),
) -> SpreadsheetStageResponse:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="Envie um arquivo .xlsx.")

    content = await _read_within_limit(file)

    result = handle_stage_spreadsheet(
        uow=SqlAlchemyImportUnitOfWork(uow),
        command=StageSpreadsheetCommand(
            actor_id=current_user.id,
            actor_permissions=current_user.permissions,
            source_filename=file.filename,
            content=content,
        ),
        clock=SystemClock(),
    )

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
    current_user: ActorContext = Depends(_IMPORT_ACCESS),
) -> PriceTablePdfStageResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Envie um arquivo .pdf.")

    content = await _read_within_limit(file)

    result = handle_stage_price_table_pdf(
        uow=SqlAlchemyImportUnitOfWork(uow),
        command=StagePriceTablePdfCommand(
            actor_id=current_user.id,
            actor_permissions=current_user.permissions,
            source_filename=file.filename,
            content=content,
        ),
        clock=SystemClock(),
    )

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
    current_user: ActorContext = Depends(_IMPORT_ACCESS),
) -> PriceTableImportResponse:
    result = handle_dry_run_price_table_import(
        uow=SqlAlchemyImportUnitOfWork(uow),
        command=RunPriceTableImportCommand(
            actor_id=current_user.id,
            actor_permissions=current_user.permissions,
            batch_id=batch_id,
        ),
        clock=SystemClock(),
    )

    return _price_table_response(result, status="DRY_RUN_DONE")


@router.post("/{batch_id}/price-table/commit", response_model=PriceTableImportResponse)
def commit_price_table_import(
    batch_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(_IMPORT_ACCESS),
) -> PriceTableImportResponse:
    result = handle_commit_price_table_import(
        uow=SqlAlchemyImportUnitOfWork(uow),
        command=RunPriceTableImportCommand(
            actor_id=current_user.id,
            actor_permissions=current_user.permissions,
            batch_id=batch_id,
        ),
        clock=SystemClock(),
    )

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
    current_user: ActorContext = Depends(_IMPORT_ACCESS),
) -> AttendanceHistoryImportResponse:
    result = handle_dry_run_attendance_history_import(
        uow=SqlAlchemyImportUnitOfWork(uow),
        command=RunAttendanceHistoryImportCommand(
            actor_id=current_user.id,
            actor_permissions=current_user.permissions,
            batch_id=batch_id,
        ),
        clock=SystemClock(),
    )

    return _attendance_history_response(result, status="DRY_RUN_DONE")


@router.post("/{batch_id}/attendances/commit", response_model=AttendanceHistoryImportResponse)
def commit_attendance_history_import(
    batch_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(_IMPORT_ACCESS),
) -> AttendanceHistoryImportResponse:
    result = handle_commit_attendance_history_import(
        uow=SqlAlchemyImportUnitOfWork(uow),
        command=RunAttendanceHistoryImportCommand(
            actor_id=current_user.id,
            actor_permissions=current_user.permissions,
            batch_id=batch_id,
        ),
        clock=SystemClock(),
    )

    return _attendance_history_response(result, status="COMMITTED")


@router.post("/{batch_id}/clinics", response_model=ImportClinicsResponse)
def import_clinics(
    batch_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(_IMPORT_ACCESS),
) -> ImportClinicsResponse:
    result = handle_import_clinics(
        uow=SqlAlchemyImportUnitOfWork(uow),
        command=ImportClinicsCommand(
            actor_id=current_user.id,
            actor_permissions=current_user.permissions,
            batch_id=batch_id,
        ),
        clock=SystemClock(),
    )

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
    current_user: ActorContext = Depends(_IMPORT_ACCESS),
) -> ImportVeterinariansResponse:
    result = handle_import_veterinarians(
        uow=SqlAlchemyImportUnitOfWork(uow),
        command=ImportVeterinariansCommand(
            actor_id=current_user.id,
            actor_permissions=current_user.permissions,
            batch_id=batch_id,
        ),
        clock=SystemClock(),
    )

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
    current_user: ActorContext = Depends(_IMPORT_ACCESS),
) -> LinkVeterinarianClinicsResponse:
    result = handle_link_veterinarian_clinics(
        uow=SqlAlchemyImportUnitOfWork(uow),
        command=LinkVeterinarianClinicsFromHistoryCommand(
            actor_id=current_user.id,
            actor_permissions=current_user.permissions,
            batch_id=batch_id,
        ),
        clock=SystemClock(),
    )

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
    current_user: ActorContext = Depends(_IMPORT_ACCESS),
) -> ImportExamCategoriesResponse:
    result = handle_import_exam_categories(
        uow=SqlAlchemyImportUnitOfWork(uow),
        command=ImportExamCategoriesCommand(
            actor_id=current_user.id,
            actor_permissions=current_user.permissions,
            batch_id=batch_id,
        ),
        clock=SystemClock(),
    )

    return ImportExamCategoriesResponse(
        imported_count=result.imported_count,
        skipped_existing_count=result.skipped_existing_count,
    )


@router.post("/{batch_id}/exams", response_model=ImportExamsFromHistoryResponse)
def import_exams_from_history(
    batch_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(_IMPORT_ACCESS),
) -> ImportExamsFromHistoryResponse:
    result = handle_import_exams(
        uow=SqlAlchemyImportUnitOfWork(uow),
        command=ImportExamsFromHistoryCommand(
            actor_id=current_user.id,
            actor_permissions=current_user.permissions,
            batch_id=batch_id,
        ),
        clock=SystemClock(),
    )

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
    current_user: ActorContext = Depends(_IMPORT_ACCESS),
) -> ImportPatientsResponse:
    result = handle_import_patients(
        uow=SqlAlchemyImportUnitOfWork(uow),
        command=ImportPatientsCommand(
            actor_id=current_user.id,
            actor_permissions=current_user.permissions,
            batch_id=batch_id,
        ),
        clock=SystemClock(),
    )

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
    current_user: ActorContext = Depends(_IMPORT_ACCESS),
) -> ImportPipelineResponse:
    result = handle_dry_run_import_pipeline(
        uow=SqlAlchemyImportUnitOfWork(uow),
        command=RunImportPipelineCommand(
            actor_id=current_user.id,
            actor_permissions=current_user.permissions,
            batch_id=batch_id,
        ),
        clock=SystemClock(),
    )

    return _pipeline_response(result, status="DRY_RUN_DONE")


@router.post("/{batch_id}/commit", response_model=ImportPipelineResponse)
def commit_import(
    batch_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(_IMPORT_ACCESS),
) -> ImportPipelineResponse:
    result = handle_commit_import_pipeline(
        uow=SqlAlchemyImportUnitOfWork(uow),
        command=RunImportPipelineCommand(
            actor_id=current_user.id,
            actor_permissions=current_user.permissions,
            batch_id=batch_id,
        ),
        clock=SystemClock(),
    )

    return _pipeline_response(result, status="COMMITTED")


@router.get("/{batch_id}/exceptions", response_model=ImportExceptionsListResponse)
def list_import_exceptions(
    batch_id: UUID,
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(_IMPORT_ACCESS),
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
