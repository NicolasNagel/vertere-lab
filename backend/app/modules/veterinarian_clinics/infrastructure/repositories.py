"""SQLAlchemy implementation of the veterinarian-clinic link repository
protocol.

Domain entities are the only thing that crosses back out of this module;
ORM models never leak past this file (rule: .claude/rules/03-database.md).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session as SqlAlchemySession

from app.modules.veterinarian_clinics.domain.entities import VeterinarianClinicLink
from app.modules.veterinarian_clinics.infrastructure.models import VeterinarianClinicModel


def _to_domain(model: VeterinarianClinicModel) -> VeterinarianClinicLink:
    return VeterinarianClinicLink(
        id=model.id,
        veterinarian_id=model.veterinarian_id,
        clinic_id=model.clinic_id,
        primary_clinic=model.primary_clinic,
        created_by=model.created_by,
        created_at=model.created_at,
    )


class SqlAlchemyVeterinarianClinicLinkRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def get(self, veterinarian_id: UUID, clinic_id: UUID) -> VeterinarianClinicLink | None:
        model = self._session.execute(
            select(VeterinarianClinicModel).where(
                VeterinarianClinicModel.veterinarian_id == veterinarian_id,
                VeterinarianClinicModel.clinic_id == clinic_id,
            )
        ).scalar_one_or_none()
        return _to_domain(model) if model is not None else None

    def add(self, link: VeterinarianClinicLink) -> None:
        self._session.add(
            VeterinarianClinicModel(
                id=link.id,
                veterinarian_id=link.veterinarian_id,
                clinic_id=link.clinic_id,
                primary_clinic=link.primary_clinic,
                created_by=link.created_by,
                created_at=link.created_at,
            )
        )

    def delete(self, link: VeterinarianClinicLink) -> None:
        model = self._session.get(VeterinarianClinicModel, link.id)
        if model is None:
            raise LookupError(f"Vínculo {link.id} não encontrado para remoção.")
        self._session.delete(model)

    def clear_primary_for_veterinarian(self, veterinarian_id: UUID) -> None:
        models = (
            self._session.execute(
                select(VeterinarianClinicModel).where(
                    VeterinarianClinicModel.veterinarian_id == veterinarian_id,
                    VeterinarianClinicModel.primary_clinic.is_(True),
                )
            )
            .scalars()
            .all()
        )
        for model in models:
            model.primary_clinic = False

    def mark_primary(self, link_id: UUID) -> None:
        model = self._session.get(VeterinarianClinicModel, link_id)
        if model is None:
            raise LookupError(f"Vínculo {link_id} não encontrado para promoção a principal.")
        model.primary_clinic = True

    def list_by_veterinarian(self, veterinarian_id: UUID) -> list[VeterinarianClinicLink]:
        models = (
            self._session.execute(
                select(VeterinarianClinicModel)
                .where(VeterinarianClinicModel.veterinarian_id == veterinarian_id)
                .order_by(VeterinarianClinicModel.created_at)
            )
            .scalars()
            .all()
        )
        return [_to_domain(model) for model in models]

    def list_by_clinic(self, clinic_id: UUID) -> list[VeterinarianClinicLink]:
        models = (
            self._session.execute(
                select(VeterinarianClinicModel)
                .where(VeterinarianClinicModel.clinic_id == clinic_id)
                .order_by(VeterinarianClinicModel.created_at)
            )
            .scalars()
            .all()
        )
        return [_to_domain(model) for model in models]

    def count_by_veterinarian(self, veterinarian_id: UUID) -> int:
        return self._session.execute(
            select(func.count())
            .select_from(VeterinarianClinicModel)
            .where(VeterinarianClinicModel.veterinarian_id == veterinarian_id)
        ).scalar_one()
