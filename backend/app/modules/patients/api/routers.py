"""Patients API — thin routers, no business rule (rule:
.claude/rules/backend.md).

Only the read-only `/species` endpoint exists in this slice; `Patient`
itself (and its own router) lands in a later fatia.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as SqlAlchemySession

from app.api.dependencies import get_session
from app.modules.identity.api.dependencies import require_permission
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.api.schemas import SpeciesListResponse, SpeciesRead
from app.modules.patients.application.list_species import ListSpeciesQuery, ListSpeciesUseCase
from app.modules.patients.infrastructure.repositories import SqlAlchemySpeciesRepository

router = APIRouter(prefix="/species", tags=["species"])


@router.get("", response_model=SpeciesListResponse)
def list_species(
    session: SqlAlchemySession = Depends(get_session),
    current_user: AuthenticatedUserDTO = Depends(require_permission("patients.read")),
) -> SpeciesListResponse:
    use_case = ListSpeciesUseCase(species=SqlAlchemySpeciesRepository(session))
    result = use_case.execute(ListSpeciesQuery(actor=current_user))
    return SpeciesListResponse(
        items=[
            SpeciesRead(id=item.id, name=item.name, created_at=item.created_at) for item in result
        ]
    )
