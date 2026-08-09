"""Atomic handlers for attendance mutations other than confirmation."""

from __future__ import annotations

from app.modules.attendances.application.cancel_attendance import (
    CancelAttendanceCommand,
    CancelAttendanceUseCase,
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
from app.modules.attendances.application.update_on_call_fee_setting import (
    UpdateOnCallFeeSettingCommand,
    UpdateOnCallFeeSettingUseCase,
)
from app.modules.attendances.domain.entities import OnCallFeeSetting
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
