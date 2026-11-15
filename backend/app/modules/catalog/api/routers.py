"""Catalog API — thin routers, no business rule (rule:
.claude/rules/02-backend.md).

Two routers live here: `exam_categories_router` and `exams_router`, mounted
separately in `app.main`.
"""

from __future__ import annotations

import csv
import io
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session as SqlAlchemySession

from app.api.dependencies import get_session, get_unit_of_work
from app.modules.catalog.api.schemas import (
    ExamCategoryActiveListResponse,
    ExamCategoryCreateRequest,
    ExamCategoryListResponse,
    ExamCategoryRead,
    ExamCategoryStatusLiteral,
    ExamCategoryUpdateRequest,
    ExamCreateRequest,
    ExamImportResponse,
    ExamImportRowErrorRead,
    ExamListResponse,
    ExamRead,
    ExamStatusLiteral,
    ExamUpdateRequest,
)
from app.modules.catalog.application.create_exam import CreateExamCommand
from app.modules.catalog.application.create_exam_category import (
    CreateExamCategoryCommand,
)
from app.modules.catalog.application.deactivate_exam import (
    DeactivateExamCommand,
)
from app.modules.catalog.application.deactivate_exam_category import (
    DeactivateExamCategoryCommand,
)
from app.modules.catalog.application.dtos import ExamCategoryDTO, ExamDTO
from app.modules.catalog.application.get_exam import GetExamQuery, GetExamUseCase
from app.modules.catalog.application.get_exam_category import (
    GetExamCategoryQuery,
    GetExamCategoryUseCase,
)
from app.modules.catalog.application.import_exams import (
    ExamImportRow,
    ImportExamsCommand,
)
from app.modules.catalog.application.list_active_exam_categories import (
    ListActiveExamCategoriesQuery,
    ListActiveExamCategoriesUseCase,
)
from app.modules.catalog.application.list_exam_categories import (
    ListExamCategoriesQuery,
    ListExamCategoriesUseCase,
)
from app.modules.catalog.application.list_exams import ListExamsQuery, ListExamsUseCase
from app.modules.catalog.application.mutation_handlers import (
    handle_create_category,
    handle_create_exam,
    handle_deactivate_category,
    handle_deactivate_exam,
    handle_import_exams,
    handle_update_category,
    handle_update_exam,
)
from app.modules.catalog.application.update_exam import UpdateExamCommand
from app.modules.catalog.application.update_exam_category import (
    UpdateExamCategoryCommand,
)
from app.modules.catalog.domain.entities import ExamCategoryStatus, ExamStatus
from app.modules.catalog.infrastructure.repositories import (
    SqlAlchemyExamCategoryRepository,
    SqlAlchemyExamRepository,
)
from app.modules.catalog.infrastructure.uow import SqlAlchemyCatalogUnitOfWork
from app.modules.identity.api.dependencies import require_permission
from app.shared.application.authorization import ActorContext
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/exam-categories", tags=["catalog"])
exams_router = APIRouter(prefix="/exams", tags=["catalog"])


def _category_read(dto: ExamCategoryDTO) -> ExamCategoryRead:
    return ExamCategoryRead(
        id=dto.id,
        name=dto.name,
        status=cast(ExamCategoryStatusLiteral, dto.status),
        created_at=dto.created_at,
        updated_at=dto.updated_at,
        row_version=dto.row_version,
    )


@router.get("", response_model=ExamCategoryListResponse)
def list_exam_categories(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: ExamCategoryStatus | None = Query(None),
    search: str | None = Query(None),
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("catalog.read")),
) -> ExamCategoryListResponse:
    use_case = ListExamCategoriesUseCase(categories=SqlAlchemyExamCategoryRepository(session))
    result = use_case.execute(
        ListExamCategoriesQuery(
            actor=current_user, page=page, page_size=page_size, status=status, search=search
        )
    )
    return ExamCategoryListResponse(
        items=[_category_read(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/active", response_model=ExamCategoryActiveListResponse)
def list_active_exam_categories(
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("catalog.read")),
) -> ExamCategoryActiveListResponse:
    use_case = ListActiveExamCategoriesUseCase(categories=SqlAlchemyExamCategoryRepository(session))
    result = use_case.execute(ListActiveExamCategoriesQuery(actor=current_user))
    return ExamCategoryActiveListResponse(items=[_category_read(item) for item in result])


@router.get("/{category_id}", response_model=ExamCategoryRead)
def get_exam_category(
    category_id: UUID,
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("catalog.read")),
) -> ExamCategoryRead:
    use_case = GetExamCategoryUseCase(categories=SqlAlchemyExamCategoryRepository(session))
    result = use_case.execute(GetExamCategoryQuery(actor=current_user, category_id=category_id))
    return _category_read(result)


@router.post("", response_model=ExamCategoryRead, status_code=201)
def create_exam_category(
    payload: ExamCategoryCreateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("catalog.manage")),
) -> ExamCategoryRead:
    result = handle_create_category(
        uow=SqlAlchemyCatalogUnitOfWork(uow),
        command=CreateExamCategoryCommand(actor=current_user, name=payload.name),
        clock=SystemClock(),
    )
    return _category_read(result)


@router.patch("/{category_id}", response_model=ExamCategoryRead)
def update_exam_category(
    category_id: UUID,
    payload: ExamCategoryUpdateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("catalog.manage")),
) -> ExamCategoryRead:
    result = handle_update_category(
        uow=SqlAlchemyCatalogUnitOfWork(uow),
        command=UpdateExamCategoryCommand(
            actor=current_user,
            category_id=category_id,
            name=payload.name,
            status=payload.status,
            expected_row_version=payload.expected_row_version,
        ),
        clock=SystemClock(),
    )
    return _category_read(result)


@router.post("/{category_id}/deactivate", response_model=ExamCategoryRead)
def deactivate_exam_category(
    category_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("catalog.manage")),
) -> ExamCategoryRead:
    result = handle_deactivate_category(
        uow=SqlAlchemyCatalogUnitOfWork(uow),
        command=DeactivateExamCategoryCommand(actor=current_user, category_id=category_id),
        clock=SystemClock(),
    )
    return _category_read(result)


def _exam_read(dto: ExamDTO) -> ExamRead:
    return ExamRead(
        id=dto.id,
        code=dto.code,
        name=dto.name,
        category_id=dto.category_id,
        description=dto.description,
        species_ids=list(dto.species_ids),
        component_exam_ids=list(dto.component_exam_ids),
        is_panel=dto.is_panel,
        status=cast(ExamStatusLiteral, dto.status),
        created_at=dto.created_at,
        updated_at=dto.updated_at,
        row_version=dto.row_version,
        price_base=dto.price_base,
        price_valid_from=dto.price_valid_from,
        price_valid_to=dto.price_valid_to,
    )


@exams_router.get("", response_model=ExamListResponse)
def list_exams(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: ExamStatus | None = Query(None),
    category_id: UUID | None = Query(None),
    species_id: UUID | None = Query(None),
    search: str | None = Query(None),
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("catalog.read")),
) -> ExamListResponse:
    use_case = ListExamsUseCase(exams=SqlAlchemyExamRepository(session))
    result = use_case.execute(
        ListExamsQuery(
            actor=current_user,
            page=page,
            page_size=page_size,
            status=status,
            category_id=category_id,
            species_id=species_id,
            search=search,
        )
    )
    return ExamListResponse(
        items=[_exam_read(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@exams_router.get("/{exam_id}", response_model=ExamRead)
def get_exam(
    exam_id: UUID,
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("catalog.read")),
) -> ExamRead:
    use_case = GetExamUseCase(exams=SqlAlchemyExamRepository(session))
    result = use_case.execute(GetExamQuery(actor=current_user, exam_id=exam_id))
    return _exam_read(result)


@exams_router.post("", response_model=ExamRead, status_code=201)
def create_exam(
    payload: ExamCreateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("catalog.manage")),
) -> ExamRead:
    result = handle_create_exam(
        uow=SqlAlchemyCatalogUnitOfWork(uow),
        command=CreateExamCommand(
            actor=current_user,
            name=payload.name,
            category_id=payload.category_id,
            price_base=payload.price_base,
            description=payload.description,
            species_ids=frozenset(payload.species_ids),
            component_exam_ids=tuple(payload.component_exam_ids),
        ),
        clock=SystemClock(),
    )
    return _exam_read(result)


@exams_router.patch("/{exam_id}", response_model=ExamRead)
def update_exam(
    exam_id: UUID,
    payload: ExamUpdateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("catalog.manage")),
) -> ExamRead:
    result = handle_update_exam(
        uow=SqlAlchemyCatalogUnitOfWork(uow),
        command=UpdateExamCommand(
            actor=current_user,
            exam_id=exam_id,
            name=payload.name,
            category_id=payload.category_id,
            price_base=payload.price_base,
            description=payload.description,
            species_ids=frozenset(payload.species_ids),
            component_exam_ids=tuple(payload.component_exam_ids),
            status=payload.status,
            expected_row_version=payload.expected_row_version,
            reason=payload.reason,
        ),
        clock=SystemClock(),
    )
    return _exam_read(result)


@exams_router.post("/{exam_id}/deactivate", response_model=ExamRead)
def deactivate_exam(
    exam_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("catalog.manage")),
) -> ExamRead:
    result = handle_deactivate_exam(
        uow=SqlAlchemyCatalogUnitOfWork(uow),
        command=DeactivateExamCommand(actor=current_user, exam_id=exam_id),
        clock=SystemClock(),
    )
    return _exam_read(result)


_IMPORT_MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB
_IMPORT_REQUIRED_COLUMNS = {"code", "name", "category", "price_base", "species"}
_IMPORT_FALSY_ACTIVE_VALUES = {"false", "0", "inativo", "não", "nao"}


def _parse_import_rows(content: str) -> list[ExamImportRow]:
    reader = csv.DictReader(io.StringIO(content))
    fieldnames = set(reader.fieldnames or [])
    if not _IMPORT_REQUIRED_COLUMNS.issubset(fieldnames):
        missing = ", ".join(sorted(_IMPORT_REQUIRED_COLUMNS - fieldnames))
        raise HTTPException(status_code=422, detail=f"CSV sem as colunas obrigatórias: {missing}.")

    rows: list[ExamImportRow] = []
    for line_number, raw_row in enumerate(reader, start=2):  # line 1 is the header
        species_raw = (raw_row.get("species") or "").strip()
        active_raw = (raw_row.get("active") or "").strip().lower()
        rows.append(
            ExamImportRow(
                line=line_number,
                code=(raw_row.get("code") or "").strip(),
                name=(raw_row.get("name") or "").strip(),
                category_name=(raw_row.get("category") or "").strip(),
                price_base=(raw_row.get("price_base") or "").strip(),
                description=(raw_row.get("description") or "").strip() or None,
                species_names=tuple(
                    part.strip() for part in species_raw.split(";") if part.strip()
                ),
                active=active_raw not in _IMPORT_FALSY_ACTIVE_VALUES,
            )
        )
    return rows


@exams_router.post("/import", response_model=ExamImportResponse)
async def import_exams(
    file: UploadFile = File(...),
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("catalog.manage")),
) -> ExamImportResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Envie um arquivo .csv.")

    raw_bytes = await file.read()
    if len(raw_bytes) > _IMPORT_MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413, detail="Arquivo excede o tamanho máximo permitido (2 MB)."
        )

    try:
        content = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="Arquivo precisa estar em UTF-8.") from exc

    rows = _parse_import_rows(content)

    result = handle_import_exams(
        uow=SqlAlchemyCatalogUnitOfWork(uow),
        command=ImportExamsCommand(actor=current_user, rows=tuple(rows)),
        clock=SystemClock(),
    )

    return ExamImportResponse(
        imported_count=result.imported_count,
        errors=[
            ExamImportRowErrorRead(line=error.line, message=error.message)
            for error in result.errors
        ],
    )
