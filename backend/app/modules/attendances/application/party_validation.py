"""Shared existence + active-status validation for clinic/veterinarian/
patient — used by draft creation, confirm/preview (`attendance_items.py`)
and controlled edit (`update_attendance.py`). Extracted so this check has
exactly one implementation (rule: duplicou 2x+, extraia — `AGENTS.md`
"Princípios de código"), and so the revalidation discipline
(`.claude/rules/12-attendance.md`: "todo ID é revalidado no momento da
confirmação") stays identical everywhere it applies.
"""

from __future__ import annotations

from uuid import UUID

from app.modules.clinics.domain.entities import ClinicStatus
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.patients.domain.entities import PatientStatus
from app.modules.patients.domain.repositories import PatientRepository
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.entities import VeterinarianStatus
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.domain.errors import NotFoundError, ValidationError


def validate_clinic_veterinarian_patient(
    *,
    clinic_id: UUID,
    veterinarian_id: UUID,
    patient_id: UUID,
    clinics: ClinicRepository,
    veterinarians: VeterinarianRepository,
    veterinarian_clinics: VeterinarianClinicLinkRepository,
    patients: PatientRepository,
) -> None:
    clinic = clinics.get_by_id(clinic_id)
    if clinic is None:
        raise NotFoundError("Clínica não encontrada.")
    if clinic.status != ClinicStatus.ACTIVE:
        raise ValidationError("Clínica não está ativa.")

    veterinarian = veterinarians.get_by_id(veterinarian_id)
    if veterinarian is None:
        raise NotFoundError("Veterinário não encontrado.")
    if veterinarian.status != VeterinarianStatus.ACTIVE:
        raise ValidationError("Veterinário não está ativo.")
    if not veterinarian.is_autonomous:
        link = veterinarian_clinics.get(veterinarian_id, clinic_id)
        if link is None:
            raise ValidationError("Veterinário não está vinculado a esta clínica.")

    patient = patients.get_by_id(patient_id)
    if patient is None:
        raise NotFoundError("Paciente não encontrado.")
    if patient.status != PatientStatus.ACTIVE:
        raise ValidationError("Paciente não está ativo.")
