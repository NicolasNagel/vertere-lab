"""SQLAlchemy implementation of the species repository protocol.

Domain entities are the only thing that crosses back out of this module;
ORM models never leak past this file (rule: .claude/rules/03-database.md).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session as SqlAlchemySession

from app.modules.patients.domain.entities import Patient, PatientSex, PatientStatus, Species
from app.modules.patients.infrastructure.models import PatientModel, SpeciesModel
from app.shared.infrastructure.sql import LIKE_ESCAPE, contains_pattern


def _species_to_domain(model: SpeciesModel) -> Species:
    return Species(id=model.id, name=model.name, created_at=model.created_at)


class SqlAlchemySpeciesRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def list_all(self) -> list[Species]:
        models = (
            self._session.execute(select(SpeciesModel).order_by(SpeciesModel.name)).scalars().all()
        )
        return [_species_to_domain(model) for model in models]


def _patient_to_domain(model: PatientModel) -> Patient:
    return Patient(
        id=model.id,
        clinic_id=model.clinic_id,
        name=model.name,
        species_id=model.species_id,
        sex=PatientSex(model.sex),
        breed=model.breed,
        age_description=model.age_description,
        owner_name=model.owner_name,
        owner_phone=model.owner_phone,
        owner_document=model.owner_document,
        status=PatientStatus(model.status),
        notes=model.notes,
        created_by=model.created_by,
        updated_by=model.updated_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
        row_version=model.row_version,
    )


class SqlAlchemyPatientRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def get_by_id(self, patient_id: UUID) -> Patient | None:
        model = self._session.get(PatientModel, patient_id)
        return _patient_to_domain(model) if model is not None else None

    def get_by_owner_and_name(self, *, owner_name: str, name: str) -> Patient | None:
        model = (
            self._session.execute(
                select(PatientModel).where(
                    func.lower(PatientModel.owner_name) == owner_name.lower(),
                    func.lower(PatientModel.name) == name.lower(),
                )
            )
            .scalars()
            .first()
        )
        return _patient_to_domain(model) if model is not None else None

    def add(self, patient: Patient) -> None:
        self._session.add(
            PatientModel(
                id=patient.id,
                clinic_id=patient.clinic_id,
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
                created_by=patient.created_by,
                updated_by=patient.updated_by,
                created_at=patient.created_at,
                updated_at=patient.updated_at,
                row_version=patient.row_version,
            )
        )

    def save(self, patient: Patient) -> None:
        model = self._session.get(PatientModel, patient.id)
        if model is None:
            raise LookupError(f"Paciente {patient.id} não encontrado para atualização.")
        model.name = patient.name
        model.clinic_id = patient.clinic_id
        model.species_id = patient.species_id
        model.sex = patient.sex.value
        model.breed = patient.breed
        model.age_description = patient.age_description
        model.owner_name = patient.owner_name
        model.owner_phone = patient.owner_phone
        model.owner_document = patient.owner_document
        model.status = patient.status.value
        model.notes = patient.notes
        model.updated_by = patient.updated_by
        model.updated_at = patient.updated_at
        model.row_version = patient.row_version + 1
        patient.row_version = model.row_version

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: PatientStatus | None,
        search: str | None,
        clinic_ids: frozenset[UUID] | None = None,
        clinic_id: UUID | None = None,
    ) -> tuple[list[Patient], int]:
        conditions: list[ColumnElement[bool]] = []
        if clinic_ids is not None:
            conditions.append(PatientModel.clinic_id.in_(clinic_ids))
        elif clinic_id is not None:
            conditions.append(PatientModel.clinic_id == clinic_id)
        if status is not None:
            conditions.append(PatientModel.status == status.value)
        if search:
            like_pattern = contains_pattern(search.lower())
            conditions.append(
                or_(
                    func.lower(PatientModel.name).like(like_pattern, escape=LIKE_ESCAPE),
                    func.lower(PatientModel.owner_name).like(like_pattern, escape=LIKE_ESCAPE),
                )
            )

        count_stmt = select(func.count()).select_from(PatientModel)
        list_stmt = select(PatientModel).order_by(PatientModel.name)
        for condition in conditions:
            count_stmt = count_stmt.where(condition)
            list_stmt = list_stmt.where(condition)

        total = self._session.execute(count_stmt).scalar_one()
        list_stmt = list_stmt.offset((page - 1) * page_size).limit(page_size)
        models = self._session.execute(list_stmt).scalars().all()
        return [_patient_to_domain(model) for model in models], total
