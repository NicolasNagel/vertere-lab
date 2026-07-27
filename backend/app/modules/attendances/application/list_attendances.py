from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.attendances.application.dtos import AttendanceDTO
from app.modules.attendances.application.mappers import attendance_to_dto
from app.modules.attendances.domain.entities import AttendanceStatus
from app.modules.attendances.domain.repositories import AttendanceRepository
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.application.dtos import PageDTO
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "attendances.read"


@dataclass(frozen=True, kw_only=True)
class ListAttendancesQuery:
    actor: AuthenticatedUserDTO
    page: int
    page_size: int
    clinic_id: UUID | None = None
    veterinarian_id: UUID | None = None
    patient_id: UUID | None = None
    status: AttendanceStatus | None = None


class ListAttendancesUseCase:
    def __init__(self, *, attendances: AttendanceRepository) -> None:
        self._attendances = attendances

    def execute(self, query: ListAttendancesQuery) -> PageDTO[AttendanceDTO]:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        attendances, total = self._attendances.list_page(
            page=query.page,
            page_size=query.page_size,
            clinic_id=query.clinic_id,
            veterinarian_id=query.veterinarian_id,
            patient_id=query.patient_id,
            status=query.status,
        )
        return PageDTO(
            items=[attendance_to_dto(attendance) for attendance in attendances],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )
