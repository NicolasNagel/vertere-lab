"""Attendances API — thin routers, no business rule (rule:
.claude/rules/backend.md).

`POST /attendances/{id}/confirm` has no `Idempotency-Key` in this slice —
see `.claude/rules/attendence.md` deviation note in
`application/confirm_attendance.py`. `/cancel`, `PATCH` and `/timeline`
remain out of scope.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as SqlAlchemySession

from app.api.dependencies import get_session, get_unit_of_work
from app.modules.attendances.api.schemas import (
    AttendanceConfirmRequest,
    AttendanceDraftCreateRequest,
    AttendanceExamRead,
    AttendanceExamStatusLiteral,
    AttendanceListResponse,
    AttendanceRead,
    AttendanceStatusLiteral,
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
from app.modules.attendances.application.dtos import AttendanceDTO, AttendanceExamDTO
from app.modules.attendances.application.get_attendance import (
    GetAttendanceQuery,
    GetAttendanceUseCase,
)
from app.modules.attendances.application.list_attendances import (
    ListAttendancesQuery,
    ListAttendancesUseCase,
)
from app.modules.attendances.domain.entities import AttendanceStatus
from app.modules.attendances.infrastructure.repositories import (
    SqlAlchemyAttendanceRepository,
    SqlAlchemyAttendanceSequenceRepository,
)
from app.modules.audit.infrastructure.repositories import SqlAlchemyAuditLogWriter
from app.modules.catalog.infrastructure.repositories import SqlAlchemyExamRepository
from app.modules.clinics.infrastructure.repositories import SqlAlchemyClinicRepository
from app.modules.identity.api.dependencies import require_permission
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.infrastructure.repositories import SqlAlchemyPatientRepository
from app.modules.veterinarian_clinics.infrastructure.repositories import (
    SqlAlchemyVeterinarianClinicLinkRepository,
)
from app.modules.veterinarians.infrastructure.repositories import SqlAlchemyVeterinarianRepository
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
        created_at=dto.created_at,
        updated_at=dto.updated_at,
        row_version=dto.row_version,
    )


@router.get("", response_model=AttendanceListResponse)
def list_attendances(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    clinic_id: UUID | None = Query(None),
    veterinarian_id: UUID | None = Query(None),
    patient_id: UUID | None = Query(None),
    status: AttendanceStatus | None = Query(None),
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
                service_date=payload.service_date,
                notes=payload.notes,
            )
        )
        uow.commit()
    return _attendance_read(result)


@router.post("/{attendance_id}/confirm", response_model=AttendanceRead)
def confirm_attendance(
    attendance_id: UUID,
    payload: AttendanceConfirmRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("attendances.update")),
) -> AttendanceRead:
    with uow:
        use_case = ConfirmAttendanceUseCase(
            attendances=SqlAlchemyAttendanceRepository(uow.session),
            attendance_sequences=SqlAlchemyAttendanceSequenceRepository(uow.session),
            clinics=SqlAlchemyClinicRepository(uow.session),
            veterinarians=SqlAlchemyVeterinarianRepository(uow.session),
            veterinarian_clinics=SqlAlchemyVeterinarianClinicLinkRepository(uow.session),
            patients=SqlAlchemyPatientRepository(uow.session),
            exams=SqlAlchemyExamRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
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
        uow.commit()
    return _attendance_read(result)
