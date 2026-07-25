from __future__ import annotations

from app.modules.patients.application.dtos import PatientDTO, SpeciesDTO
from app.modules.patients.domain.entities import Patient, Species


def species_to_dto(species: Species) -> SpeciesDTO:
    return SpeciesDTO(id=species.id, name=species.name, created_at=species.created_at)


def patient_to_dto(patient: Patient) -> PatientDTO:
    return PatientDTO(
        id=patient.id,
        name=patient.name,
        species_id=patient.species_id,
        sex=patient.sex.value,
        breed=patient.breed,
        age_description=patient.age_description,
        owner_name=patient.owner_name,
        owner_phone=patient.owner_phone,
        owner_document=patient.owner_document,
        status=patient.status.value,
        notes=patient.notes,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
        row_version=patient.row_version,
    )
