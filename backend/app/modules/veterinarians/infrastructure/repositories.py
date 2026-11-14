"""SQLAlchemy implementation of the veterinarians repository protocol.

Domain entities are the only thing that crosses back out of this module;
ORM models never leak past this file (rule: .claude/rules/03-database.md).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session as SqlAlchemySession

from app.modules.veterinarian_clinics.infrastructure.models import VeterinarianClinicModel
from app.modules.veterinarians.domain.entities import Veterinarian, VeterinarianStatus
from app.modules.veterinarians.domain.value_objects import Crmv
from app.modules.veterinarians.infrastructure.models import VeterinarianModel
from app.shared.infrastructure.sql import LIKE_ESCAPE, contains_pattern


def _to_domain(model: VeterinarianModel) -> Veterinarian:
    return Veterinarian(
        id=model.id,
        name=model.name,
        crmv=Crmv(model.crmv),
        phone=model.phone,
        email=model.email,
        is_autonomous=model.is_autonomous,
        status=VeterinarianStatus(model.status),
        notes=model.notes,
        created_by=model.created_by,
        updated_by=model.updated_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
        row_version=model.row_version,
    )


class SqlAlchemyVeterinarianRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def get_by_id(self, veterinarian_id: UUID) -> Veterinarian | None:
        model = self._session.get(VeterinarianModel, veterinarian_id)
        return _to_domain(model) if model is not None else None

    def get_by_crmv(self, crmv: str) -> Veterinarian | None:
        model = self._session.execute(
            select(VeterinarianModel).where(VeterinarianModel.crmv == crmv)
        ).scalar_one_or_none()
        return _to_domain(model) if model is not None else None

    def get_by_name(self, name: str) -> Veterinarian | None:
        model = (
            self._session.execute(
                select(VeterinarianModel).where(func.lower(VeterinarianModel.name) == name.lower())
            )
            .scalars()
            .first()
        )
        return _to_domain(model) if model is not None else None

    def add(self, veterinarian: Veterinarian) -> None:
        self._session.add(
            VeterinarianModel(
                id=veterinarian.id,
                name=veterinarian.name,
                crmv=str(veterinarian.crmv),
                phone=veterinarian.phone,
                email=veterinarian.email,
                is_autonomous=veterinarian.is_autonomous,
                status=veterinarian.status.value,
                notes=veterinarian.notes,
                created_by=veterinarian.created_by,
                updated_by=veterinarian.updated_by,
                created_at=veterinarian.created_at,
                updated_at=veterinarian.updated_at,
                row_version=veterinarian.row_version,
            )
        )
        # No `relationship()` between VeterinarianModel and
        # VeterinarianClinicModel, so the unit of work can't infer insert
        # order on its own — flush so a same-transaction caller creating
        # links right after (CreateVeterinarianUseCase) doesn't hit a raw
        # FK violation (same pattern as SqlAlchemyUserRepository.add()).
        self._session.flush()

    def save(self, veterinarian: Veterinarian) -> None:
        model = self._session.get(VeterinarianModel, veterinarian.id)
        if model is None:
            raise LookupError(f"Veterinário {veterinarian.id} não encontrado para atualização.")
        model.name = veterinarian.name
        model.crmv = str(veterinarian.crmv)
        model.phone = veterinarian.phone
        model.email = veterinarian.email
        model.is_autonomous = veterinarian.is_autonomous
        model.status = veterinarian.status.value
        model.notes = veterinarian.notes
        model.updated_by = veterinarian.updated_by
        model.updated_at = veterinarian.updated_at
        model.row_version = veterinarian.row_version + 1
        veterinarian.row_version = model.row_version

    def is_linked_to_any_clinic(self, veterinarian_id: UUID, clinic_ids: frozenset[UUID]) -> bool:
        if not clinic_ids:
            return False
        stmt = (
            select(VeterinarianClinicModel.id)
            .where(
                VeterinarianClinicModel.veterinarian_id == veterinarian_id,
                VeterinarianClinicModel.clinic_id.in_(clinic_ids),
            )
            .limit(1)
        )
        return self._session.execute(stmt).first() is not None

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: VeterinarianStatus | None,
        is_autonomous: bool | None,
        search: str | None,
        available_for_clinic_id: UUID | None = None,
        allowed_clinic_ids: frozenset[UUID] | None = None,
    ) -> tuple[list[Veterinarian], int]:
        conditions: list[ColumnElement[bool]] = []
        if status is not None:
            conditions.append(VeterinarianModel.status == status.value)
        if is_autonomous is not None:
            conditions.append(VeterinarianModel.is_autonomous == is_autonomous)
        if search:
            like_pattern = contains_pattern(search.lower())
            conditions.append(
                or_(
                    func.lower(VeterinarianModel.name).like(like_pattern, escape=LIKE_ESCAPE),
                    func.lower(VeterinarianModel.crmv).like(like_pattern, escape=LIKE_ESCAPE),
                )
            )
        if available_for_clinic_id is not None:
            # Mesma regra que /confirm revalida (`.claude/rules/12-attendance.md`):
            # autônomo serve qualquer clínica; não-autônomo só a(s) que ele
            # está vinculado.
            linked_ids = select(VeterinarianClinicModel.veterinarian_id).where(
                VeterinarianClinicModel.clinic_id == available_for_clinic_id
            )
            conditions.append(
                or_(
                    VeterinarianModel.is_autonomous.is_(True),
                    VeterinarianModel.id.in_(linked_ids),
                )
            )
        elif allowed_clinic_ids is not None:
            linked_ids = select(VeterinarianClinicModel.veterinarian_id).where(
                VeterinarianClinicModel.clinic_id.in_(allowed_clinic_ids)
            )
            conditions.append(
                or_(VeterinarianModel.is_autonomous.is_(True), VeterinarianModel.id.in_(linked_ids))
            )

        count_stmt = select(func.count()).select_from(VeterinarianModel)
        list_stmt = select(VeterinarianModel).order_by(VeterinarianModel.name)
        for condition in conditions:
            count_stmt = count_stmt.where(condition)
            list_stmt = list_stmt.where(condition)

        total = self._session.execute(count_stmt).scalar_one()
        list_stmt = list_stmt.offset((page - 1) * page_size).limit(page_size)
        models = self._session.execute(list_stmt).scalars().all()
        return [_to_domain(model) for model in models], total
