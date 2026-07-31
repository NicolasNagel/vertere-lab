"""List closed competences — Incremento 4.2, `GET /closures`.

Paginated, optionally scoped to one clinic — same read-only, snapshot-only
principle as `GetMonthlyClosureUseCase`.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.billing.application.dtos import MonthlyClosurePageDTO
from app.modules.billing.application.mappers import monthly_closure_to_dto
from app.modules.billing.domain.repositories import MonthlyClosureRepository
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "closures.read"


@dataclass(frozen=True, kw_only=True)
class ListMonthlyClosuresQuery:
    actor: AuthenticatedUserDTO
    clinic_id: UUID | None
    page: int
    page_size: int


class ListMonthlyClosuresUseCase:
    def __init__(self, *, closures: MonthlyClosureRepository) -> None:
        self._closures = closures

    def execute(self, query: ListMonthlyClosuresQuery) -> MonthlyClosurePageDTO:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        items, total = self._closures.list_page(
            clinic_id=query.clinic_id, page=query.page, page_size=query.page_size
        )
        return MonthlyClosurePageDTO(
            items=[monthly_closure_to_dto(item) for item in items],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )
