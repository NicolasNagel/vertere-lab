"""Atomic handlers for attendance mutations other than confirmation."""

from __future__ import annotations

from app.modules.attendances.application.cancel_attendance import (
    CancelAttendanceCommand,
    CancelAttendanceUseCase,
)
from app.modules.attendances.application.clinic_fee_rules import (
    CreateClinicFeeRuleCommand,
    CreateClinicFeeRuleUseCase,
    UpdateClinicFeeRuleCommand,
    UpdateClinicFeeRuleUseCase,
)
from app.modules.attendances.application.create_attendance_draft import (
    CreateAttendanceDraftCommand,
    CreateAttendanceDraftUseCase,
)
from app.modules.attendances.application.dtos import AttendanceDTO
from app.modules.attendances.application.uow import AttendanceUnitOfWork
from app.modules.attendances.application.update_attendance import (
    UpdateAttendanceCommand,
    UpdateAttendanceUseCase,
)
from app.modules.attendances.application.update_attendance_items import (
    UpdateAttendanceItemsCommand,
    UpdateAttendanceItemsUseCase,
)
from app.modules.attendances.application.update_on_call_fee_setting import (
    UpdateOnCallFeeSettingCommand,
    UpdateOnCallFeeSettingUseCase,
)
from app.modules.attendances.application.urgency_fee_setting import (
    UpdateUrgencyFeeSettingCommand,
    UpdateUrgencyFeeSettingUseCase,
)
from app.modules.attendances.domain.entities import (
    ClinicFeeRule,
    OnCallFeeSetting,
    UrgencyFeeSetting,
)
from app.shared.application.clock import Clock


def handle_create_attendance_draft(
    *,
    uow: AttendanceUnitOfWork,
    command: CreateAttendanceDraftCommand,
    clock: Clock,
) -> AttendanceDTO:
    with uow:
        result = CreateAttendanceDraftUseCase(
            attendances=uow.attendances,
            clinics=uow.clinics,
            veterinarians=uow.veterinarians,
            veterinarian_clinics=uow.veterinarian_clinics,
            patients=uow.patients,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result


def handle_update_attendance(
    *,
    uow: AttendanceUnitOfWork,
    command: UpdateAttendanceCommand,
    clock: Clock,
) -> AttendanceDTO:
    with uow:
        result = UpdateAttendanceUseCase(
            attendances=uow.attendances,
            clinics=uow.clinics,
            veterinarians=uow.veterinarians,
            veterinarian_clinics=uow.veterinarian_clinics,
            patients=uow.patients,
            on_call_fees=uow.on_call_fees,
            urgency_fee=uow.urgency_fee,
            clinic_fee_rules=uow.clinic_fee_rules,
            closure_settlement=uow.closure_settlement,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result


def handle_update_attendance_items(
    *,
    uow: AttendanceUnitOfWork,
    command: UpdateAttendanceItemsCommand,
    clock: Clock,
) -> AttendanceDTO:
    with uow:
        result = UpdateAttendanceItemsUseCase(
            attendances=uow.attendances,
            exams=uow.exams,
            closure_settlement=uow.closure_settlement,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result


def handle_cancel_attendance(
    *,
    uow: AttendanceUnitOfWork,
    command: CancelAttendanceCommand,
    clock: Clock,
) -> AttendanceDTO:
    with uow:
        result = CancelAttendanceUseCase(
            attendances=uow.attendances,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result


def handle_update_on_call_fee_setting(
    *,
    uow: AttendanceUnitOfWork,
    command: UpdateOnCallFeeSettingCommand,
    clock: Clock,
) -> OnCallFeeSetting:
    with uow:
        result = UpdateOnCallFeeSettingUseCase(
            on_call_fees=uow.on_call_fees,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result


def handle_update_urgency_fee_setting(
    *,
    uow: AttendanceUnitOfWork,
    command: UpdateUrgencyFeeSettingCommand,
    clock: Clock,
) -> UrgencyFeeSetting:
    with uow:
        result = UpdateUrgencyFeeSettingUseCase(
            urgency_fee=uow.urgency_fee, audit=uow.audit, clock=clock
        ).execute(command)
        uow.commit()
        return result


def handle_create_clinic_fee_rule(
    *,
    uow: AttendanceUnitOfWork,
    command: CreateClinicFeeRuleCommand,
    clock: Clock,
) -> ClinicFeeRule:
    with uow:
        result = CreateClinicFeeRuleUseCase(
            rules=uow.clinic_fee_rules, clinics=uow.clinics, audit=uow.audit, clock=clock
        ).execute(command)
        uow.commit()
        return result


def handle_update_clinic_fee_rule(
    *,
    uow: AttendanceUnitOfWork,
    command: UpdateClinicFeeRuleCommand,
    clock: Clock,
) -> ClinicFeeRule:
    with uow:
        result = UpdateClinicFeeRuleUseCase(
            rules=uow.clinic_fee_rules, audit=uow.audit, clock=clock
        ).execute(command)
        uow.commit()
        return result
