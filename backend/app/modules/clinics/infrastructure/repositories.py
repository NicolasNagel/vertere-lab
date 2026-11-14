"""SQLAlchemy implementation of the clinics repository protocol.

Domain entities are the only thing that crosses back out of this module;
ORM models never leak past this file (rule: .claude/rules/03-database.md).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session as SqlAlchemySession

from app.modules.clinics.domain.entities import Clinic, ClinicStatus
from app.modules.clinics.domain.value_objects import TaxId
from app.modules.clinics.infrastructure.models import ClinicModel
from app.shared.infrastructure.sql import LIKE_ESCAPE, contains_pattern


def _to_domain(model: ClinicModel) -> Clinic:
    return Clinic(
        id=model.id,
        name=model.name,
        tax_id=TaxId(model.tax_id) if model.tax_id else None,
        phone=model.phone,
        email=model.email,
        status=ClinicStatus(model.status),
        address_zip_code=model.address_zip_code,
        address_street=model.address_street,
        address_number=model.address_number,
        address_neighborhood=model.address_neighborhood,
        address_city=model.address_city,
        address_state=model.address_state,
        address_complement=model.address_complement,
        notes=model.notes,
        created_by=model.created_by,
        updated_by=model.updated_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
        row_version=model.row_version,
    )


class SqlAlchemyClinicRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def get_by_id(self, clinic_id: UUID) -> Clinic | None:
        model = self._session.get(ClinicModel, clinic_id)
        return _to_domain(model) if model is not None else None

    def get_by_tax_id(self, tax_id: str) -> Clinic | None:
        model = self._session.execute(
            select(ClinicModel).where(ClinicModel.tax_id == tax_id)
        ).scalar_one_or_none()
        return _to_domain(model) if model is not None else None

    def get_by_name(self, name: str) -> Clinic | None:
        model = self._session.execute(
            select(ClinicModel).where(func.lower(ClinicModel.name) == name.lower())
        ).scalar_one_or_none()
        return _to_domain(model) if model is not None else None

    def list_all_names(self) -> dict[str, UUID]:
        rows = self._session.execute(select(ClinicModel.id, ClinicModel.name)).all()
        return {name.lower(): id_ for id_, name in rows}

    def add(self, clinic: Clinic) -> None:
        self._session.add(
            ClinicModel(
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
                created_by=clinic.created_by,
                updated_by=clinic.updated_by,
                created_at=clinic.created_at,
                updated_at=clinic.updated_at,
                row_version=clinic.row_version,
            )
        )

    def save(self, clinic: Clinic) -> None:
        model = self._session.get(ClinicModel, clinic.id)
        if model is None:
            raise LookupError(f"Clínica {clinic.id} não encontrada para atualização.")
        model.name = clinic.name
        model.tax_id = str(clinic.tax_id) if clinic.tax_id else None
        model.phone = clinic.phone
        model.email = clinic.email
        model.status = clinic.status.value
        model.address_zip_code = clinic.address_zip_code
        model.address_street = clinic.address_street
        model.address_number = clinic.address_number
        model.address_neighborhood = clinic.address_neighborhood
        model.address_city = clinic.address_city
        model.address_state = clinic.address_state
        model.address_complement = clinic.address_complement
        model.notes = clinic.notes
        model.updated_by = clinic.updated_by
        model.updated_at = clinic.updated_at
        model.row_version = clinic.row_version + 1
        clinic.row_version = model.row_version

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: ClinicStatus | None,
        search: str | None,
        clinic_ids: frozenset[UUID] | None = None,
    ) -> tuple[list[Clinic], int]:
        conditions: list[ColumnElement[bool]] = []
        if clinic_ids is not None:
            conditions.append(ClinicModel.id.in_(clinic_ids))
        if status is not None:
            conditions.append(ClinicModel.status == status.value)
        if search:
            like_pattern = contains_pattern(search.lower())
            conditions.append(
                or_(
                    func.lower(ClinicModel.name).like(like_pattern, escape=LIKE_ESCAPE),
                    func.lower(ClinicModel.tax_id).like(like_pattern, escape=LIKE_ESCAPE),
                )
            )

        count_stmt = select(func.count()).select_from(ClinicModel)
        list_stmt = select(ClinicModel).order_by(ClinicModel.name)
        for condition in conditions:
            count_stmt = count_stmt.where(condition)
            list_stmt = list_stmt.where(condition)

        total = self._session.execute(count_stmt).scalar_one()
        list_stmt = list_stmt.offset((page - 1) * page_size).limit(page_size)
        models = self._session.execute(list_stmt).scalars().all()
        return [_to_domain(model) for model in models], total
