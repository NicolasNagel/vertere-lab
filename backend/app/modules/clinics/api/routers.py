"""Clinics API — thin routers, no business rule (rule: .claude/rules/02-backend.md).

Every mutating endpoint owns its transaction via the shared unit of work;
read-only endpoints reuse the request-scoped session from
`app.api.dependencies.get_session`.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as SqlAlchemySession

from app.api.dependencies import get_session, get_unit_of_work
from app.modules.audit.infrastructure.repositories import SqlAlchemyAuditLogWriter
from app.modules.clinics.api.schemas import (
    ClinicCreateRequest,
    ClinicDetailRead,
    ClinicLinkedVeterinarian,
    ClinicListResponse,
    ClinicRead,
    ClinicStatusLiteral,
    ClinicUpdateRequest,
)
from app.modules.clinics.application.create_clinic import CreateClinicCommand, CreateClinicUseCase
from app.modules.clinics.application.deactivate_clinic import (
    DeactivateClinicCommand,
    DeactivateClinicUseCase,
)
from app.modules.clinics.application.dtos import ClinicDTO
from app.modules.clinics.application.get_clinic import GetClinicQuery, GetClinicUseCase
from app.modules.clinics.application.list_clinics import ListClinicsQuery, ListClinicsUseCase
from app.modules.clinics.application.update_clinic import UpdateClinicCommand, UpdateClinicUseCase
from app.modules.clinics.domain.entities import ClinicStatus
from app.modules.clinics.infrastructure.repositories import SqlAlchemyClinicRepository
from app.modules.identity.api.dependencies import require_permission
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.veterinarian_clinics.application.list_veterinarians_for_clinic import (
    ListVeterinariansForClinicQuery,
    ListVeterinariansForClinicUseCase,
)
from app.modules.veterinarian_clinics.infrastructure.repositories import (
    SqlAlchemyVeterinarianClinicLinkRepository,
)
from app.modules.veterinarians.infrastructure.repositories import SqlAlchemyVeterinarianRepository
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/clinics", tags=["clinics"])


def _clinic_read(dto: ClinicDTO) -> ClinicRead:
    return ClinicRead(
        id=dto.id,
        name=dto.name,
        tax_id=dto.tax_id,
        phone=dto.phone,
        email=dto.email,
        status=cast(ClinicStatusLiteral, dto.status),
        address_zip_code=dto.address_zip_code,
        address_street=dto.address_street,
        address_number=dto.address_number,
        address_neighborhood=dto.address_neighborhood,
        address_city=dto.address_city,
        address_state=dto.address_state,
        address_complement=dto.address_complement,
        notes=dto.notes,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
        row_version=dto.row_version,
    )


@router.get("", response_model=ClinicListResponse)
def list_clinics(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: ClinicStatus | None = Query(None),
    search: str | None = Query(None),
    session: SqlAlchemySession = Depends(get_session),
    current_user: AuthenticatedUserDTO = Depends(require_permission("clinics.read")),
) -> ClinicListResponse:
    use_case = ListClinicsUseCase(clinics=SqlAlchemyClinicRepository(session))
    result = use_case.execute(
        ListClinicsQuery(
            actor=current_user, page=page, page_size=page_size, status=status, search=search
        )
    )
    return ClinicListResponse(
        items=[_clinic_read(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/{clinic_id}", response_model=ClinicDetailRead)
def get_clinic(
    clinic_id: UUID,
    session: SqlAlchemySession = Depends(get_session),
    current_user: AuthenticatedUserDTO = Depends(require_permission("clinics.read")),
) -> ClinicDetailRead:
    use_case = GetClinicUseCase(clinics=SqlAlchemyClinicRepository(session))
    result = use_case.execute(GetClinicQuery(actor=current_user, clinic_id=clinic_id))
    veterinarians_use_case = ListVeterinariansForClinicUseCase(
        links=SqlAlchemyVeterinarianClinicLinkRepository(session),
        veterinarians=SqlAlchemyVeterinarianRepository(session),
    )
    linked_veterinarians = veterinarians_use_case.execute(
        ListVeterinariansForClinicQuery(actor=current_user, clinic_id=clinic_id)
    )
    return ClinicDetailRead(
        **_clinic_read(result).model_dump(),
        veterinarians=[
            ClinicLinkedVeterinarian(
                veterinarian_id=item.veterinarian_id,
                veterinarian_name=item.veterinarian_name,
                crmv=item.crmv,
                primary_clinic=item.primary_clinic,
            )
            for item in linked_veterinarians
        ],
    )


@router.post("", response_model=ClinicRead, status_code=201)
def create_clinic(
    payload: ClinicCreateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("clinics.manage")),
) -> ClinicRead:
    with uow:
        use_case = CreateClinicUseCase(
            clinics=SqlAlchemyClinicRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            CreateClinicCommand(
                actor=current_user,
                name=payload.name,
                tax_id=payload.tax_id,
                phone=payload.phone,
                email=payload.email,
                address_zip_code=payload.address_zip_code,
                address_street=payload.address_street,
                address_number=payload.address_number,
                address_neighborhood=payload.address_neighborhood,
                address_city=payload.address_city,
                address_state=payload.address_state,
                address_complement=payload.address_complement,
                notes=payload.notes,
            )
        )
        uow.commit()
    return _clinic_read(result)


@router.patch("/{clinic_id}", response_model=ClinicRead)
def update_clinic(
    clinic_id: UUID,
    payload: ClinicUpdateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("clinics.manage")),
) -> ClinicRead:
    with uow:
        use_case = UpdateClinicUseCase(
            clinics=SqlAlchemyClinicRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            UpdateClinicCommand(
                actor=current_user,
                clinic_id=clinic_id,
                name=payload.name,
                tax_id=payload.tax_id,
                phone=payload.phone,
                email=payload.email,
                status=payload.status,
                address_zip_code=payload.address_zip_code,
                address_street=payload.address_street,
                address_number=payload.address_number,
                address_neighborhood=payload.address_neighborhood,
                address_city=payload.address_city,
                address_state=payload.address_state,
                address_complement=payload.address_complement,
                notes=payload.notes,
                expected_row_version=payload.expected_row_version,
            )
        )
        uow.commit()
    return _clinic_read(result)


@router.post("/{clinic_id}/deactivate", response_model=ClinicRead)
def deactivate_clinic(
    clinic_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("clinics.manage")),
) -> ClinicRead:
    with uow:
        use_case = DeactivateClinicUseCase(
            clinics=SqlAlchemyClinicRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(DeactivateClinicCommand(actor=current_user, clinic_id=clinic_id))
        uow.commit()
    return _clinic_read(result)
