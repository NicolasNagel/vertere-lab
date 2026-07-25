"""Veterinarians API — thin routers, no business rule (rule:
.claude/rules/backend.md).

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
from app.modules.clinics.infrastructure.repositories import SqlAlchemyClinicRepository
from app.modules.identity.api.dependencies import require_permission
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.veterinarian_clinics.application.link_veterinarian_to_clinic import (
    LinkVeterinarianToClinicCommand,
    LinkVeterinarianToClinicUseCase,
)
from app.modules.veterinarian_clinics.application.list_clinics_for_veterinarian import (
    ListClinicsForVeterinarianQuery,
    ListClinicsForVeterinarianUseCase,
)
from app.modules.veterinarian_clinics.application.unlink_veterinarian_from_clinic import (
    UnlinkVeterinarianFromClinicCommand,
    UnlinkVeterinarianFromClinicUseCase,
)
from app.modules.veterinarian_clinics.infrastructure.repositories import (
    SqlAlchemyVeterinarianClinicLinkRepository,
)
from app.modules.veterinarians.api.schemas import (
    VeterinarianCreateRequest,
    VeterinarianDetailRead,
    VeterinarianLinkClinicRequest,
    VeterinarianLinkedClinic,
    VeterinarianListResponse,
    VeterinarianRead,
    VeterinarianStatusLiteral,
    VeterinarianUpdateRequest,
)
from app.modules.veterinarians.application.create_veterinarian import (
    CreateVeterinarianCommand,
    CreateVeterinarianUseCase,
)
from app.modules.veterinarians.application.deactivate_veterinarian import (
    DeactivateVeterinarianCommand,
    DeactivateVeterinarianUseCase,
)
from app.modules.veterinarians.application.dtos import VeterinarianDTO
from app.modules.veterinarians.application.get_veterinarian import (
    GetVeterinarianQuery,
    GetVeterinarianUseCase,
)
from app.modules.veterinarians.application.list_veterinarians import (
    ListVeterinariansQuery,
    ListVeterinariansUseCase,
)
from app.modules.veterinarians.application.update_veterinarian import (
    UpdateVeterinarianCommand,
    UpdateVeterinarianUseCase,
)
from app.modules.veterinarians.domain.entities import VeterinarianStatus
from app.modules.veterinarians.infrastructure.repositories import SqlAlchemyVeterinarianRepository
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/veterinarians", tags=["veterinarians"])


def _veterinarian_read(dto: VeterinarianDTO) -> VeterinarianRead:
    return VeterinarianRead(
        id=dto.id,
        name=dto.name,
        crmv=dto.crmv,
        phone=dto.phone,
        email=dto.email,
        is_autonomous=dto.is_autonomous,
        status=cast(VeterinarianStatusLiteral, dto.status),
        notes=dto.notes,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
        row_version=dto.row_version,
    )


@router.get("", response_model=VeterinarianListResponse)
def list_veterinarians(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: VeterinarianStatus | None = Query(None),
    is_autonomous: bool | None = Query(None),
    search: str | None = Query(None),
    session: SqlAlchemySession = Depends(get_session),
    current_user: AuthenticatedUserDTO = Depends(require_permission("veterinarians.read")),
) -> VeterinarianListResponse:
    use_case = ListVeterinariansUseCase(veterinarians=SqlAlchemyVeterinarianRepository(session))
    result = use_case.execute(
        ListVeterinariansQuery(
            actor=current_user,
            page=page,
            page_size=page_size,
            status=status,
            is_autonomous=is_autonomous,
            search=search,
        )
    )
    return VeterinarianListResponse(
        items=[_veterinarian_read(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/{veterinarian_id}", response_model=VeterinarianDetailRead)
def get_veterinarian(
    veterinarian_id: UUID,
    session: SqlAlchemySession = Depends(get_session),
    current_user: AuthenticatedUserDTO = Depends(require_permission("veterinarians.read")),
) -> VeterinarianDetailRead:
    use_case = GetVeterinarianUseCase(veterinarians=SqlAlchemyVeterinarianRepository(session))
    result = use_case.execute(
        GetVeterinarianQuery(actor=current_user, veterinarian_id=veterinarian_id)
    )
    clinics_use_case = ListClinicsForVeterinarianUseCase(
        links=SqlAlchemyVeterinarianClinicLinkRepository(session),
        clinics=SqlAlchemyClinicRepository(session),
    )
    linked_clinics = clinics_use_case.execute(
        ListClinicsForVeterinarianQuery(actor=current_user, veterinarian_id=veterinarian_id)
    )
    return VeterinarianDetailRead(
        **_veterinarian_read(result).model_dump(),
        clinics=[
            VeterinarianLinkedClinic(
                clinic_id=item.clinic_id,
                clinic_name=item.clinic_name,
                primary_clinic=item.primary_clinic,
            )
            for item in linked_clinics
        ],
    )


@router.post("", response_model=VeterinarianRead, status_code=201)
def create_veterinarian(
    payload: VeterinarianCreateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("veterinarians.manage")),
) -> VeterinarianRead:
    with uow:
        use_case = CreateVeterinarianUseCase(
            veterinarians=SqlAlchemyVeterinarianRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            CreateVeterinarianCommand(
                actor=current_user,
                name=payload.name,
                crmv=payload.crmv,
                phone=payload.phone,
                email=payload.email,
                is_autonomous=payload.is_autonomous,
                notes=payload.notes,
            )
        )
        uow.commit()
    return _veterinarian_read(result)


@router.patch("/{veterinarian_id}", response_model=VeterinarianRead)
def update_veterinarian(
    veterinarian_id: UUID,
    payload: VeterinarianUpdateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("veterinarians.manage")),
) -> VeterinarianRead:
    with uow:
        use_case = UpdateVeterinarianUseCase(
            veterinarians=SqlAlchemyVeterinarianRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            UpdateVeterinarianCommand(
                actor=current_user,
                veterinarian_id=veterinarian_id,
                name=payload.name,
                crmv=payload.crmv,
                phone=payload.phone,
                email=payload.email,
                is_autonomous=payload.is_autonomous,
                status=payload.status,
                notes=payload.notes,
                expected_row_version=payload.expected_row_version,
            )
        )
        uow.commit()
    return _veterinarian_read(result)


@router.post("/{veterinarian_id}/deactivate", response_model=VeterinarianRead)
def deactivate_veterinarian(
    veterinarian_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("veterinarians.manage")),
) -> VeterinarianRead:
    with uow:
        use_case = DeactivateVeterinarianUseCase(
            veterinarians=SqlAlchemyVeterinarianRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        result = use_case.execute(
            DeactivateVeterinarianCommand(actor=current_user, veterinarian_id=veterinarian_id)
        )
        uow.commit()
    return _veterinarian_read(result)


@router.post("/{veterinarian_id}/clinics", status_code=204)
def link_veterinarian_clinic(
    veterinarian_id: UUID,
    payload: VeterinarianLinkClinicRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("veterinarians.manage")),
) -> None:
    with uow:
        use_case = LinkVeterinarianToClinicUseCase(
            veterinarians=SqlAlchemyVeterinarianRepository(uow.session),
            clinics=SqlAlchemyClinicRepository(uow.session),
            links=SqlAlchemyVeterinarianClinicLinkRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
            clock=SystemClock(),
        )
        use_case.execute(
            LinkVeterinarianToClinicCommand(
                actor=current_user,
                veterinarian_id=veterinarian_id,
                clinic_id=payload.clinic_id,
                primary_clinic=payload.primary,
            )
        )
        uow.commit()


@router.delete("/{veterinarian_id}/clinics/{clinic_id}", status_code=204)
def unlink_veterinarian_clinic(
    veterinarian_id: UUID,
    clinic_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: AuthenticatedUserDTO = Depends(require_permission("veterinarians.manage")),
) -> None:
    with uow:
        use_case = UnlinkVeterinarianFromClinicUseCase(
            veterinarians=SqlAlchemyVeterinarianRepository(uow.session),
            links=SqlAlchemyVeterinarianClinicLinkRepository(uow.session),
            audit=SqlAlchemyAuditLogWriter(uow.session),
        )
        use_case.execute(
            UnlinkVeterinarianFromClinicCommand(
                actor=current_user, veterinarian_id=veterinarian_id, clinic_id=clinic_id
            )
        )
        uow.commit()
