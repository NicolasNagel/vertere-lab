"""Attendances API — thin routers, no business rule (rule:
.claude/rules/02-backend.md)."""

from __future__ import annotations

from datetime import date
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session as SqlAlchemySession

from app.api.dependencies import get_session, get_unit_of_work
from app.modules.attendances.api.schemas import (
    AttendanceCancelRequest,
    AttendanceConfirmRequest,
    AttendanceDraftCreateRequest,
    AttendanceExamRead,
    AttendanceExamStatusLiteral,
    AttendanceListResponse,
    AttendancePreviewResponse,
    AttendanceRead,
    AttendanceStatusLiteral,
    AttendanceTimelineEntryRead,
    AttendanceTimelineResponse,
    AttendanceUpdateRequest,
    CollectionMethodLiteral,
    ServiceLevelLiteral,
)
from app.modules.attendances.application.attendance_items import AttendanceItemInput
from app.modules.attendances.application.cancel_attendance import (
    CancelAttendanceCommand,
    CancelAttendanceUseCase,
)
from app.modules.attendances.application.confirm_attendance import (
    ConfirmAttendanceCommand,
    ConfirmAttendanceItemInput,
    ConfirmAttendanceUseCase,
)
from app.modules.attendances.application.create_attendance_draft import (
    CreateAttendanceDraftCommand,
    CreateAttendanceDraftUseCase,
)
from app.modules.attendances.application.dtos import (
    AttendanceDTO,
    AttendanceExamDTO,
    AttendancePreviewDTO,
)
from app.modules.attendances.application.get_attendance import (
    GetAttendanceQuery,
    GetAttendanceUseCase,
)
from app.modules.attendances.application.get_attendance_timeline import (
    GetAttendanceTimelineQuery,
    GetAttendanceTimelineUseCase,
)
from app.modules.attendances.application.list_attendances import (
    ListAttendancesQuery,
    ListAttendancesUseCase,
)
from app.modules.attendances.application.preview_attendance import (
    PreviewAttendanceCommand,
    PreviewAttendanceUseCase,
)
from app.modules.attendances.application.update_attendance import (
    UpdateAttendanceCommand,
    UpdateAttendanceUseCase,
)
from app.modules.attendances.domain.entities import (
    AttendanceStatus,
    CollectionMethod,
    ServiceLevel,
)
from app.modules.attendances.infrastructure.repositories import (
    SqlAlchemyAttendanceRepository,
    SqlAlchemyAttendanceSequenceRepository,
)
from app.modules.audit.infrastructure.repositories import (
    SqlAlchemyAuditLogReader,
    SqlAlchemyAuditLogWriter,
)
from app.modules.catalog.infrastructure.repositories import SqlAlchemyExamRepository
from app.modules.clinics.infrastructure.repositories import SqlAlchemyClinicRepository
from app.modules.identity.api.dependencies import require_permission
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.infrastructure.repositories import SqlAlchemyPatientRepository
from app.modules.veterinarian_clinics.infrastructure.repositories import (
    SqlAlchemyVeterinarianClinicLinkRepository,
)
from app.modules.veterinarians.infrastructure.repositories import SqlAlchemyVeterinarianRepository
from app.shared.idempotency.application.guard import IdempotencyGuard
from app.shared.idempotency.infrastructure.repositories import (
    SqlAlchemyIdempotencyRecordRepository,
)
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/attendances", tags=["attendances"])


def _attendance_exam_read(dto: AttendanceExamDTO) -> AttendanceExamRead:
    return AttendanceExamRead(
        id=dto.id,
        exam_id=dto.exam_id,
        exam_code=dto.exam_code,
        exam_name=dto.exam_name,
        price_base=dto.price_base,
        quantity=dto.quantity,
        discount_amount=dto.discount_amount,
        surcharge_amount=dto.surcharge_amount,
        total_amount=dto.total_amount,
        override_reason=dto.override_reason,
        status=cast(AttendanceExamStatusLiteral, dto.status),
    )


def _attendance_read(dto: AttendanceDTO) -> AttendanceRead:
    return AttendanceRead(
        id=dto.id,
        clinic_id=dto.clinic_id,
        veterinarian_id=dto.veterinarian_id,
        patient_id=dto.patient_id,
        collection_method=cast(CollectionMethodLiteral, dto.collection_method),
        service_level=cast(ServiceLevelLiteral, dto.service_level),
        service_date=dto.service_date,
        notes=dto.notes,
        status=cast(AttendanceStatusLiteral, dto.status),
        items=[_attendance_exam_read(item) for item in dto.items],
        billing_competence=dto.billing_competence,
        subtotal=dto.subtotal,
        discount_total=dto.discount_total,
        surcharge_total=dto.surcharge_total,
        grand_total=dto.grand_total,
        protocol_number=dto.protocol_number,
        cancel_reason=dto.cancel_reason,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
        row_version=dto.row_version,
    )


def _attendance_preview_read(dto: AttendancePreviewDTO) -> AttendancePreviewResponse:
    return AttendancePreviewResponse(
        attendance_id=dto.attendance_id,
        clinic_id=dto.clinic_id,
        veterinarian_id=dto.veterinarian_id,
        patient_id=dto.patient_id,
        collection_method=cast(CollectionMethodLiteral, dto.collection_method),
        service_level=cast(ServiceLevelLiteral, dto.service_level),
        service_date=dto.service_date,
        items=[_attendance_exam_read(item) for item in dto.items],
        subtotal=dto.subtotal,
        discount_total=dto.discount_total,
        surcharge_total=dto.surcharge_total,
        grand_total=dto.grand_total,
    )


@router.get("", response_model=AttendanceListResponse)
def list_attendances(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    clinic_id: UUID | None = Query(None),
    veterinarian_id: UUID | None = Query(None),
    patient_id: UUID | None = Query(None),
    status: AttendanceStatus | None = Query(None),
    protocol_number: str | None = Query(None, min_length=1, max_length=32),
    owner_name: str | None = Query(None, min_length=1, max_length=200),
    service_date_from: date | None = Query(None),
    service_date_to: date | None = Query(None),
    session: SqlAlchemySession = Depends(get_session),
    current_user: AuthenticatedUserDTO = Depends(require_permission("attendances.read")),
) -> AttendanceListResponse:
    use_case = ListAttendancesUseCase(attendances=SqlAlchemyAttendanceRepository(session))
    result = use_case.execute(
        ListAttendancesQuery(
            actor=current_user,
            page=page,
            page_size=page_size,
            clinic_id=clinic_id,
            veterinarian_id=veterinarian_id,
            patient_id=patient_id,
            status=status,
            protocol_number=protocol_number,
            owner_name=owner_name,
            service_date_from=service_date_from,
            service_date_to=service_date_to,
        )
    )
    return AttendanceListResponse(
        items=[_attendance_read(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/{attendance_id}", response_model=AttendanceRead)
def get_attendance(
    attendance_id: UUID,
    session: SqlAlchemySession = Depends(get_session),
    current_user: AuthenticatedUserDTO = Depends(require_permission("attendances.read")),
) -> AttendanceRead:
    use_case = GetAttendanceUseCase(attendances=SqlAlchemyAttendanceRepository(session))
    result = use_case.execute(GetAttendanceQuery(actor=current_user, attendance_id=attendance_id))
    return _attendance_read(result)


@router.get("/{attendance_id}/timeline", response_model=AttendanceTimelineResponse)
def get_attendance_timeline(
    attendance_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: SqlAlchemySession = Depends(get_session),
    current_user: AuthenticatedUserDTO = Depends(require_permission("attendances.read")),
) -> AttendanceTimelineResponse:
    use_case = GetAttendanceTimelineUseCase(
        attendances=SqlAlchemyAttendanceRepository(session),
        audit=SqlAlchemyAuditLogReader(session),
    )
    result = use_case.execute(
        GetAttendanceTimelineQuery(
            actor=current_user, attendance_id=attendance_id, page=page, page_size=page_size
        )
    )
    return AttendanceTimelineResponse(
        items=[
            AttendanceTimelineEntryRead(
                id=entry.id,
                occurred_at=entry.occurred_at,
                actor_user_id=entry.actor_user_id,
                action=entry.action,
                before_state=entry.before_state,
                after_state=entry.after_state,
                reason=entry.reason,
            )
            for entry in result.entries
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.patch("/{attendance_id}", response_model=AttendanceRead)
def update_attendance(
    attendance_id: UUID,
    payload: AttendanceUpdateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("attendances.update")),
) -> AttendanceRead:
    with uow:
        use_case = UpdateAttendanceUseCase(
            attendances=SqlAlchemyAttendanceRepository(uow.session),
            clinics=SqlAlchemyClinicRepository(uow.session),
            veterinarians=SqlAlchemyVeterinarianRepository(uow.session),
            veterinarian_clinics=SqlAlchemyVeterinarianClinicLinkRepository(uow.session),
            patients=SqlAlchemyPatientRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            UpdateAttendanceCommand(
                actor=current_user,
                attendance_id=attendance_id,
                expected_row_version=payload.row_version,
                clinic_id=payload.clinic_id,
                veterinarian_id=payload.veterinarian_id,
                patient_id=payload.patient_id,
                collection_method=(
                    CollectionMethod(payload.collection_method)
                    if payload.collection_method is not None
                    else None
                ),
                service_level=(
                    ServiceLevel(payload.service_level)
                    if payload.service_level is not None
                    else None
                ),
                service_date=payload.service_date,
                notes=payload.notes,
            )
        )
        uow.commit()
    return _attendance_read(result)


@router.post("/drafts", response_model=AttendanceRead, status_code=201)
def create_attendance_draft(
    payload: AttendanceDraftCreateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("attendances.create")),
) -> AttendanceRead:
    with uow:
        use_case = CreateAttendanceDraftUseCase(
            attendances=SqlAlchemyAttendanceRepository(uow.session),
            clinics=SqlAlchemyClinicRepository(uow.session),
            veterinarians=SqlAlchemyVeterinarianRepository(uow.session),
            veterinarian_clinics=SqlAlchemyVeterinarianClinicLinkRepository(uow.session),
            patients=SqlAlchemyPatientRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            CreateAttendanceDraftCommand(
                actor=current_user,
                clinic_id=payload.clinic_id,
                veterinarian_id=payload.veterinarian_id,
                patient_id=payload.patient_id,
                collection_method=CollectionMethod(payload.collection_method),
                service_level=ServiceLevel(payload.service_level),
                service_date=payload.service_date,
                notes=payload.notes,
            )
        )
        uow.commit()
    return _attendance_read(result)


@router.post("/{attendance_id}/preview", response_model=AttendancePreviewResponse)
def preview_attendance(
    attendance_id: UUID,
    payload: AttendanceConfirmRequest,
    session: SqlAlchemySession = Depends(get_session),
    current_user: AuthenticatedUserDTO = Depends(require_permission("attendances.update")),
) -> AttendancePreviewResponse:
    use_case = PreviewAttendanceUseCase(
        attendances=SqlAlchemyAttendanceRepository(session),
        clinics=SqlAlchemyClinicRepository(session),
        veterinarians=SqlAlchemyVeterinarianRepository(session),
        veterinarian_clinics=SqlAlchemyVeterinarianClinicLinkRepository(session),
        patients=SqlAlchemyPatientRepository(session),
        exams=SqlAlchemyExamRepository(session),
    )
    result = use_case.execute(
        PreviewAttendanceCommand(
            actor=current_user,
            attendance_id=attendance_id,
            items=[
                AttendanceItemInput(
                    exam_id=item.exam_id,
                    quantity=item.quantity,
                    discount_amount=item.discount_amount,
                    override_reason=item.override_reason,
                )
                for item in payload.items
            ],
        )
    )
    return _attendance_preview_read(result)


@router.post("/{attendance_id}/confirm", response_model=AttendanceRead)
def confirm_attendance(
    attendance_id: UUID,
    payload: AttendanceConfirmRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=255),
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("attendances.update")),
) -> AttendanceRead:
    clock = SystemClock()
    with uow:
        guard = IdempotencyGuard(records=SqlAlchemyIdempotencyRecordRepository(uow.session))
        outcome = guard.begin(
            actor_id=current_user.id,
            operation=f"attendances.confirm:{attendance_id}",
            idempotency_key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            now=clock.now(),
        )
        if outcome.replayed_response is not None:
            uow.commit()
            _, body = outcome.replayed_response
            return AttendanceRead.model_validate(body)

        use_case = ConfirmAttendanceUseCase(
            attendances=SqlAlchemyAttendanceRepository(uow.session),
            attendance_sequences=SqlAlchemyAttendanceSequenceRepository(uow.session),
            clinics=SqlAlchemyClinicRepository(uow.session),
            veterinarians=SqlAlchemyVeterinarianRepository(uow.session),
            veterinarian_clinics=SqlAlchemyVeterinarianClinicLinkRepository(uow.session),
            patients=SqlAlchemyPatientRepository(uow.session),
            exams=SqlAlchemyExamRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=clock,
        )
        result = use_case.execute(
            ConfirmAttendanceCommand(
                actor=current_user,
                attendance_id=attendance_id,
                items=[
                    ConfirmAttendanceItemInput(
                        exam_id=item.exam_id,
                        quantity=item.quantity,
                        discount_amount=item.discount_amount,
                        override_reason=item.override_reason,
                    )
                    for item in payload.items
                ],
            )
        )
        response = _attendance_read(result)
        guard.complete(
            outcome.record_id,
            status_code=200,
            body=response.model_dump(mode="json"),
            now=clock.now(),
        )
        uow.commit()
    return response


@router.post("/{attendance_id}/cancel", response_model=AttendanceRead)
def cancel_attendance(
    attendance_id: UUID,
    payload: AttendanceCancelRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("attendances.cancel")),
) -> AttendanceRead:
    with uow:
        use_case = CancelAttendanceUseCase(
            attendances=SqlAlchemyAttendanceRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            CancelAttendanceCommand(
                actor=current_user,
                attendance_id=attendance_id,
                reason=payload.reason,
            )
        )
        uow.commit()
    return _attendance_read(result)
