"""Atomic handlers for clinic-directory mutations."""

from __future__ import annotations

from app.modules.clinics.application.create_clinic import CreateClinicCommand, CreateClinicUseCase
from app.modules.clinics.application.deactivate_clinic import (
    DeactivateClinicCommand,
    DeactivateClinicUseCase,
)
from app.modules.clinics.application.dtos import ClinicDTO
from app.modules.clinics.application.update_clinic import UpdateClinicCommand, UpdateClinicUseCase
from app.modules.veterinarian_clinics.application.link_veterinarian_to_clinic import (
    LinkVeterinarianToClinicCommand,
    LinkVeterinarianToClinicUseCase,
)
from app.modules.veterinarian_clinics.application.unlink_veterinarian_from_clinic import (
    UnlinkVeterinarianFromClinicCommand,
    UnlinkVeterinarianFromClinicUseCase,
)
from app.modules.veterinarian_clinics.application.uow import ClinicDirectoryUnitOfWork
from app.modules.veterinarians.application.create_veterinarian import (
    CreateVeterinarianCommand,
    CreateVeterinarianUseCase,
)
from app.modules.veterinarians.application.deactivate_veterinarian import (
    DeactivateVeterinarianCommand,
    DeactivateVeterinarianUseCase,
)
from app.modules.veterinarians.application.dtos import VeterinarianDTO
from app.modules.veterinarians.application.update_veterinarian import (
    UpdateVeterinarianCommand,
    UpdateVeterinarianUseCase,
)
from app.shared.application.clock import Clock


def handle_create_clinic(
    *, uow: ClinicDirectoryUnitOfWork, command: CreateClinicCommand, clock: Clock
) -> ClinicDTO:
    with uow:
        result = CreateClinicUseCase(clinics=uow.clinics, audit=uow.audit, clock=clock).execute(
            command
        )
        uow.commit()
        return result


def handle_update_clinic(
    *, uow: ClinicDirectoryUnitOfWork, command: UpdateClinicCommand, clock: Clock
) -> ClinicDTO:
    with uow:
        result = UpdateClinicUseCase(clinics=uow.clinics, audit=uow.audit, clock=clock).execute(
            command
        )
        uow.commit()
        return result


def handle_deactivate_clinic(
    *, uow: ClinicDirectoryUnitOfWork, command: DeactivateClinicCommand, clock: Clock
) -> ClinicDTO:
    with uow:
        result = DeactivateClinicUseCase(clinics=uow.clinics, audit=uow.audit, clock=clock).execute(
            command
        )
        uow.commit()
        return result


def handle_create_veterinarian(
    *, uow: ClinicDirectoryUnitOfWork, command: CreateVeterinarianCommand, clock: Clock
) -> VeterinarianDTO:
    with uow:
        result = CreateVeterinarianUseCase(
            veterinarians=uow.veterinarians,
            clinics=uow.clinics,
            links=uow.links,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()
        return result


def handle_update_veterinarian(
    *, uow: ClinicDirectoryUnitOfWork, command: UpdateVeterinarianCommand, clock: Clock
) -> VeterinarianDTO:
    with uow:
        result = UpdateVeterinarianUseCase(
            veterinarians=uow.veterinarians, audit=uow.audit, clock=clock
        ).execute(command)
        uow.commit()
        return result


def handle_deactivate_veterinarian(
    *, uow: ClinicDirectoryUnitOfWork, command: DeactivateVeterinarianCommand, clock: Clock
) -> VeterinarianDTO:
    with uow:
        result = DeactivateVeterinarianUseCase(
            veterinarians=uow.veterinarians, audit=uow.audit, clock=clock
        ).execute(command)
        uow.commit()
        return result


def handle_link_veterinarian(
    *, uow: ClinicDirectoryUnitOfWork, command: LinkVeterinarianToClinicCommand, clock: Clock
) -> None:
    with uow:
        LinkVeterinarianToClinicUseCase(
            veterinarians=uow.veterinarians,
            clinics=uow.clinics,
            links=uow.links,
            audit=uow.audit,
            clock=clock,
        ).execute(command)
        uow.commit()


def handle_unlink_veterinarian(
    *, uow: ClinicDirectoryUnitOfWork, command: UnlinkVeterinarianFromClinicCommand
) -> None:
    with uow:
        UnlinkVeterinarianFromClinicUseCase(
            veterinarians=uow.veterinarians, links=uow.links, audit=uow.audit
        ).execute(command)
        uow.commit()
