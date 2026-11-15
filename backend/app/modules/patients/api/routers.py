"""Patients API — thin routers, no business rule (rule:
.claude/rules/02-backend.md).

Two routers live here: `species_router` (read-only reference list) and
`patients_router` (full CRUD). Both are mounted separately in `app.main`.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as SqlAlchemySession

from app.api.dependencies import get_session, get_unit_of_work
from app.modules.identity.api.dependencies import get_current_user, require_permission
from app.modules.patients.api.schemas import (
    AgeUnitLiteral,
    PatientCreateRequest,
    PatientListResponse,
    PatientRead,
    PatientSexLiteral,
    PatientStatusLiteral,
    PatientUpdateRequest,
    SpeciesListResponse,
    SpeciesRead,
)
from app.modules.patients.application.create_patient import (
    CreatePatientCommand,
)
from app.modules.patients.application.deactivate_patient import (
    DeactivatePatientCommand,
)
from app.modules.patients.application.dtos import PatientDTO
from app.modules.patients.application.get_patient import GetPatientQuery, GetPatientUseCase
from app.modules.patients.application.list_patients import ListPatientsQuery, ListPatientsUseCase
from app.modules.patients.application.list_species import ListSpeciesQuery, ListSpeciesUseCase
from app.modules.patients.application.mutation_handlers import (
    handle_create_patient,
    handle_deactivate_patient,
    handle_update_patient,
)
from app.modules.patients.application.update_patient import (
    UpdatePatientCommand,
)
from app.modules.patients.domain.entities import PatientStatus
from app.modules.patients.infrastructure.repositories import (
    SqlAlchemyPatientRepository,
    SqlAlchemySpeciesRepository,
)
from app.modules.patients.infrastructure.uow import SqlAlchemyPatientUnitOfWork
from app.shared.application.authorization import ActorContext
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork

species_router = APIRouter(prefix="/species", tags=["species"])
patients_router = APIRouter(prefix="/patients", tags=["patients"])


@species_router.get("", response_model=SpeciesListResponse)
def list_species(
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(get_current_user),
) -> SpeciesListResponse:
    use_case = ListSpeciesUseCase(species=SqlAlchemySpeciesRepository(session))
    result = use_case.execute(ListSpeciesQuery(actor=current_user))
    return SpeciesListResponse(
        items=[
            SpeciesRead(id=item.id, name=item.name, created_at=item.created_at) for item in result
        ]
    )


def _patient_read(dto: PatientDTO) -> PatientRead:
    return PatientRead(
        id=dto.id,
        clinic_id=dto.clinic_id,
        name=dto.name,
        species_id=dto.species_id,
        sex=cast(PatientSexLiteral, dto.sex),
        breed=dto.breed,
        age_description=dto.age_description,
        owner_name=dto.owner_name,
        owner_phone=dto.owner_phone,
        owner_document=dto.owner_document,
        status=cast(PatientStatusLiteral, dto.status),
        notes=dto.notes,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
        row_version=dto.row_version,
        age_value=dto.age_value,
        age_unit=cast(AgeUnitLiteral | None, dto.age_unit),
        age_recorded_on=dto.age_recorded_on,
    )


@patients_router.get("", response_model=PatientListResponse)
def list_patients(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: PatientStatus | None = Query(None),
    search: str | None = Query(None),
    clinic_id: UUID | None = Query(None),
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("patients.read")),
) -> PatientListResponse:
    use_case = ListPatientsUseCase(patients=SqlAlchemyPatientRepository(session))
    result = use_case.execute(
        ListPatientsQuery(
            actor=current_user,
            page=page,
            page_size=page_size,
            status=status,
            search=search,
            clinic_id=clinic_id,
        )
    )
    return PatientListResponse(
        items=[_patient_read(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@patients_router.get("/{patient_id}", response_model=PatientRead)
def get_patient(
    patient_id: UUID,
    session: SqlAlchemySession = Depends(get_session),
    current_user: ActorContext = Depends(require_permission("patients.read")),
) -> PatientRead:
    use_case = GetPatientUseCase(patients=SqlAlchemyPatientRepository(session))
    result = use_case.execute(GetPatientQuery(actor=current_user, patient_id=patient_id))
    return _patient_read(result)


@patients_router.post("", response_model=PatientRead, status_code=201)
def create_patient(
    payload: PatientCreateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("patients.manage")),
) -> PatientRead:
    result = handle_create_patient(
        uow=SqlAlchemyPatientUnitOfWork(uow),
        command=CreatePatientCommand(
            actor=current_user,
            clinic_id=payload.clinic_id,
            name=payload.name,
            species_id=payload.species_id,
            sex=payload.sex,
            breed=payload.breed,
            age_description=payload.age_description,
            owner_name=payload.owner_name,
            owner_phone=payload.owner_phone,
            owner_document=payload.owner_document,
            notes=payload.notes,
            age_value=payload.age_value,
            age_unit=payload.age_unit,
        ),
        clock=SystemClock(),
    )
    return _patient_read(result)


@patients_router.patch("/{patient_id}", response_model=PatientRead)
def update_patient(
    patient_id: UUID,
    payload: PatientUpdateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("patients.manage")),
) -> PatientRead:
    result = handle_update_patient(
        uow=SqlAlchemyPatientUnitOfWork(uow),
        command=UpdatePatientCommand(
            actor=current_user,
            patient_id=patient_id,
            clinic_id=payload.clinic_id,
            name=payload.name,
            species_id=payload.species_id,
            sex=payload.sex,
            breed=payload.breed,
            age_description=payload.age_description,
            owner_name=payload.owner_name,
            owner_phone=payload.owner_phone,
            owner_document=payload.owner_document,
            status=payload.status,
            notes=payload.notes,
            expected_row_version=payload.expected_row_version,
            age_value=payload.age_value,
            age_unit=payload.age_unit,
        ),
        clock=SystemClock(),
    )
    return _patient_read(result)


@patients_router.post("/{patient_id}/deactivate", response_model=PatientRead)
def deactivate_patient(
    patient_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    current_user: ActorContext = Depends(require_permission("patients.manage")),
) -> PatientRead:
    result = handle_deactivate_patient(
        uow=SqlAlchemyPatientUnitOfWork(uow),
        command=DeactivatePatientCommand(actor=current_user, patient_id=patient_id),
        clock=SystemClock(),
    )
    return _patient_read(result)
