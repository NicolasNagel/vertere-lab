from __future__ import annotations

from app.modules.clinics.application.dtos import ClinicDTO
from app.modules.clinics.domain.entities import Clinic


def clinic_to_dto(clinic: Clinic) -> ClinicDTO:
    return ClinicDTO(
        id=clinic.id,
        name=clinic.name,
        tax_id=str(clinic.tax_id) if clinic.tax_id else None,
        phone=clinic.phone,
        email=clinic.email,
        status=clinic.status.value,
        address_zip_code=clinic.address_zip_code,
        address_street=clinic.address_street,
        address_number=clinic.address_number,
        address_neighborhood=clinic.address_neighborhood,
        address_city=clinic.address_city,
        address_state=clinic.address_state,
        address_complement=clinic.address_complement,
        notes=clinic.notes,
        created_at=clinic.created_at,
        updated_at=clinic.updated_at,
        row_version=clinic.row_version,
    )
