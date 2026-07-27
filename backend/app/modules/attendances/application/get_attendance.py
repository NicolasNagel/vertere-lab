from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.attendances.application.dtos import AttendanceDTO
from app.modules.attendances.application.mappers import attendance_to_dto
from app.modules.attendances.domain.repositories import AttendanceRepository
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "attendances.read"


@dataclass(frozen=True, kw_only=True)
class GetAttendanceQuery:
    actor: AuthenticatedUserDTO
    attendance_id: UUID


class GetAttendanceUseCase:
    def __init__(self, *, attendances: AttendanceRepository) -> None:
        self._attendances = attendances

    def execute(self, query: GetAttendanceQuery) -> AttendanceDTO:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        attendance = self._attendances.get_by_id(query.attendance_id)
        if attendance is None:
            raise NotFoundError("Atendimento não encontrado.")

        return attendance_to_dto(attendance)
