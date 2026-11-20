from __future__ import annotations

from app.modules.patients.application.create_patient import (
    CreatePatientCommand,
    CreatePatientUseCase,
)
from app.modules.patients.application.deactivate_patient import (
    DeactivatePatientCommand,
    DeactivatePatientUseCase,
)
from app.modules.patients.application.dtos import PatientDTO
from app.modules.patients.application.reactivate_patient import (
    ReactivatePatientCommand,
    ReactivatePatientUseCase,
)
from app.modules.patients.application.uow import PatientUnitOfWork
from app.modules.patients.application.update_patient import (
    UpdatePatientCommand,
    UpdatePatientUseCase,
)
from app.shared.application.clock import Clock


def handle_create_patient(
    *, uow: PatientUnitOfWork, command: CreatePatientCommand, clock: Clock
) -> PatientDTO:
    with uow:
        r = CreatePatientUseCase(
            patients=uow.patients,
            species=uow.species,
            clinics=uow.clinics,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return r


def handle_update_patient(
    *, uow: PatientUnitOfWork, command: UpdatePatientCommand, clock: Clock
) -> PatientDTO:
    with uow:
        r = UpdatePatientUseCase(
            patients=uow.patients,
            species=uow.species,
            clinics=uow.clinics,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return r


def handle_deactivate_patient(
    *, uow: PatientUnitOfWork, command: DeactivatePatientCommand, clock: Clock
) -> PatientDTO:
    with uow:
        r = DeactivatePatientUseCase(patients=uow.patients, audit=uow.audit, clock=clock).execute(
            command
        )
        uow.commit()
        return r


def handle_reactivate_patient(
    *, uow: PatientUnitOfWork, command: ReactivatePatientCommand, clock: Clock
) -> PatientDTO:
    with uow:
        r = ReactivatePatientUseCase(patients=uow.patients, audit=uow.audit, clock=clock).execute(
            command
        )
        uow.commit()
        return r
