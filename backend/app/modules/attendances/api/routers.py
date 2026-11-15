"""Attendances API — thin routers, no business rule (rule:
.claude/rules/02-backend.md)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
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
    AttendanceItemsUpdateRequest,
    AttendanceListResponse,
    AttendancePreviewResponse,
    AttendanceRead,
    AttendanceStatusCountsResponse,
    AttendanceStatusLiteral,
    AttendanceTimelineEntryRead,
    AttendanceTimelineResponse,
    AttendanceUpdateRequest,
    ClinicFeeRuleCreateRequest,
    ClinicFeeRuleListResponse,
    ClinicFeeRuleRead,
    ClinicFeeRuleUpdateRequest,
    CollectionMethodLiteral,
    ExamComponentRead,
    FeeKindLiteral,
    FeeLineRead,
    OnCallFeeSettingListResponse,
    OnCallFeeSettingRead,
    OnCallFeeSettingUpdateRequest,
    OnCallServiceLevelLiteral,
    ServiceLevelLiteral,
    UrgencyFeeSettingRead,
    UrgencyFeeSettingUpdateRequest,
)
from app.modules.attendances.application.attendance_items import AttendanceItemInput
from app.modules.attendances.application.cancel_attendance import (
    CancelAttendanceCommand,
)
from app.modules.attendances.application.clinic_fee_rules import (
    CreateClinicFeeRuleCommand,
    ListClinicFeeRulesQuery,
    ListClinicFeeRulesUseCase,
    UpdateClinicFeeRuleCommand,
)
from app.modules.attendances.application.confirm_attendance import (
    ConfirmAttendanceCommand,
    ConfirmAttendanceItemInput,
)
from app.modules.attendances.application.confirm_attendance_handler import ConfirmAttendanceHandler
from app.modules.attendances.application.create_attendance_draft import (
    CreateAttendanceDraftCommand,
)
from app.modules.attendances.application.dtos import (
    AttendanceDTO,
    AttendanceExamDTO,
    AttendancePreviewDTO,
    FeeLineDTO,
)
from app.modules.attendances.application.get_attendance import (
    GetAttendanceQuery,
    GetAttendanceUseCase,
)
from app.modules.attendances.application.get_attendance_timeline import (
    GetAttendanceTimelineQuery,
    GetAttendanceTimelineUseCase,
)
from app.modules.attendances.application.get_on_call_fee_settings import (
    GetOnCallFeeSettingsQuery,
    GetOnCallFeeSettingsUseCase,
)
from app.modules.attendances.application.list_attendances import (
    CountAttendancesByStatusQuery,
    CountAttendancesByStatusUseCase,
    ListAttendancesQuery,
    ListAttendancesUseCase,
    SumBilledTotalUseCase,
)
from app.modules.attendances.application.mutation_handlers import (
    handle_cancel_attendance,
    handle_create_attendance_draft,
    handle_create_clinic_fee_rule,
    handle_update_attendance,
    handle_update_attendance_items,
    handle_update_clinic_fee_rule,
    handle_update_on_call_fee_setting,
    handle_update_urgency_fee_setting,
)
from app.modules.attendances.application.preview_attendance import (
    PreviewAttendanceCommand,
    PreviewAttendanceUseCase,
)
from app.modules.attendances.application.update_attendance import (
    UpdateAttendanceCommand,
)
from app.modules.attendances.application.update_attendance_items import (
    AttendanceItemEdit,
    UpdateAttendanceItemsCommand,
)
from app.modules.attendances.application.update_on_call_fee_setting import (
    UpdateOnCallFeeSettingCommand,
)
from app.modules.attendances.application.urgency_fee_setting import (
    GetUrgencyFeeSettingQuery,
    GetUrgencyFeeSettingUseCase,
    UpdateUrgencyFeeSettingCommand,
)
from app.modules.attendances.domain.entities import (
    AttendanceStatus,
    ClinicFeeRule,
    CollectionMethod,
    OnCallFeeSetting,
    ServiceLevel,
    UrgencyFeeSetting,
)
from app.modules.attendances.infrastructure.repositories import (
    SqlAlchemyAttendanceRepository,
    SqlAlchemyClinicFeeRuleRepository,
    SqlAlchemyOnCallFeeSettingRepository,
    SqlAlchemyUrgencyFeeSettingRepository,
)
from app.modules.attendances.infrastructure.uow import SqlAlchemyAttendanceUnitOfWork
from app.modules.audit.infrastructure.repositories import (
    SqlAlchemyAuditLogReader,
)
from app.modules.catalog.infrastructure.repositories import SqlAlchemyExamRepository
from app.modules.clinics.infrastructure.repositories import SqlAlchemyClinicRepository
from app.modules.identity.api.dependencies import require_permission
from app.modules.identity.infrastructure.repositories import SqlAlchemyUserNameLookup
from app.modules.patients.infrastructure.repositories import SqlAlchemyPatientRepository
from app.modules.veterinarian_clinics.infrastructure.repositories import (
    SqlAlchemyVeterinarianClinicLinkRepository,
)
from app.modules.veterinarians.infrastructure.repositories import SqlAlchemyVeterinarianRepository
from app.shared.application.authorization import ActorContext
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/attendances", tags=["attendances"])


def _can_see_money(actor: ActorContext) -> bool:
    # Valor financeiro só sai da API para quem tem `pricing.read`; a tela esconder não basta.
    return "pricing.read" in actor.permissions


def _money(value: Decimal, show_money: bool) -> Decimal | None:
    return value if show_money else None


def _fee_lines_read(lines: tuple[FeeLineDTO, ...], show_money: bool) -> list[FeeLineRead]:
    return [
        FeeLineRead(
            kind=cast(FeeKindLiteral, line.kind),
            label=line.label,
            amount=_money(line.amount, show_money),
            rule_id=line.rule_id,
        )
        for line in lines
    ]


def _attendance_exam_read(dto: AttendanceExamDTO, show_money: bool) -> AttendanceExamRead:
    return AttendanceExamRead(
        id=dto.id,
        exam_id=dto.exam_id,
        exam_code=dto.exam_code,
        exam_name=dto.exam_name,
        price_base=_money(dto.price_base, show_money),
        components=[ExamComponentRead(code=code, name=name) for code, name in dto.components],
        quantity=dto.quantity,
        discount_amount=_money(dto.discount_amount, show_money),
        surcharge_amount=_money(dto.surcharge_amount, show_money),
        total_amount=_money(dto.total_amount, show_money),
        override_reason=dto.override_reason,
        status=cast(AttendanceExamStatusLiteral, dto.status),
    )


def _attendance_read(dto: AttendanceDTO, show_money: bool) -> AttendanceRead:
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
        items=[_attendance_exam_read(item, show_money) for item in dto.items],
        billing_competence=dto.billing_competence,
        subtotal=_money(dto.subtotal, show_money),
        discount_total=_money(dto.discount_total, show_money),
        surcharge_total=_money(dto.surcharge_total, show_money),
        on_call_fee=_money(dto.on_call_fee, show_money),
        is_urgent=dto.is_urgent,
        urgency_fee=_money(dto.urgency_fee, show_money),
        clinic_fee=_money(dto.clinic_fee, show_money),
        fee_lines=_fee_lines_read(dto.fee_lines, show_money),
        grand_total=_money(dto.grand_total, show_money),
        protocol_number=dto.protocol_number,
        cancel_reason=dto.cancel_reason,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
        row_version=dto.row_version,
    )


def _attendance_preview_read(
    dto: AttendancePreviewDTO, show_money: bool
) -> AttendancePreviewResponse:
    return AttendancePreviewResponse(
        attendance_id=dto.attendance_id,
        clinic_id=dto.clinic_id,
        veterinarian_id=dto.veterinarian_id,
        patient_id=dto.patient_id,
        collection_method=cast(CollectionMethodLiteral, dto.collection_method),
        service_level=cast(ServiceLevelLiteral, dto.service_level),
        service_date=dto.service_date,
        items=[_attendance_exam_read(item, show_money) for item in dto.items],
        subtotal=_money(dto.subtotal, show_money),
        discount_total=_money(dto.discount_total, show_money),
        surcharge_total=_money(dto.surcharge_total, show_money),
        on_call_fee=_money(dto.on_call_fee, show_money),
        is_urgent=dto.is_urgent,
        urgency_fee=_money(dto.urgency_fee, show_money),
        clinic_fee=_money(dto.clinic_fee, show_money),
        fee_lines=_fee_lines_read(dto.fee_lines, show_money),
        grand_total=_money(dto.grand_total, show_money),
    )


@router.get("", response_model=AttendanceListResponse)
def list_attendances(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    clinic_id: UUID | None = Query(None),
    veterinarian_id: UUID | None = Query(None),
    patient_id: UUID | None = Query(None),
    status: AttendanceStatus | None = Query(None),
    service_level: ServiceLevel | None = Query(None),
    protocol_number: str | None = Query(None, min_length=1, max_length=32),
    owner_name: str | None = Query(None, min_length=1, max_length=200),
    service_date_from: date | None = Query(None),
    service_date_to: date | None = Query(None),
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("attendances.read")),
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
            service_level=service_level,
            protocol_number=protocol_number,
            owner_name=owner_name,
            service_date_from=service_date_from,
            service_date_to=service_date_to,
        )
    )
    return AttendanceListResponse(
        items=[_attendance_read(item, _can_see_money(current_user)) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/status-counts", response_model=AttendanceStatusCountsResponse)
def get_attendance_status_counts(
    clinic_id: UUID | None = Query(None),
    veterinarian_id: UUID | None = Query(None),
    service_level: ServiceLevel | None = Query(None),
    protocol_number: str | None = Query(None, min_length=1, max_length=32),
    owner_name: str | None = Query(None, min_length=1, max_length=200),
    service_date_from: date | None = Query(None),
    service_date_to: date | None = Query(None),
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("attendances.read")),
) -> AttendanceStatusCountsResponse:
    repository = SqlAlchemyAttendanceRepository(session)
    query = CountAttendancesByStatusQuery(
        actor=current_user,
        clinic_id=clinic_id,
        veterinarian_id=veterinarian_id,
        service_level=service_level,
        protocol_number=protocol_number,
        owner_name=owner_name,
        service_date_from=service_date_from,
        service_date_to=service_date_to,
    )
    counts = CountAttendancesByStatusUseCase(attendances=repository).execute(query)
    show_money = _can_see_money(current_user)
    billed_total = (
        SumBilledTotalUseCase(attendances=repository).execute(query) if show_money else None
    )
    return AttendanceStatusCountsResponse(
        total=sum(counts.values()),
        by_status={status.value: count for status, count in counts.items()},
        billed_total=billed_total,
    )


@router.get("/{attendance_id}", response_model=AttendanceRead)
def get_attendance(
    attendance_id: UUID,
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("attendances.read")),
) -> AttendanceRead:
    use_case = GetAttendanceUseCase(attendances=SqlAlchemyAttendanceRepository(session))
    result = use_case.execute(GetAttendanceQuery(actor=current_user, attendance_id=attendance_id))
    return _attendance_read(result, _can_see_money(current_user))


@router.get("/{attendance_id}/timeline", response_model=AttendanceTimelineResponse)
def get_attendance_timeline(
    attendance_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("attendances.read")),
) -> AttendanceTimelineResponse:
    use_case = GetAttendanceTimelineUseCase(
        attendances=SqlAlchemyAttendanceRepository(session),
        audit=SqlAlchemyAuditLogReader(session),
        user_names=SqlAlchemyUserNameLookup(session),
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
                actor_user_id=entry.actor_user_id if current_user.role_scope != "CLINIC" else None,
                actor_name=result.actor_names.get(entry.actor_user_id)
                if entry.actor_user_id
                else None,
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
    current_user: ActorContext = Depends(require_permission("attendances.update")),
) -> AttendanceRead:
    result = handle_update_attendance(
        uow=SqlAlchemyAttendanceUnitOfWork(uow),
        command=UpdateAttendanceCommand(
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
                ServiceLevel(payload.service_level) if payload.service_level is not None else None
            ),
            is_urgent=payload.is_urgent,
            service_date=payload.service_date,
            notes=payload.notes,
            reason=payload.reason,
        ),
        clock=SystemClock(),
    )
    return _attendance_read(result, _can_see_money(current_user))


@router.put("/{attendance_id}/items", response_model=AttendanceRead)
def update_attendance_items(
    attendance_id: UUID,
    payload: AttendanceItemsUpdateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("attendances.update")),
) -> AttendanceRead:
    result = handle_update_attendance_items(
        uow=SqlAlchemyAttendanceUnitOfWork(uow),
        command=UpdateAttendanceItemsCommand(
            actor=current_user,
            attendance_id=attendance_id,
            expected_row_version=payload.row_version,
            reason=payload.reason,
            items=[
                AttendanceItemEdit(
                    item_id=line.item_id,
                    exam_id=line.exam_id,
                    quantity=line.quantity,
                    discount_amount=line.discount_amount,
                    override_reason=line.override_reason,
                )
                for line in payload.items
            ],
        ),
        clock=SystemClock(),
    )
    return _attendance_read(result, _can_see_money(current_user))


@router.post("/drafts", response_model=AttendanceRead, status_code=201)
def create_attendance_draft(
    payload: AttendanceDraftCreateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("attendances.create")),
) -> AttendanceRead:
    result = handle_create_attendance_draft(
        uow=SqlAlchemyAttendanceUnitOfWork(uow),
        command=CreateAttendanceDraftCommand(
            actor=current_user,
            clinic_id=payload.clinic_id,
            veterinarian_id=payload.veterinarian_id,
            patient_id=payload.patient_id,
            collection_method=CollectionMethod(payload.collection_method),
            service_level=ServiceLevel(payload.service_level),
            is_urgent=payload.is_urgent,
            service_date=payload.service_date,
            notes=payload.notes,
        ),
        clock=SystemClock(),
    )
    return _attendance_read(result, _can_see_money(current_user))


@router.post("/{attendance_id}/preview", response_model=AttendancePreviewResponse)
def preview_attendance(
    attendance_id: UUID,
    payload: AttendanceConfirmRequest,
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("attendances.update")),
) -> AttendancePreviewResponse:
    use_case = PreviewAttendanceUseCase(
        attendances=SqlAlchemyAttendanceRepository(session),
        clinics=SqlAlchemyClinicRepository(session),
        veterinarians=SqlAlchemyVeterinarianRepository(session),
        veterinarian_clinics=SqlAlchemyVeterinarianClinicLinkRepository(session),
        patients=SqlAlchemyPatientRepository(session),
        exams=SqlAlchemyExamRepository(session),
        on_call_fees=SqlAlchemyOnCallFeeSettingRepository(session),
        urgency_fee=SqlAlchemyUrgencyFeeSettingRepository(session),
        clinic_fee_rules=SqlAlchemyClinicFeeRuleRepository(session),
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
    return _attendance_preview_read(result, _can_see_money(current_user))


@router.post("/{attendance_id}/confirm", response_model=AttendanceRead)
def confirm_attendance(
    attendance_id: UUID,
    payload: AttendanceConfirmRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=255),
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("attendances.update")),
) -> AttendanceRead:
    result = ConfirmAttendanceHandler(
        uow=SqlAlchemyAttendanceUnitOfWork(uow), clock=SystemClock()
    ).execute(
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
        ),
        idempotency_key=idempotency_key,
    )
    return _attendance_read(result, _can_see_money(current_user))


@router.post("/{attendance_id}/cancel", response_model=AttendanceRead)
def cancel_attendance(
    attendance_id: UUID,
    payload: AttendanceCancelRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("attendances.cancel")),
) -> AttendanceRead:
    result = handle_cancel_attendance(
        uow=SqlAlchemyAttendanceUnitOfWork(uow),
        command=CancelAttendanceCommand(
            actor=current_user,
            attendance_id=attendance_id,
            reason=payload.reason,
        ),
        clock=SystemClock(),
    )
    return _attendance_read(result, _can_see_money(current_user))


on_call_fee_settings_router = APIRouter(prefix="/on-call-fee-settings", tags=["attendances"])


def _on_call_fee_setting_read(setting: OnCallFeeSetting) -> OnCallFeeSettingRead:
    return OnCallFeeSettingRead(
        id=setting.id,
        service_level=cast(OnCallServiceLevelLiteral, setting.service_level.value),
        fee_amount=setting.fee_amount,
        schedule_label=setting.schedule_label,
        updated_at=setting.updated_at,
        row_version=setting.row_version,
    )


@on_call_fee_settings_router.get("", response_model=OnCallFeeSettingListResponse)
def list_on_call_fee_settings(
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("pricing.read")),
) -> OnCallFeeSettingListResponse:
    use_case = GetOnCallFeeSettingsUseCase(
        on_call_fees=SqlAlchemyOnCallFeeSettingRepository(session)
    )
    result = use_case.execute(GetOnCallFeeSettingsQuery(actor=current_user))
    return OnCallFeeSettingListResponse(items=[_on_call_fee_setting_read(item) for item in result])


@on_call_fee_settings_router.patch("/{service_level}", response_model=OnCallFeeSettingRead)
def update_on_call_fee_setting(
    service_level: OnCallServiceLevelLiteral,
    payload: OnCallFeeSettingUpdateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("pricing.manage")),
) -> OnCallFeeSettingRead:
    result = handle_update_on_call_fee_setting(
        uow=SqlAlchemyAttendanceUnitOfWork(uow),
        command=UpdateOnCallFeeSettingCommand(
            actor=current_user,
            service_level=ServiceLevel(service_level),
            fee_amount=payload.fee_amount,
            schedule_label=payload.schedule_label,
            reason=payload.reason,
            expected_row_version=payload.expected_row_version,
        ),
        clock=SystemClock(),
    )
    return _on_call_fee_setting_read(result)


urgency_fee_router = APIRouter(prefix="/urgency-fee-setting", tags=["attendances"])


def _urgency_read(setting: UrgencyFeeSetting) -> UrgencyFeeSettingRead:
    return UrgencyFeeSettingRead(
        id=setting.id,
        fee_amount=setting.fee_amount,
        schedule_label=setting.schedule_label,
        updated_at=setting.updated_at,
        row_version=setting.row_version,
    )


@urgency_fee_router.get("", response_model=UrgencyFeeSettingRead)
def get_urgency_fee_setting(
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("pricing.read")),
) -> UrgencyFeeSettingRead:
    result = GetUrgencyFeeSettingUseCase(
        urgency_fee=SqlAlchemyUrgencyFeeSettingRepository(session)
    ).execute(GetUrgencyFeeSettingQuery(actor=current_user))
    return _urgency_read(result)


@urgency_fee_router.patch("", response_model=UrgencyFeeSettingRead)
def update_urgency_fee_setting(
    payload: UrgencyFeeSettingUpdateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("pricing.manage")),
) -> UrgencyFeeSettingRead:
    result = handle_update_urgency_fee_setting(
        uow=SqlAlchemyAttendanceUnitOfWork(uow),
        command=UpdateUrgencyFeeSettingCommand(
            actor=current_user,
            fee_amount=payload.fee_amount,
            schedule_label=payload.schedule_label,
            reason=payload.reason,
            expected_row_version=payload.expected_row_version,
        ),
        clock=SystemClock(),
    )
    return _urgency_read(result)


clinic_fee_rules_router = APIRouter(prefix="/clinic-fee-rules", tags=["attendances"])


def _clinic_rule_read(rule: ClinicFeeRule) -> ClinicFeeRuleRead:
    return ClinicFeeRuleRead(
        id=rule.id,
        clinic_id=rule.clinic_id,
        name=rule.name,
        fee_amount=rule.fee_amount,
        valid_from=rule.valid_from,
        valid_to=rule.valid_to,
        is_active=rule.is_active,
        updated_at=rule.updated_at,
        row_version=rule.row_version,
    )


@clinic_fee_rules_router.get("", response_model=ClinicFeeRuleListResponse)
def list_clinic_fee_rules(
    clinic_id: UUID | None = Query(default=None),
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("pricing.read")),
) -> ClinicFeeRuleListResponse:
    result = ListClinicFeeRulesUseCase(rules=SqlAlchemyClinicFeeRuleRepository(session)).execute(
        ListClinicFeeRulesQuery(actor=current_user, clinic_id=clinic_id)
    )
    return ClinicFeeRuleListResponse(items=[_clinic_rule_read(rule) for rule in result])


@clinic_fee_rules_router.post("", response_model=ClinicFeeRuleRead, status_code=201)
def create_clinic_fee_rule(
    payload: ClinicFeeRuleCreateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("pricing.manage")),
) -> ClinicFeeRuleRead:
    result = handle_create_clinic_fee_rule(
        uow=SqlAlchemyAttendanceUnitOfWork(uow),
        command=CreateClinicFeeRuleCommand(
            actor=current_user,
            clinic_id=payload.clinic_id,
            name=payload.name,
            fee_amount=payload.fee_amount,
            valid_from=payload.valid_from,
            valid_to=payload.valid_to,
            reason=payload.reason,
        ),
        clock=SystemClock(),
    )
    return _clinic_rule_read(result)


@clinic_fee_rules_router.patch("/{rule_id}", response_model=ClinicFeeRuleRead)
def update_clinic_fee_rule(
    rule_id: UUID,
    payload: ClinicFeeRuleUpdateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("pricing.manage")),
) -> ClinicFeeRuleRead:
    result = handle_update_clinic_fee_rule(
        uow=SqlAlchemyAttendanceUnitOfWork(uow),
        command=UpdateClinicFeeRuleCommand(
            actor=current_user,
            rule_id=rule_id,
            name=payload.name,
            fee_amount=payload.fee_amount,
            valid_from=payload.valid_from,
            valid_to=payload.valid_to,
            is_active=payload.is_active,
            reason=payload.reason,
            expected_row_version=payload.expected_row_version,
        ),
        clock=SystemClock(),
    )
    return _clinic_rule_read(result)
