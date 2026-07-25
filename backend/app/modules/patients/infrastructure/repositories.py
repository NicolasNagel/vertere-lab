"""SQLAlchemy implementation of the species repository protocol.

Domain entities are the only thing that crosses back out of this module;
ORM models never leak past this file (rule: .claude/rules/database.md).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as SqlAlchemySession

from app.modules.patients.domain.entities import Species
from app.modules.patients.infrastructure.models import SpeciesModel


def _to_domain(model: SpeciesModel) -> Species:
    return Species(id=model.id, name=model.name, created_at=model.created_at)


class SqlAlchemySpeciesRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def list_all(self) -> list[Species]:
        models = (
            self._session.execute(select(SpeciesModel).order_by(SpeciesModel.name)).scalars().all()
        )
        return [_to_domain(model) for model in models]
